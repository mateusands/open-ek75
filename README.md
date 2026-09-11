# open-ek75

**English** · [Português (Brasil)](README.pt-br.md)

**Configure the RGB lighting of a Dareu TK51G/EK75 keyboard — sold in Brazil as
the Husky Nomadic — on Linux, with no Windows needed.** Read the real
effect, colour and brightness of every lighting zone and change any of them,
from a graphical interface or the command line.

Dareu (the actual chip/firmware vendor) ships a **web-based** configuration
tool, [dr.dareu.com](https://dr.dareu.com/), that talks to the keyboard
straight from Chrome via WebHID — no native app, Windows-only or otherwise.
This project ports that tool's own protocol logic to Python: the JavaScript
was decompiled (it is minified but not obfuscated — every class, method and
constant name survives) and every packet this code sends was replayed against
real hardware before it shipped.

Written in pure Python, for **Linux** (it drives the keyboard through
`hidraw`). **Zero dependencies** — standard library only, including the
graphical interface, which is tkinter.

> Not affiliated with or endorsed by Dareu, Husky, or any other brand this
> keyboard is sold under. Use at your own risk.

## Does this work with your keyboard?

Run `lsusb` and look for **`260d:0101`**:

```
Bus 003 Device 003: ID 260d:0101  EK75_Keyboard
```

This chip/firmware combination is a Dareu reference design (internally called
**TK51G**, sold at retail as **EK75**) that multiple brands rebrand under
their own model names. Confirmed so far:

| Brand | Model(s) |
|-------|----------|
| Dareu | TK51G / EK75 |
| Husky (Kabum, Brazil) | **Nomadic** — HTG200 / HTG500 / HTG800 V2 |

The name on the box and the name in the firmware are different, which is worth
knowing if you are searching: Husky sells this as the **Nomadic**, while the
keyboard itself only ever reports `TK51G` / `EK75`. "Nomadic" appears nowhere in
Dareu's own driver, its device profile, or the Windows application's binaries —
it is Husky's retail branding over a Dareu reference design.

If your keyboard's `lsusb` shows a **different** PID under vendor `260D`,
check `https://dr.dareu.com/products/<PID>/<PID>.json` — if it exists and its
`"FwType"` is `0`, this same code very likely works unmodified (see
[PROTOCOL.md](PROTOCOL.md) for what `FwType` changes). A different
`FwType` needs a different Report ID/size, which `ek75/core/device.py`
already does not hardcode incorrectly — but `find_device()`'s descriptor
signature was written against the `FwType: 0` device and may need adjusting.

> **Connect the keyboard by its USB cable to configure it.** This model can
> also run over a 2.4G dongle, and configuration does not work that way — the
> keyboard will not answer, and `open-ek75` will report that it cannot find it.
> Three separate things agree on this: the vendor's own JavaScript switches to
> a different Report ID when its `WirelessFlag` says 2.4G, its Windows
> application hides a whole `gdDisableWl` panel of settings when the connection
> is wireless, and the owner of the unit this was built against confirmed it
> directly. Once a setting is written over the cable it is kept in the
> keyboard's own memory, so you can unplug and go back to wireless afterwards.

## What works

- **A graphical interface** (`open-ek75 gui`) with the keyboard drawn from
  Dareu's own device profile — 83 keys in the vendor's own geometry, volume
  knob included — an animated preview of the selected effect, and every
  lighting control on one screen. **English or Brazilian Portuguese**, switched
  from the header and remembered between runs.
- **A guide to the Fn shortcuts**, on the Device page. This keyboard has 38 of
  them and prints none on the case; they are decoded from the key map the
  keyboard itself ships with, so the list is the hardware's, not a guess.
  `Fn` + `I` is Print Screen, `Fn` + `Space` cycles the brightness, and so on.
- **Reading** the real state of every lighting zone: effect, colour(s),
  speed, brightness — not just what this tool last wrote.
- **Asking the keyboard which effects each zone supports**
  (`LED_CMD_ATTRIBUTE`) and which zones exist (`LED_CMD_ID_LIST`), instead of
  offering all 33 effects and hoping. This matters more than it sounds: on the
  unit this was built against the firmware reports four effects that the
  vendor's own device profile leaves out, and omits one the profile offers.
- **The vendor's own effect names**, in English and Brazilian Portuguese, taken
  from the official software's string table — so "Difusão" here is the same
  effect as "Difusão" there, even though the protocol calls it `Rotate`.
- **RGB mode** — sending an empty colour list is how the wire says "you
  choose", which is the rainbow the official software calls RGB and what this
  keyboard ships with for `Wave`. The colour picker offers it as a swatch.
- **A preview that matches the hardware**, not an approximation of it: the
  rainbow ramp and the side light's fixed pattern are the firmware's own colour
  tables, lifted out of the vendor's software rather than guessed at with HSV.
- **Setting** `Static` (solid colour) and `Breathing` (pulsing colour) on any
  zone, with any RGB colour — plus the other effects your keyboard reports as
  supported, which are ported but not individually confirmed on hardware.
- **Brightness and speed on the ranges the hardware actually uses** —
  brightness as a percentage of a 0-255 byte (which is how the official
  software's 1-100 slider works), and speed 1-3 rather than 0-255. Both came
  from decompiling the vendor's Windows application, an independent
  implementation of the same protocol; see [PROTOCOL.md](PROTOCOL.md),
  "A second vendor source".
- **Honest about what does not work.** The packet's `Flag` byte is the
  animation direction in the vendor's software, and this firmware stores it
  faithfully — but was tested and confirmed **not to render it**. The control
  is still there, labelled as such, because the packet is right and a sibling
  model may honour it. The same goes for the side light under `Static`, which
  lights up but renders a fixed pattern and ignores the colour you send.
- **Backup/restore** of the full lighting state to a JSON file, so a test that
  doesn't look right is one command away from being undone. The GUI takes one
  automatically the first time it connects.

Two lighting zones are confirmed on the keyboard this was built against (a
Husky HTG-series unit): region `1` is the per-key matrix (a 6x15 LED grid) and
region `4` is the side light bar (a strip of 16). `open-ek75 probe` asks your
own keyboard which zones it has, and which effects each one supports.

**Reading is further along than writing**, and the split is deliberate: a read
can be wrong and you just get a wrong answer, while a write can leave a
physical keyboard in a state you cannot get out of.

*Implemented, read-only*: the battery level and idle timer, the key map (`keys`
— what every key does on both layers, taken from the keyboard rather than from
the vendor's profile, which disagrees with this hardware 23 times), which
profiles exist and which is active, and the stored macros (`probe`).

That last one is worth a sentence: Dareu's device profile does not contain the
word "macro", and the keyboard this was built against has one stored anyway. The
raw bytes are shown because the format is not decoded — the code that builds it
is not in any vendor file this project has, and a guess at the keystrokes would
be an invented format.

*Implemented, and it writes*: the lighting, and **remapping a key** from the
GUI's Keys page — pick a key, pick a layer, and assign it another key (with
Ctrl/Shift/Alt/Win if you want), a media key, or whatever another key on your
keyboard already does. `backup` records the key map alongside the lighting and
`restore` puts both back; use `--keys-only` or `--lighting-only` to move just
one of them.

Nothing is written until a key map has been backed up, and two keys can never be
remapped: whichever ones carry `Fn` and the factory reset. Together they are
**`Fn`+`Esc`, a factory reset built into the firmware** — the way back that needs
nothing from this software, and which remapping either half would destroy.

**Profiles** are named files on this machine — `open-ek75 profiles`, or the
Profiles page. That is not a workaround for the device's single profile: it is
where the vendor's own app keeps its Profile 1/2/3 too, which was settled by
decompiling both of Dareu's implementations. What it does not give is switching
with a key on the keyboard.

**Not implemented**: per-key colour maps, recording or editing macros, and
creating a second profile in the device's own memory. The last one is worth being blunt about: the official
Windows app shows Profile 1/2/3, and this keyboard reports exactly one. The
other two are not hidden — they do not exist, and creating them is a persistent
write whose undo has never been tested. The GUI shows unimplemented features as
named and unimplemented rather than hiding them, each saying which command class
it needs.
See [PROTOCOL.md](PROTOCOL.md) — specifically "What is not
implemented yet" and "What to try next" — for the full map of what is known
but unported, versus genuinely unknown.

## Requirements

Linux, Python 3.8+, no dependencies.

## Install

From a checkout of this repository:

```bash
git clone https://github.com/mateusands/open-ek75 && cd open-ek75
sudo sh packaging/install.sh
```

That installs a udev rule for `260d:0101` so the keyboard's HID node is
usable without root, using `TAG+="uaccess"` — the same modern
systemd/logind mechanism `open-m711pro` uses, for the same reason: it hands
the device to the logged-in user's active session instead of leaving it
world-writable forever with `MODE="0666"`. See the comments in
[packaging/60-ek75.rules](packaging/60-ek75.rules) for the details and a
fallback for systems without `systemd-logind`. Replug the keyboard afterwards.

Then, optionally, `pip install --user .` for the `open-ek75` command anywhere
on your `PATH` — running from the checkout with `python3 main.py` needs no
install at all.

## Usage

### Graphical interface

```bash
python3 main.py gui        # or `open-ek75 gui`, or `open-ek75-gui`, once installed
```

It opens on **Device**: what this keyboard is, backup/restore, and the full
list of Fn shortcuts. The other three pages match the official software's
shape — **Lighting** (the working one), **Keys** and **Macros** (not
implemented; they say so, and say which command class they would need).

The language switch is the `EN` / `PT-BR` pair in the header. It defaults to
English and remembers your choice in `~/.config/open-ek75/settings.json`;
`OPEN_EK75_LANG=pt` overrides it for one run.

The lighting page asks the keyboard which effects each zone supports and shows
only those, and shows a control only when the selected effect has it — no speed
slider on `Static`, no direction arrows on anything but `Wave` — which is what
the official software does, for the same reason.

### Command line

```bash
python3 main.py probe                # read-only: zones, their supported effects, their state
python3 main.py regions              # read every zone's current state
python3 main.py set 1 static ff0000  # key matrix: solid red
python3 main.py set 4 static 00c8ff  # side light: solid cyan-blue
python3 main.py set 1 breathing 00ff00 --speed 2
python3 main.py set 1 wave --speed 2          # no colour given = the firmware's rainbow
python3 main.py set 1 wave --speed 3 --flag 1 # direction: see PROTOCOL.md before trusting it
python3 main.py brightness 1 60 --percent     # or `brightness 1 153` for the raw byte
python3 main.py off 4                # side light off

python3 main.py backup                       # save every zone to ~/.config/open-ek75/backup.json
python3 main.py backup mine.json             # ...or to a file you name
python3 main.py restore                      # put it all back

python3 main.py watch 1                      # read-only: print zone 1's state as it changes
```

`watch` writes nothing. Run it and press the keyboard's own Fn lighting
shortcuts: it prints which protocol field the firmware moved. That is how the
remaining unknowns (what `Flag` means, what range `Speed` and brightness
accept) get settled without sending the hardware a byte no one has validated —
see [PROTOCOL.md](PROTOCOL.md), "What to try next".

`set` takes the region number, an effect (by name — `static`, `breathing`,
`wave`, `off`, or any of the 33 in [PROTOCOL.md](PROTOCOL.md) — or a raw
number), and an R G B colour as three separate byte arguments (`0` `255` `0`).
**Leave the colour out** and the firmware picks its own, which is the rainbow
form of the animated effects.

`--speed` runs 1-3 (2 is the vendor's "normal") and only some effects use it.
`--flag` is the animation direction, 0 or 1 — the vendor's software treats it
that way and this firmware stores it faithfully, but was confirmed **not** to
render it; `PROTOCOL.md` has the whole story. `brightness` takes a raw 0-255
byte, or 0-100 with `--percent`, which is the scale the official software's
slider shows.

**Run `backup` before experimenting.** The lighting state is written to the
keyboard's persistent memory — a change is not undone by unplugging the
cable or power-cycling. `restore` is the way back.

## Project layout

```
main.py                  entry point (also `python3 -m ek75`, or `open-ek75` once installed)
ek75/
├── cli.py                command-line interface — never builds packets itself
├── core/
│   ├── protocol.py       packet builders + parsers — PURE LOGIC, no I/O
│   ├── device.py         hidraw I/O (find_device, command_process, multi-packet reads)
│   ├── lighting.py       high-level lighting operations, shared by the CLI and GUI
│   ├── layout.py         the key layout, read from Dareu's device profile
│   ├── keymap.py         decodes what each key does, including the Fn layer
│   ├── vendor_tables.py  the firmware's own colour tables, for an honest preview
│   ├── settings.py       app preferences (language) — not device state
│   └── state.py          backup/restore persistence (plain JSON)
├── data/0101.json        Dareu's device profile — the GUI's key layout comes from here
└── gui/                  tkinter interface — never builds packets either
    ├── app.py            main window, sidebar, status line
    ├── controller.py     device work on a worker thread, results back on the Tk thread
    ├── keyboard_view.py  the keyboard drawing and the effect preview
    ├── widgets.py        effect grid, colour picker, sliders
    ├── theme.py          the dark theme
    ├── i18n.py           English and Portuguese strings, and the language switch
    └── pages/            one module per sidebar page
tests/
└── test_protocol.py      byte-match tests against packets confirmed on real hardware
tools/
└── run_tests.py          runs the same tests without pytest (core has zero deps)
packaging/                udev rule, install script
PROTOCOL.md               the full protocol write-up — read this before touching device.py
```

Layer rule, same as `open-m711pro`: `core/protocol.py` is pure logic and is
what the byte-match tests exercise; `core/device.py` is the only module that
touches the hardware; neither `cli.py` nor anything under `gui/` ever builds a
packet itself — both go through `core/lighting.py`.

## Protocol

Full write-up, including how it was recovered (decompiling Dareu's own public
web driver and, later, Husky's Windows application — not a USB capture) and
everything that is still unmapped, is in [PROTOCOL.md](PROTOCOL.md).
Summary:

HID **Feature Reports**, 64 bytes, no Report ID declared by the device (Linux
still needs a `0x00` prefix byte for the ioctl, so buffers here are 65 bytes),
sent via `ioctl(HIDIOCSFEATURE)`/read via `ioctl(HIDIOCGFEATURE)` on the one
`/dev/hidraw*` node (of five) that exposes this vendor interface.

```
byte 0  TargetId (0 = wired)          byte 4  Profile (1 = default)
byte 1  payload length                byte 5  (unused)
byte 2  command class (3 = Lighting)  byte 6+ payload
byte 3  subcommand | 0x80 (get) or | 0x00 (set)
```

Setting an effect: `region, effect, flag, speed, colour_count, [R,G,B]...` in
the payload. The device replies asynchronously — a command is sent, then
`GET_FEATURE` is polled until the status byte says "ready".

## Development

```bash
python3 -m pytest              # byte-match tests (if pytest is installed)
python3 tools/run_tests.py     # same tests without pytest
```

Same discipline as `open-m711pro`: **no packet is sent to the hardware unless
it has been replayed and visually confirmed, or read back from the device.**
Every builder in `protocol.py` has a byte-match test pinning it to a payload
that either produced a confirmed visual effect or matches a value read from
real hardware — see the docstrings in `tests/test_protocol.py` for which is
which; not everything there is a raw capture the way `open-m711pro`'s tests
are, because this protocol came from source code, not a `.pcapng`.

## Credits

The protocol is Dareu's own — recovered from their public web driver at
`dr.dareu.com`, and from Husky's Windows application where the web driver was
silent, rather than from USB traffic (compare `open-m711pro`, where no vendor
tool existed and everything came from capturing packets). No vendor file is
redistributed here and no vendor artwork is used: the keyboard this GUI draws
is built from the layout geometry in Dareu's own public device profile. The
Python port, the region-discovery sweep, and the hardware confirmation are this
repo's own work.

## License

[GPL-3.0](LICENSE).
