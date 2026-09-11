# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Mateus Andrade
"""Command-line interface. Builds no packets itself — calls core.device /
core.protocol, same layering rule as open-m711pro.
"""
import argparse
import sys
import time

from .core import device, keymap, layout, lighting, protocol, state

# Regions known on the hardware this was reverse-engineered against (a Husky
# HTG-series unit, PID 0101). See PROTOCOL.md before assuming these are
# universal to every device sharing this protocol.
KNOWN_REGIONS = (protocol.REGION_KEYS, protocol.REGION_SIDE_LIGHT)

EFFECT_BY_NAME = {name.lower(): value for value, name in protocol.EFFECT_NAMES.items()}


def _resolve_effect(text):
    if text.lower() in EFFECT_BY_NAME:
        return EFFECT_BY_NAME[text.lower()]
    try:
        return int(text, 0)
    except ValueError:
        raise SystemExit(
            f"unknown effect '{text}'. Known names: {', '.join(EFFECT_BY_NAME)}"
        )


def _describe(region, info):
    name = protocol.EFFECT_NAMES.get(info["effect"], f"?({info['effect']})")
    return (f"region {region}: {name}  flag={info['flag']}  speed={info['speed']}  "
            f"brightness={info['brightness']}  colors={info['colors']}")


def cmd_regions(args):
    with lighting.Session.open() as session:
        for region, info in session.snapshot(range(args.scan)).items():
            print(_describe(region, info))


def _report_write(region, description, ok):
    """Say what the keyboard actually did, not what was asked of it.

    `command_process` returns None when the device never reported the command
    as ready. Printing success either way would be exactly the "a plausible
    packet presented as confirmed" this project exists to avoid — and it is how
    an unsupported effect would look like a working one.
    """
    if ok:
        print(f"region {region}: {description}")
        return 0
    print(f"region {region}: the keyboard did not confirm '{description}' — "
          f"it may not support it on this region.\n"
          f"Nothing else was sent. Check with 'open-ek75 regions'.",
          file=sys.stderr)
    return 1


def cmd_set(args):
    effect = _resolve_effect(args.effect)
    colors = [(args.r, args.g, args.b)] if args.r is not None else []
    name = protocol.EFFECT_NAMES.get(effect, effect)

    # Direction only exists on some effects, and sending it where the vendor's
    # own software hides the control would be sending an unvalidated byte.
    if args.flag and protocol.direction_axis(effect) is None:
        print(f"note: {name} has no direction — the vendor's software hides the "
              f"control for it, so --flag {args.flag} is probably ignored. "
              f"Sending it anyway because you asked.", file=sys.stderr)

    with lighting.Session.open() as session:
        ok = session.set_effect(args.region, effect, colors,
                                flag=args.flag, speed=args.speed)
        described = f"set to {name} {colors or ''}".strip()
        if args.flag:
            described += f" direction={args.flag}"
        return _report_write(args.region, described, ok)


def cmd_brightness(args):
    """LED_CMD_BRIGHTNESS write — the one lighting write never sent to hardware."""
    value = (protocol.brightness_from_percent(args.value)
             if args.percent else args.value)
    if not 0 <= value <= protocol.BRIGHTNESS_MAX:
        raise SystemExit(f"brightness must be 0-{protocol.BRIGHTNESS_MAX} "
                          f"(or 0-100 with --percent)")
    with lighting.Session.open() as session:
        ok = session.set_brightness(args.region, value)
        return _report_write(
            args.region,
            f"brightness {value} ({protocol.brightness_to_percent(value)}%)", ok)


def cmd_off(args):
    with lighting.Session.open() as session:
        ok = session.set_effect(args.region, protocol.EFFECT_OFF, [])
        return _report_write(args.region, "off", ok)


def cmd_backup(args):
    """Record what the keyboard currently holds, so a write has a way back."""
    keys = None
    with lighting.Session.open() as session:
        regions = None if args.keys_only else session.snapshot(range(args.scan))
        if not args.lighting_only:
            # Key ids come from the profile's layout, never from a range: they
            # are non-contiguous and run past 83 (the knob sits at 170-172).
            profile = layout.load()
            keys = session.read_key_map([k.id for k in profile.keys])

    state.save(args.path, regions, keys=keys)
    for region, info in (regions or {}).items():
        print(_describe(region, info) + " -- saved")
    if keys is not None:
        answered = sum(1 for v in keys.values() if v is not None)
        print(f"key map: {answered}/{len(keys)} assignments -- saved")
    print(f"\nsaved to {args.path}")


def cmd_restore(args):
    regions = {} if args.keys_only else state.load(args.path)
    keys = None if args.lighting_only else state.load_keys(args.path)
    failed = 0
    with lighting.Session.open() as session:
        for region, ok in session.restore(regions):
            info = regions[region]
            name = protocol.EFFECT_NAMES.get(info["effect"], info["effect"])
            brightness = info.get("brightness")
            detail = f"{name}" + (f", brightness {brightness}"
                                   if brightness is not None else "")
            if ok:
                print(f"region {region}: restored to {detail}")
            else:
                failed += 1
                print(f"region {region}: FAILED restoring to {detail}",
                      file=sys.stderr)

        if keys is None and not args.lighting_only:
            print("no key map in this backup; nothing to restore for keys "
                  "(back it up with 'backup' first)", file=sys.stderr)
            if args.keys_only:
                # The user asked for the key map and nothing else, and nothing
                # happened. Exiting 0 here would tell a script it worked.
                # Without the flag this is not a failure: the file held only
                # lighting and all of it was restored.
                failed += 1
        elif keys:
            results = session.restore_key_map(keys)
            bad = [k for k, ok in results if not ok]
            print(f"key map: {len(results) - len(bad)}/{len(results)} restored")
            for key_id, layer in bad:
                failed += 1
                print(f"key {key_id} layer {layer}: FAILED", file=sys.stderr)

    return 1 if failed else 0


def cmd_probe(args):
    """Read-only discovery: what this keyboard says about itself.

    Sends nothing but GET commands, so it is safe to run on an unknown unit —
    it is the first thing to run when adapting this project to a new PID.
    """
    path = device.find_device()
    print(f"device: {path}")
    with lighting.Session.open() as session:
        battery = session.read_battery()
        if battery is not None:
            pct = f"{battery['percent']}%" if battery["percent"] is not None else "?"
            print(f"battery: {pct}  (level {battery['level']}/{battery['max_level']}, "
                  f"status {battery['status']}, critical {battery['critical']})")
        sleep = session.read_sleep()
        if sleep is not None:
            print("sleep:   " + (f"{sleep['minutes']} min ({sleep['seconds']} s)"
                                  if sleep["enabled"] else "disabled"))

        profiles = session.read_profiles()
        listed = ("no reply" if profiles["ids"] is None
                  else profiles["ids"] or "none reported")
        active = "no reply" if profiles["active"] is None else profiles["active"]
        print(f"profiles: {listed}   active: {active}")
        if profiles["ids"] is not None and len(profiles["ids"]) == 1:
            # The official Windows app offers Profile 1/2/3. Where a keyboard
            # lists one, the other slots do not exist yet — they are created by
            # PFL_CMD_CREATE, a persistent write this project does not send.
            # Exactly one, not "fewer than two": an empty list is a different
            # and stranger answer, and this line would contradict the "none
            # reported" printed directly above it.
            print("          (only one profile exists; the extra slots the "
                  "vendor app shows must be created first)")

        macros = session.read_macros()
        if macros["ids"] is None:
            print("macros:   no reply — this keyboard does not answer CLASS_MACRO")
        elif not macros["ids"]:
            print("macros:   none stored")
        else:
            print(f"macros:   {macros['ids']}")
            for macro_id in macros["ids"]:
                data = session.read_macro_data(macro_id)
                if data is None:
                    print(f"          {macro_id}: no reply")
                else:
                    print(f"          {macro_id}: {len(data)} bytes  "
                          f"{data.hex(' ')}")

        ids, source = session.region_ids()
        print(f"regions: {ids}   (source: {source})")
        for region in ids:
            print(f"\n--- region {region} ---")
            attr = session.region_attribute(region)
            if attr is None:
                print("  LED_CMD_ATTRIBUTE: no reply")
            else:
                print(f"  type={attr['type']}  fps={attr['fps']}  "
                      f"matrix={attr['matrix'][0]}x{attr['matrix'][1]}")
                print(f"  effects_raw={attr['effects_raw']}")
                names = [f"{e}:{protocol.EFFECT_NAMES.get(e, '?')}"
                         for e in attr["effects"]]
                print(f"  effects ({len(names)}): {', '.join(names)}")
            info = session.read_region(region)
            if info is not None:
                print("  " + _describe(region, info))


def cmd_watch(args):
    """Poll one region and print its state whenever it changes.

    Read-only. The point is to learn what the keyboard's own Fn shortcuts do to
    the protocol fields: run this, press Fn+<brightness/speed/direction>, and
    watch which byte moves. That pins the meaning of `flag` and the real range
    of `speed`/`brightness` without writing a single unvalidated byte — see
    PROTOCOL.md.
    """
    print(f"watching region {args.region} — press the keyboard's own Fn "
          f"lighting shortcuts. Ctrl-C to stop.\n")
    previous = None
    with lighting.Session.open() as session:
        try:
            while True:
                info = session.read_region(args.region)
                if info is None:
                    time.sleep(args.interval)
                    continue
                current = (info["effect"], info["flag"], info["speed"],
                           info["brightness"], tuple(info["colors"]))
                if current != previous:
                    stamp = time.strftime("%H:%M:%S")
                    changed = ""
                    if previous is not None:
                        fields = ("effect", "flag", "speed", "brightness", "colors")
                        changed = "   <- changed: " + ", ".join(
                            f for f, a, b in zip(fields, previous, current) if a != b)
                    print(f"[{stamp}] {_describe(args.region, info)}{changed}")
                    previous = current
                time.sleep(args.interval)
        except KeyboardInterrupt:
            print("\nstopped.")


def cmd_gui(args):
    """Open the tkinter UI.

    Imported lazily so the CLI still works on a machine without tkinter
    installed (Arch, for one, splits it into a separate `tk` package).
    """
    try:
        from .gui.app import run
    except ImportError as exc:
        raise SystemExit(
            f"the GUI needs tkinter, which is not available: {exc}\n"
            "On Debian/Ubuntu: sudo apt install python3-tk\n"
            "On Arch/CachyOS:  sudo pacman -S tk"
        )
    return run()


def cmd_keys(args):
    """Print what each key is actually assigned to, read from the keyboard.

    Read-only. This is the command that answers "is my keyboard still at factory
    defaults?", which the vendor's device profile cannot: on the unit this was
    built against, 23 of 166 assignments differ from it — see PROTOCOL.md.
    """
    profile = layout.load()
    layers = ({"base": (protocol.LAYER_BASE,), "fn": (protocol.LAYER_FN,)}
              .get(args.layer, (protocol.LAYER_BASE, protocol.LAYER_FN)))
    with lighting.Session.open() as session:
        live = session.read_key_map([k.id for k in profile.keys], layers=layers)

    unread = differing = shown = 0
    for key in profile.keys:
        for layer in layers:
            got = live[(key.id, layer)]
            if got is None:
                unread += 1
                print(f"  {key.label:<11} {_LAYER_NAMES[layer]:<5} (no reply)")
                continue
            expected_id = (key.function_id if layer == protocol.LAYER_BASE
                           else key.fn_function_id)
            expected_data = list(key.function_data if layer == protocol.LAYER_BASE
                                 else key.fn_function_data)
            same = (got["function_id"], got["data"]) == (expected_id, expected_data)
            if same:
                if args.diff:
                    continue
            else:
                differing += 1
            label = keymap.describe(got["function_id"], got["data"])
            text = label[0 if i18n_lang() == "en" else 1] if label else \
                f"fid={got['function_id']} {got['data']}"
            mark = "" if same else "  <- differs from the vendor profile"
            print(f"  {key.label:<11} {_LAYER_NAMES[layer]:<5} {text}{mark}")
            shown += 1

    print(f"\n{shown} shown, {differing} differ from {profile.pid}.json"
          + (f", {unread} unread" if unread else ""))
    if differing:
        print("The keyboard is the authority; the profile is the vendor's idea of "
              "this PID. See PROTOCOL.md.")


_LAYER_NAMES = {protocol.LAYER_BASE: "base", protocol.LAYER_FN: "fn"}


def i18n_lang():
    """The CLI is English-only; the GUI has the language switch. This exists so
    keymap's (english, portuguese) pairs are indexed in one obvious place."""
    return "en"


def _only_flags(parser):
    """`--keys-only` / `--lighting-only`, mutually exclusive.

    Backup and restore both cover two independent things now. Someone restoring
    a lighting mistake should not be made to rewrite 166 key assignments to do
    it, and someone recovering a key map should not have their current colours
    replaced by whatever was on screen when the file was written.
    """
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--keys-only", action="store_true",
                       help="the key map only, leaving lighting alone")
    group.add_argument("--lighting-only", action="store_true",
                       help="the lighting only, leaving the key map alone")


def build_parser():
    p = argparse.ArgumentParser(prog="open-ek75",
        description="Configure a Dareu TK51G/EK75 keyboard on Linux "
                     "(sold as Husky HTG200/HTG500/HTG800 V2 and others).")
    sub = p.add_subparsers(dest="command", required=True)

    p_regions = sub.add_parser("regions", help="list lighting regions and their current state")
    p_regions.add_argument("--scan", type=int, default=8,
                            help="RegionIds to probe, 0..N-1 (default: 8)")
    p_regions.set_defaults(func=cmd_regions)

    p_set = sub.add_parser("set", help="apply an effect to one region")
    p_set.add_argument("region", type=int)
    p_set.add_argument("effect", help="name (static, breathing, off, ...) or number")
    p_set.add_argument("r", type=int, nargs="?", default=None)
    p_set.add_argument("g", type=int, nargs="?", default=0)
    p_set.add_argument("b", type=int, nargs="?", default=0)
    p_set.add_argument("--speed", type=int, default=0,
                        help=f"animation speed, {protocol.SPEED_MIN}-"
                             f"{protocol.SPEED_MAX} ({protocol.SPEED_NORMAL} is "
                             f"the vendor's 'normal'); only some effects use it")
    p_set.add_argument("--flag", "--direction", type=int, default=0,
                        choices=(protocol.DIRECTION_FORWARD,
                                 protocol.DIRECTION_REVERSE),
                        help="animation direction: 0 forward (left-to-right or "
                             "top-to-bottom), 1 reverse. Only Wave has one on "
                             "this keyboard — see PROTOCOL.md")
    p_set.set_defaults(func=cmd_set)

    p_bright = sub.add_parser(
        "brightness", help="set a region's brightness (UNCONFIRMED on hardware)")
    p_bright.add_argument("region", type=int)
    p_bright.add_argument("value", type=int,
                           help=f"0-{protocol.BRIGHTNESS_MAX}, or 0-100 with --percent")
    p_bright.add_argument("--percent", action="store_true",
                           help="read `value` as the 1-100 the official software shows")
    p_bright.set_defaults(func=cmd_brightness)

    p_off = sub.add_parser("off", help="turn a region off")
    p_off.add_argument("region", type=int)
    p_off.set_defaults(func=cmd_off)

    p_backup = sub.add_parser(
        "backup", help="save the lighting state and the key map")
    p_backup.add_argument("path", nargs="?", default=state.DEFAULT_PATH)
    p_backup.add_argument("--scan", type=int, default=8)
    _only_flags(p_backup)
    p_backup.set_defaults(func=cmd_backup)

    p_restore = sub.add_parser("restore", help="apply a state saved by 'backup'")
    p_restore.add_argument("path", nargs="?", default=state.DEFAULT_PATH)
    _only_flags(p_restore)
    p_restore.set_defaults(func=cmd_restore)

    p_gui = sub.add_parser("gui", help="open the graphical interface (tkinter)")
    p_gui.set_defaults(func=cmd_gui)

    p_keys = sub.add_parser(
        "keys", help="read-only: what each key is assigned to, from the keyboard")
    p_keys.add_argument("--layer", choices=("base", "fn", "both"), default="both")
    p_keys.add_argument("--diff", action="store_true",
                         help="show only keys that differ from the vendor profile")
    p_keys.set_defaults(func=cmd_keys)

    p_probe = sub.add_parser(
        "probe", help="read-only: regions, per-region attributes and effect lists")
    p_probe.set_defaults(func=cmd_probe)

    p_watch = sub.add_parser(
        "watch",
        help="read-only: print a region's state whenever it changes "
             "(use with the keyboard's own Fn lighting shortcuts)")
    p_watch.add_argument("region", type=int, nargs="?", default=protocol.REGION_KEYS)
    p_watch.add_argument("--interval", type=float, default=0.4)
    p_watch.set_defaults(func=cmd_watch)

    return p


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        status = args.func(args)
        if status:
            return status
    except FileNotFoundError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    except PermissionError as e:
        # The keyboard is there, the HID node is root-only. The fix is one
        # command, so say which one instead of showing a traceback.
        print(f"error: {e}\n\n"
              "The keyboard's HID node is not accessible to your user. Install\n"
              "the udev rule once, then replug the keyboard:\n"
              "    sudo sh packaging/install.sh",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
