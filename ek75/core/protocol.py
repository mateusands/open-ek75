# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Mateus Andrade
"""Dareu TgDevice protocol — packet construction (pure logic, no I/O).

See PROTOCOL.md for the full write-up. Every builder here is testable by
byte-matching against packets confirmed on real hardware (tests/test_protocol.py).

The protocol was not captured from USB traffic (unlike open-m711pro's): it was
recovered by decompiling the OFFICIAL vendor web driver,
https://dr.dareu.com/js/device/tgdevice.js, which talks to this exact device
over WebHID. The constants and packet layout below are a direct, line-by-line
port of that file's `HidUsbDeviceBase` / `TgKeyboard` classes — not a guess.
"""

REPORT_SIZE = 64          # Feature Report payload size for this device family
TARGET_ID = 0x00          # wired connection, no dongle multiplexing

# --- header layout (tgdevice.js: DATA_INDEX) --------------------------------
HDR_STATUS = 0             # byte 0: TargetId on write; low nibble == 2 on a ready reply
HDR_SIZE = 1                # byte 1: length of the payload that follows HDR_PROFILE
HDR_CLASS = 2               # byte 2: CMD_CLASS
HDR_COMMAND = 3             # byte 3: command | GET_CMD or | SET_CMD
HDR_PROFILE = 4             # byte 4: profile id (1 = default profile)
PAYLOAD_BASE = 6            # byte 6: first payload byte (byte 5 is unused padding)

GET_CMD = 0x80
SET_CMD = 0x00

# --- command classes (tgdevice.js: CMD_CLASS) -------------------------------
CLASS_DEVICE = 0
CLASS_KEY = 1
CLASS_BUTTON = 2
CLASS_LIGHTING = 3
CLASS_SENSOR = 4
CLASS_PROFILE = 5
CLASS_MACRO = 6
CLASS_POWER = 7
CLASS_AUDIO = 8
CLASS_DFU = 9
CLASS_TEST = 10
CLASS_LCD = 11
CLASS_FLASH = 12
CLASS_MAGNETIC_AXIS = 13

# --- lighting subcommands (tgdevice.js: CLASS_LIGHTING_CMD_LIST) ------------
LED_CMD_ID_LIST = 0                    # list of valid RegionIds (multi-packet, unimplemented here)
LED_CMD_ATTRIBUTE = 1                  # per-region attributes (type, FPS, matrix, effect list)
LED_CMD_EFFECT = 2                     # effect + colour(s) + speed — what this module writes
LED_CMD_BRIGHTNESS = 3
LED_CMD_FRAME = 4
LED_CMD_CAL_DATA = 5
LED_CMD_CHARGE_CTRL = 6
LED_CMD_DPI_STAGE_INDICATOR_COLOR = 7
LED_CMD_CUSTOM = 8

# --- lighting effects (tgdevice.js/lighting.js: TG_LIGHT_EFFECT_INDEX) ------
# Only Static (1) and Breathing (2) have been confirmed on this hardware so
# far — see PROTOCOL.md. The rest are transcribed from the vendor driver
# and are UNTESTED here; they may need per-effect payload shapes not modeled
# by build_set_lighting_effect (e.g. per-frame data for the CustomFrame* ones).
EFFECT_OFF = 0
EFFECT_STATIC = 1              # confirmed: single colour, no animation
EFFECT_BREATHING = 2           # confirmed: single colour, pulses
EFFECT_NEON = 3
EFFECT_REACTIVE = 4
EFFECT_WAVE = 5
EFFECT_RAINDROP = 6
EFFECT_GATHER = 7
EFFECT_RIPPLE = 8
EFFECT_RUNNING_LIGHT = 9
EFFECT_ROTATE = 10
EFFECT_STARLIT = 11
EFFECT_HEATUP = 12
EFFECT_CUSTOM_FRAME_1 = 13
EFFECT_CUSTOM_FRAME_2 = 14
EFFECT_CUSTOM_FRAME_3 = 15
EFFECT_CUSTOM_FRAME_4 = 16
EFFECT_CUSTOM_FRAME_5 = 17
EFFECT_STREAMING_FRAME = 18
EFFECT_LAP = 19
EFFECT_RAINBOW_W = 20
EFFECT_LIGHT_WAVE = 21
EFFECT_STEADY_STREAM = 22
EFFECT_START_UP = 23
EFFECT_AREA_REACTIVE = 24
EFFECT_LINE_REACTIVE = 25
EFFECT_WATERFALL = 26
EFFECT_SCANNING = 27
EFFECT_HEARTBEAT = 28
EFFECT_FLUXAY = 29
EFFECT_HEART_BREATH = 30
EFFECT_MOON_BREATH = 31
EFFECT_STAR_BREATH = 32

EFFECT_NAMES = {
    EFFECT_OFF: "Off", EFFECT_STATIC: "Static", EFFECT_BREATHING: "Breathing",
    EFFECT_NEON: "Neon", EFFECT_REACTIVE: "Reactive", EFFECT_WAVE: "Wave",
    EFFECT_RAINDROP: "Raindrop", EFFECT_GATHER: "Gather", EFFECT_RIPPLE: "Ripple",
    EFFECT_RUNNING_LIGHT: "RunningLight", EFFECT_ROTATE: "Rotate",
    EFFECT_STARLIT: "Starlit", EFFECT_HEATUP: "Heatup",
    EFFECT_CUSTOM_FRAME_1: "CustomFrame1", EFFECT_CUSTOM_FRAME_2: "CustomFrame2",
    EFFECT_CUSTOM_FRAME_3: "CustomFrame3", EFFECT_CUSTOM_FRAME_4: "CustomFrame4",
    EFFECT_CUSTOM_FRAME_5: "CustomFrame5", EFFECT_STREAMING_FRAME: "StreamingFrame",
    EFFECT_LAP: "Lap", EFFECT_RAINBOW_W: "RainbowW", EFFECT_LIGHT_WAVE: "LightWave",
    EFFECT_STEADY_STREAM: "SteadyStream", EFFECT_START_UP: "StartUp",
    EFFECT_AREA_REACTIVE: "AreaReactive", EFFECT_LINE_REACTIVE: "LineReactive",
    EFFECT_WATERFALL: "Waterfall", EFFECT_SCANNING: "Scanning",
    EFFECT_HEARTBEAT: "Heartbeat", EFFECT_FLUXAY: "Fluxay",
    EFFECT_HEART_BREATH: "HeartBreath", EFFECT_MOON_BREATH: "MoonBreath",
    EFFECT_STAR_BREATH: "StarBreath",
}

# --- regions -----------------------------------------------------------------
# NOT in the vendor driver: the driver discovers valid RegionIds at runtime via
# LED_CMD_ID_LIST (unimplemented here — see PROTOCOL.md). These two were
# found by sweeping RegionId 0-7 with LED_CMD_EFFECT|GET_CMD against a real
# keyboard (a Husky HTG-series unit, PID 0101) and are specific to that model;
# a different PID sharing this protocol may number its regions differently.
REGION_KEYS = 1             # confirmed: the per-key matrix
REGION_SIDE_LIGHT = 4       # confirmed: the side light bar

# Per-region quirks observed on this hardware, not derivable from the protocol.
# The side light lights up under Static, but renders a fixed multi-colour
# pattern and ignores the ColorList entirely — checked with white and with pure
# red, both of which left it unchanged. Offering a colour picker there would be
# offering a control that does nothing.
COLOR_IGNORED = frozenset({(REGION_SIDE_LIGHT, EFFECT_STATIC)})


# Effects observed to take no colour of their own. Deliberately short: it lists
# only what this hardware was seen to do, not what a vendor method's *name*
# suggested.
#
# `Off` needs no colour by construction. `Neon` is here on evidence: cycling to
# it with the keyboard's own Fn+[ shortcut made the firmware return an empty
# ColorList for the region (seen through `open-ek75 watch`), i.e. the firmware
# cleared the colours itself.
#
# An earlier version of this file also listed Wave, RunningLight, Rotate,
# Heartbeat and Fluxay, ported from the Windows app's
# `PageLedTg.CheckSupportCustomColor`. That was a misreading, and the owner
# caught it: Wave plainly accepts both a fixed colour and RGB on real hardware.
# That method gates the app's *custom colour palette* UI — the saved swatches
# behind `SaveColorToDevice` / `GenerateCustomColorButton`, whose panels it
# masks — and not whether an effect honours a colour at all. The lesson is the
# ordinary one: a method name is a hint, not a specification, and a control
# hidden on a bad inference is worse than one left visible.
EFFECTS_WITHOUT_COLOR = frozenset({EFFECT_OFF, EFFECT_NEON})


def supports_color(effect):
    """False only where this hardware was observed to ignore the colour list."""
    return effect not in EFFECTS_WITHOUT_COLOR


def color_is_ignored(region_id, effect):
    """True where this hardware is known to disregard the colour list."""
    return (region_id, effect) in COLOR_IGNORED

DEFAULT_PROFILE_ID = 1

# --- Flag (byte 8) is the animation direction --------------------------------
# Recovered from the official Husky Windows application, not from the web
# driver (which names the field `flag` and never says what it is). See
# PROTOCOL.md, "A second vendor source". `PageLedRegionTg.SetLedDirection`
# passes the direction straight into SetLedEffect's `flag` argument, and
# `SetDirctionButtonState` shows the value is binary per axis, not a 0-3
# compass.
# CONFIRMED NEGATIVE on PID 0101: the firmware stores this byte (write 1, read
# back 1) but renders `Wave` left-to-right either way — tested with the rainbow
# form of the effect at full brightness, where the direction is unmistakable.
# Kept because the packet is right and a sibling PID may honour it; never
# present it to a user as working. See PROTOCOL.md.
DIRECTION_FORWARD = 0       # left-to-right, or top-to-bottom on a vertical effect
DIRECTION_REVERSE = 1

DIRECTION_HORIZONTAL = "horizontal"
DIRECTION_VERTICAL = "vertical"

# Which effects offer a direction, and along which axis — from the Windows
# app's `SetDirctionButtonState`, which hides the control entirely for anything
# not listed here. Effects 130 and 141 appear in that method too but are
# outside TG_LIGHT_EFFECT_INDEX (0-32) and are not explained anywhere this
# project has looked; they are recorded rather than guessed at.
EFFECT_DIRECTION_AXIS = {
    EFFECT_WAVE: DIRECTION_HORIZONTAL,
    141: DIRECTION_HORIZONTAL,
    130: DIRECTION_VERTICAL,
}


def direction_axis(effect):
    """The axis an effect's direction runs along, or None if it has no direction."""
    return EFFECT_DIRECTION_AXIS.get(effect)


# --- colour list --------------------------------------------------------------
# The Windows app's TgUsbHidDevice.SetLedEffect refuses to send more than five:
#     n = colorList.Count / 3;  if (n > 5) return 0;
# The web driver has no such check, but the app is the one that ships against
# this firmware, so this is treated as the real limit.
MAX_COLORS = 5


# --- how many colours an effect actually uses --------------------------------
# From `OEMDriver.Pages.PageLedTg::CheckCustomColorCount` in the vendor's Windows
# app, which reduces to: effects 1, 4, 9, 20, 21, 22 and 132 take one colour;
# Starlit (11) and Breathing (2) take more; everything else takes one. The Ws, Qf
# and Jm pages carry the identical method, so it is a framework-wide rule.
#
# It agrees with what this keyboard was seen doing, three times over: Static one
# colour, Wave one colour (the table's default branch), Breathing cycling red,
# green and blue in order, one per breath. The table was found after those
# observations rather than used to predict them.
#
# Each number is the largest one something can vouch for, and they do not come
# from the same place:
#
#   Breathing  3  watched on this keyboard cycling red, green, blue in order.
#                 The vendor's UI caps it at 2; the firmware plainly does more,
#                 so the 2 is the application's limit. 4 and 5 are NOT offered:
#                 the wire allows them and nobody has seen them, and offering a
#                 slot that may do nothing is the thing this project does not do.
#   Starlit    2  the vendor's number, and nothing else. Nobody has looked at
#                 this effect on hardware. It got MAX_COLORS in an earlier draft
#                 purely by sharing a branch with Breathing in the vendor's
#                 table, which is not evidence about Starlit at all.
#   everything 1  the table's default branch, and what Static and Wave were
#                 seen doing.
COLORS_PER_EFFECT = {
    EFFECT_BREATHING: 3,
    EFFECT_STARLIT: 2,
}


def max_colors_for(effect):
    """How many colours this effect will actually show. See PROTOCOL.md.

    Never more than something can vouch for: an unclassified effect gets 1,
    which is the answer that cannot mislead.
    """
    return min(COLORS_PER_EFFECT.get(effect, 1), MAX_COLORS)



# --- speed --------------------------------------------------------------------
# Not 0-255. The official software's speed slider is declared Minimum="1"
# Maximum="3" in its own XAML (PageLedRegionTg's compiled BAML), matching the
# three labels the UI shows: slow / normal / fast. Its code also rewrites a
# stored 0 to 2 before displaying it, i.e. "normal" is the middle of a
# three-position control, not a midpoint of 255.
SPEED_MIN = 1
SPEED_NORMAL = 2
SPEED_MAX = 3

# Which effects have a speed at all — from the Windows app's
# SetLedParamControllerState, which disables the slider for anything not here.
# Ids above 32 in that method (130-134, 136-138) are outside
# TG_LIGHT_EFFECT_INDEX and are left out; see EFFECT_DIRECTION_AXIS's note.
EFFECTS_WITH_SPEED = frozenset({
    EFFECT_BREATHING, EFFECT_NEON, EFFECT_REACTIVE, EFFECT_WAVE,
    EFFECT_RUNNING_LIGHT, EFFECT_ROTATE, EFFECT_STARLIT, EFFECT_LAP,
    EFFECT_RAINBOW_W, EFFECT_LIGHT_WAVE, EFFECT_STEADY_STREAM,
    EFFECT_AREA_REACTIVE, EFFECT_LINE_REACTIVE, EFFECT_WATERFALL,
    EFFECT_SCANNING, EFFECT_HEARTBEAT, EFFECT_FLUXAY,
})


def has_speed(effect):
    return effect in EFFECTS_WITH_SPEED


# --- brightness ---------------------------------------------------------------
# The wire carries a raw byte; the official software's slider is declared
# Minimum="1" Maximum="100" in its XAML and filled with
#     sliderBrightness.Value = (int)(Brightness / 255f * sliderBrightness.Maximum)
# so the two are the same number in different units. This model's factory
# default is Brightness=120 in the vendor's own DefaultProfile.xml, which the
# official UI therefore shows as 47 — and 120 is also exactly what this project
# read back from real hardware for region 1.
BRIGHTNESS_MAX = 255


def brightness_to_percent(value):
    """Raw brightness byte -> the 0-100 the official software shows."""
    return int(round(value * 100.0 / BRIGHTNESS_MAX))


def brightness_from_percent(percent):
    """0-100 -> the raw byte to put on the wire."""
    percent = max(0, min(100, percent))
    return int(round(percent * BRIGHTNESS_MAX / 100.0))


def _new_packet():
    return bytearray(REPORT_SIZE)


def build_set_lighting_effect(region_id, effect, colors, flag=0, speed=0,
                               profile_id=DEFAULT_PROFILE_ID):
    """LED_CMD_EFFECT|SET_CMD — apply an effect (and colour list) to a region.

    `colors` is a list of (r, g, b) tuples, at most MAX_COLORS of them, and the
    count goes in byte PAYLOAD_BASE+4.

    **How many of them get drawn depends on the effect** — `max_colors_for()`
    is the rule, and PROTOCOL.md's "The colour list is used by some effects,
    over time" is the evidence. `Breathing` cycles the whole list, one colour
    per breath; `Static` and `Wave` draw `colors[0]` and ignore the rest.

    This builder does not apply that rule. It puts on the wire exactly what it
    is handed, capped at MAX_COLORS, because the packet is the vendor's format
    and a sibling PID may spend the list differently. Deciding how many to
    offer belongs to the caller.

    `flag` is the animation direction (DIRECTION_FORWARD/DIRECTION_REVERSE) for
    the effects that have one — see EFFECT_DIRECTION_AXIS. It is 0 for
    everything else, which is what both vendor implementations send.

    Ported from tgdevice.js `SetLightingEffect`; the same byte layout was then
    found independently in the official Husky Windows application
    (`TgUsbHidDevice.SetLedEffect`), which is where `flag`'s meaning and the
    five-colour limit come from.
    """
    if len(colors) > MAX_COLORS:
        raise ValueError(
            f"at most {MAX_COLORS} colours per effect "
            f"(the vendor's Windows app refuses more) — got {len(colors)}")
    pkt = _new_packet()
    pkt[HDR_STATUS] = TARGET_ID
    pkt[HDR_SIZE] = 5 + 3 * len(colors)
    pkt[HDR_CLASS] = CLASS_LIGHTING
    pkt[HDR_COMMAND] = LED_CMD_EFFECT | SET_CMD
    pkt[HDR_PROFILE] = profile_id
    pkt[PAYLOAD_BASE + 0] = region_id
    pkt[PAYLOAD_BASE + 1] = effect
    pkt[PAYLOAD_BASE + 2] = flag
    pkt[PAYLOAD_BASE + 3] = speed
    pkt[PAYLOAD_BASE + 4] = len(colors)
    for i, (r, g, b) in enumerate(colors):
        pkt[PAYLOAD_BASE + 5 + 3 * i + 0] = r & 0xFF
        pkt[PAYLOAD_BASE + 5 + 3 * i + 1] = g & 0xFF
        pkt[PAYLOAD_BASE + 5 + 3 * i + 2] = b & 0xFF
    return bytes(pkt)


def build_get_lighting_effect(region_id, profile_id=DEFAULT_PROFILE_ID):
    """LED_CMD_EFFECT|GET_CMD — request the current effect/colour of a region."""
    pkt = _new_packet()
    pkt[HDR_STATUS] = TARGET_ID
    pkt[HDR_SIZE] = 1
    pkt[HDR_CLASS] = CLASS_LIGHTING
    pkt[HDR_COMMAND] = LED_CMD_EFFECT | GET_CMD
    pkt[HDR_PROFILE] = profile_id
    pkt[PAYLOAD_BASE] = region_id
    return bytes(pkt)


def parse_lighting_effect_response(resp):
    """Decode a reply to build_get_lighting_effect into a dict."""
    ncolor = resp[PAYLOAD_BASE + 4]
    colors = [
        tuple(resp[PAYLOAD_BASE + 5 + 3 * i: PAYLOAD_BASE + 5 + 3 * i + 3])
        for i in range(ncolor)
    ]
    return {
        "effect": resp[PAYLOAD_BASE + 1],
        "flag": resp[PAYLOAD_BASE + 2],
        "speed": resp[PAYLOAD_BASE + 3],
        "colors": colors,
    }


def build_get_lighting_brightness(region_id, profile_id=DEFAULT_PROFILE_ID):
    """LED_CMD_BRIGHTNESS|GET_CMD — request the current brightness of a region."""
    pkt = _new_packet()
    pkt[HDR_STATUS] = TARGET_ID
    pkt[HDR_SIZE] = 2
    pkt[HDR_CLASS] = CLASS_LIGHTING
    pkt[HDR_COMMAND] = LED_CMD_BRIGHTNESS | GET_CMD
    pkt[HDR_PROFILE] = profile_id
    pkt[PAYLOAD_BASE] = region_id
    return bytes(pkt)


def parse_lighting_brightness_response(resp):
    return resp[PAYLOAD_BASE + 1]


def is_response_ready(resp):
    """True once a reply's status nibble signals the command completed.

    Port of tgdevice.js `CommandProcess`'s retry condition: `2 == (15 & status)`.
    The device does not answer synchronously — the caller must poll
    GET_FEATURE a few times after SET_FEATURE until this returns True.
    """
    return (resp[HDR_STATUS] & 0x0F) == 2


# --- LED_CMD_FRAME (4) — per-key colour, streamed from here ------------------
# Recovered from the Windows app, not from the web driver: `tgdevice.js` names
# LED_CMD_FRAME in its enum and never sends it. See PROTOCOL.md, "LED_CMD_FRAME".
#
# Sixteen LEDs per packet, which is `TgUsbHidDevice.BLOCK_SIZE` read out of its
# constructor. A seventeenth would still fit in the report (5 + 3*17 = 56 bytes
# against 58 available) and would still be wrong — the kind of limit nothing
# downstream would catch, so it is enforced here.
LED_FRAME_BLOCK = 16
# The flags byte is 0x00 on every packet but the last, which is 0x80. Nothing
# else is accepted: the firmware was asked for 0x00, 0x01, 0x02, 0x40, 0x80,
# 0x81, 0xC0 and 0xFF, and answered only the first and the fifth.
#
# The IL appeared to start this byte at 1 and OR in 0x80 on the last packet,
# which would make 0x01/0x81. The keyboard refused both. That initial `1` is
# something else in the decompiled method — the return value, most likely —
# and this is the one place in this file where the hardware corrected a reading
# of the vendor's binary rather than confirming it.
LED_FRAME_FLAG_LAST = 0x80


def build_set_led_frame(region_id, colors, frame=0, first_led=0,
                        last_frame=True):
    """LED_CMD_FRAME|SET_CMD — one packet of a streamed frame.

    `colors` is up to LED_FRAME_BLOCK (r, g, b) tuples, in LED order —
    `vendor_tables.KEY_MATRIX` is what that order means on region 1.

    HDR_SIZE is 6 + 3n where the payload is 5 + 3n bytes. That is what
    `SetLedFrame` writes; `build_set_lighting_effect` uses 5 + 3n for its own
    five payload bytes, so the vendor's two commands disagree by one.
    Transcribed rather than reconciled — a "fix" here would be inventing a byte
    the firmware may well be counting.

    **Accepted by this keyboard and not yet doing what it says.** Frames are
    acknowledged and the firmware visibly reacts to each one, but sixteen red
    LEDs at index 0 light the whole keyboard blue — and sixteen blue ones light
    it the same blue, which rules out a byte-order swap and a one-byte offset
    alike. `first_led`/`last_led` are accepted at every value 0..89 without
    changing anything. Something has to happen before a frame means what it
    says; see PROTOCOL.md, "What the hardware said when it was sent".
    """
    colors = [tuple(c) for c in colors]
    if not colors:
        raise ValueError("a frame packet needs at least one colour")
    if len(colors) > LED_FRAME_BLOCK:
        raise ValueError(f"at most {LED_FRAME_BLOCK} LEDs per packet, "
                         f"got {len(colors)}")
    if not isinstance(frame, int) or frame < 0 or frame > 255:
        raise ValueError(f"frame must be 0..255, got {frame!r}")

    pkt = _new_packet()
    pkt[HDR_STATUS] = TARGET_ID
    pkt[HDR_SIZE] = 6 + 3 * len(colors)
    pkt[HDR_CLASS] = CLASS_LIGHTING
    pkt[HDR_COMMAND] = LED_CMD_FRAME | SET_CMD
    pkt[PAYLOAD_BASE + 0] = _byte("region_id", region_id)
    pkt[PAYLOAD_BASE + 1] = LED_FRAME_FLAG_LAST if last_frame else 0
    pkt[PAYLOAD_BASE + 2] = frame
    pkt[PAYLOAD_BASE + 3] = _byte("first_led", first_led)
    pkt[PAYLOAD_BASE + 4] = _byte("last_led", first_led + len(colors) - 1)
    for i, (r, g, b) in enumerate(colors):
        base = PAYLOAD_BASE + 5 + 3 * i
        pkt[base + 0] = _byte(f"colors[{i}].r", r)
        pkt[base + 1] = _byte(f"colors[{i}].g", g)
        pkt[base + 2] = _byte(f"colors[{i}].b", b)
    return bytes(pkt)


def build_save_custom_led(profile_id=DEFAULT_PROFILE_ID):
    """LED_CMD_CUSTOM|SET_CMD — persist what was streamed.

    Port of `TgUsbHidDevice::SaveCustomLed`. There is a second method of that
    name, `TgDevice::SaveCustomLed`, which sends nothing and writes a file on
    the PC; this is the one that reaches the keyboard.

    NOT CONFIRMED ON HARDWARE, and note this keyboard does not list effects
    13-17 (CustomFrame1..5) in either region — so there may be no slot here for
    a saved pattern to live in, and streaming to effect 18 may be the only path
    this model has.
    """
    pkt = _new_packet()
    pkt[HDR_STATUS] = TARGET_ID
    pkt[HDR_SIZE] = 2
    pkt[HDR_CLASS] = CLASS_LIGHTING
    pkt[HDR_COMMAND] = LED_CMD_CUSTOM | SET_CMD
    pkt[HDR_PROFILE] = _byte("profile_id", profile_id)
    return bytes(pkt)



# --- multi-packet transfers (tgdevice.js: GetMultiPacketCmd) -----------------
# Some replies do not fit in one 64-byte report (the RegionId list, the profile
# list, macro data). The vendor driver handles them in two steps: a probe that
# returns the total byte count, then N chunked reads of at most MULTIPACKET_BLOCK
# bytes each. `width` is how many bytes encode Total/Offset in the chunk request
# (1 for every command this repo uses; the driver supports up to 4).
MULTIPACKET_BLOCK = 48         # tgdevice.js: TG_BLOCK_SIZE


def build_multipacket_probe(profile_id, cmd_class, command, args=b""):
    """First step of GetMultiPacketCmd: ask how many bytes the reply will be."""
    pkt = _new_packet()
    pkt[HDR_STATUS] = TARGET_ID
    pkt[HDR_SIZE] = 1
    pkt[HDR_CLASS] = cmd_class
    pkt[HDR_COMMAND] = command | GET_CMD
    pkt[HDR_PROFILE] = profile_id
    for i, byte in enumerate(args):
        pkt[PAYLOAD_BASE + i] = byte
    return bytes(pkt)


def parse_multipacket_total(resp, nargs=0, width=1):
    """Total byte count from a probe reply — big-endian over `width` bytes."""
    total = 0
    for i in range(width):
        total = (total << 8) | resp[PAYLOAD_BASE + nargs + i]
    return total


def build_multipacket_chunk(profile_id, cmd_class, command, total, offset,
                             chunk_len, args=b"", width=1):
    """Second step: request `chunk_len` bytes of the reply starting at `offset`.

    The Total and Offset fields sit right after the command's own arguments,
    each `width` bytes big-endian, and HDR_SIZE covers chunk + args + 2*width.
    """
    pkt = _new_packet()
    pkt[HDR_STATUS] = TARGET_ID
    pkt[HDR_CLASS] = cmd_class
    pkt[HDR_COMMAND] = command | GET_CMD
    pkt[HDR_PROFILE] = profile_id
    for i, byte in enumerate(args):
        pkt[PAYLOAD_BASE + i] = byte
    base = PAYLOAD_BASE + len(args)
    for i in range(width):
        shift = 8 * (width - 1 - i)
        pkt[base + i] = (total >> shift) & 0xFF
        pkt[base + width + i] = (offset >> shift) & 0xFF
    pkt[HDR_SIZE] = chunk_len + len(args) + 2 * width
    return bytes(pkt)


def multipacket_chunk_offset(nargs=0, width=1):
    """Where a chunk reply's data starts inside the 64-byte report."""
    return PAYLOAD_BASE + nargs + 2 * width


# --- LED_CMD_ID_LIST / LED_CMD_ATTRIBUTE (both read-only) -------------------

def build_get_led_region_id_list_probe(profile_id=0):
    """Port of tgdevice.js `GetLedRegionIdList` — a GetMultiPacketCmd probe.

    The vendor driver passes ProfileId 0 here, not the active profile.

    CONFIRMED ON HARDWARE: returns [1, 4] on this keyboard, matching both the
    original brute-force sweep and the vendor's own DefaultProfile.xml.
    """
    return build_multipacket_probe(profile_id, CLASS_LIGHTING, LED_CMD_ID_LIST)


def parse_led_region_id_list(data):
    """Port of GetLedRegionIdList's own filtering of the assembled byte array.

    Verbatim from the driver: RegionIds 0 and 1 are collapsed into whichever of
    the two appears first, every other id is kept as-is. The reason is not
    documented in the JS; it is reproduced rather than second-guessed.
    """
    regions = []
    for value in data:
        if value in (0, 1):
            if any(r in (0, 1) for r in regions):
                continue
        regions.append(value)
    return regions


def build_get_led_region_attribute(region_id):
    """LED_CMD_ATTRIBUTE|GET_CMD — a region's type, FPS, matrix and effect list.

    Port of tgdevice.js `GetLedRegionAttribute`. Note it leaves HDR_PROFILE at
    0, because the driver does not set it for this command. It is not the only
    builder here that sends profile 0 — `build_get_led_region_id_list_probe`
    does too, and so does `build_get_battery_status` — but each has its own
    reason, and none of them inherits `DEFAULT_PROFILE_ID`.
    """
    pkt = _new_packet()
    pkt[HDR_STATUS] = TARGET_ID
    pkt[HDR_SIZE] = 1
    pkt[HDR_CLASS] = CLASS_LIGHTING
    pkt[HDR_COMMAND] = LED_CMD_ATTRIBUTE | GET_CMD
    pkt[PAYLOAD_BASE] = region_id
    return bytes(pkt)


def parse_led_region_attribute_response(resp):
    """Decode a LED_CMD_ATTRIBUTE reply.

    `effects` applies the driver's own filter (it drops 13-18, the CustomFrame
    and StreamingFrame effects, which need a per-frame payload this repo does
    not implement); `effects_raw` is what the firmware actually listed.
    """
    count = resp[PAYLOAD_BASE + 5]
    raw = [resp[PAYLOAD_BASE + 6 + i] for i in range(count)]
    return {
        "type": resp[PAYLOAD_BASE + 1],
        "fps": resp[PAYLOAD_BASE + 2],
        "matrix": (resp[PAYLOAD_BASE + 3], resp[PAYLOAD_BASE + 4]),
        "effects": [e for e in raw if e < 13 or e > 18],
        "effects_raw": raw,
    }


# --- LED_CMD_BRIGHTNESS (write) ---------------------------------------------

def build_set_lighting_brightness(region_id, brightness,
                                   profile_id=DEFAULT_PROFILE_ID):
    """LED_CMD_BRIGHTNESS|SET_CMD — port of tgdevice.js `SetLightingBrightness`.

    Not yet written to a real keyboard from this code, but the byte layout is
    corroborated by two independent vendor implementations: tgdevice.js's
    `SetLightingBrightness` and the Windows app's `TgUsbHidDevice.SetLedBrigtness`
    agree byte for byte. The scale is settled too — see BRIGHTNESS_MAX.
    """
    pkt = _new_packet()
    pkt[HDR_STATUS] = TARGET_ID
    pkt[HDR_SIZE] = 2
    pkt[HDR_CLASS] = CLASS_LIGHTING
    pkt[HDR_COMMAND] = LED_CMD_BRIGHTNESS | SET_CMD
    pkt[HDR_PROFILE] = profile_id
    pkt[PAYLOAD_BASE + 0] = region_id
    pkt[PAYLOAD_BASE + 1] = brightness & 0xFF
    return bytes(pkt)


# --- CLASS_POWER subcommands (tgdevice.js: CLASS_POWER_CMD_LIST) -------------
PWR_CMD_BAT_STATUS = 0                 # implemented (read)
PWR_CMD_TIME_2_DIM = 1                 # this keyboard does not answer it
PWR_CMD_TIME_2_SLEEP = 2               # implemented (read)
PWR_CMD_LOW_INDICATOR_CTRL = 3
PWR_CMD_MAX_LED_BRIGHTNESS = 4
PWR_CMD_ADC = 5
PWR_CMD_USB_TIME_2_SLEEP = 6           # reads Control=0 while on the cable

# The official software's sleep slider runs 3-30 and TK51G0101.dll declares
# MinSleepTime=3.0 / MaxSleepTime=30.0. The wire carries SECONDS: this keyboard
# returned 180, which is those 3 minutes. Minutes in a UI, seconds on the wire.
SLEEP_MIN_MINUTES = 3
SLEEP_MAX_MINUTES = 30


def build_get_battery_status():
    """PWR_CMD_BAT_STATUS|GET_CMD — port of tgdevice.js `GetBatteryStatus`.

    Takes no profile: the vendor driver writes HDR_STATUS, HDR_SIZE, HDR_CLASS
    and HDR_COMMAND and stops, leaving HDR_PROFILE at 0. Charge is a property of
    the keyboard, not of a profile, so there is nothing to pass.

    Confirmed on hardware: this keyboard answered Status=1, Level=100,
    MaxLevel=100, Critical=0 while plugged in.
    """
    pkt = _new_packet()
    pkt[HDR_STATUS] = TARGET_ID
    pkt[HDR_SIZE] = 3
    pkt[HDR_CLASS] = CLASS_POWER
    pkt[HDR_COMMAND] = PWR_CMD_BAT_STATUS | GET_CMD
    return bytes(pkt)


def parse_battery_status_response(resp):
    """Decode a PWR_CMD_BAT_STATUS reply.

    `percent` is derived, not sent: the firmware reports Level out of MaxLevel,
    and dividing by an assumed 100 would misreport any device that uses a
    coarser scale. None when MaxLevel is 0 — unknown beats a wrong number.

    `status` and `critical` are passed through as the raw bytes. Their value
    sets are not documented anywhere this project has seen; naming them here
    would be inventing a meaning rather than reporting one.
    """
    level = resp[PAYLOAD_BASE + 1]
    max_level = resp[PAYLOAD_BASE + 2]
    return {
        "status": resp[PAYLOAD_BASE + 0],
        "level": level,
        "max_level": max_level,
        "critical": resp[PAYLOAD_BASE + 3],
        "percent": round(level * 100 / max_level) if max_level else None,
    }


def build_get_time_to_sleep(profile_id=DEFAULT_PROFILE_ID):
    """PWR_CMD_TIME_2_SLEEP|GET_CMD — port of tgdevice.js `GetTimeToSleep`.

    Carries the profile, unlike the battery read: the vendor driver sets
    `D[HDR_PROFILE] = A.ProfileId`, so the idle timeout is stored per profile.

    Confirmed on hardware: profile 1 answered Control=1, Second=180.
    """
    pkt = _new_packet()
    pkt[HDR_STATUS] = TARGET_ID
    pkt[HDR_SIZE] = 3
    pkt[HDR_CLASS] = CLASS_POWER
    pkt[HDR_COMMAND] = PWR_CMD_TIME_2_SLEEP | GET_CMD
    pkt[HDR_PROFILE] = profile_id
    return bytes(pkt)


def parse_time_to_sleep_response(resp):
    """Decode a PWR_CMD_TIME_2_SLEEP reply.

    Verbatim from the vendor driver: when Control is 0 the timer is off and the
    two seconds bytes are not read at all — reading them anyway would report a
    timeout for a device that has none.
    """
    enabled = resp[PAYLOAD_BASE] != 0
    seconds = (resp[PAYLOAD_BASE + 1] << 8 | resp[PAYLOAD_BASE + 2]) if enabled else 0
    return {
        "enabled": enabled,
        "seconds": seconds,
        "minutes": round(seconds / 60),
    }


# --- CLASS_KEY subcommands (tgdevice.js: CLASS_KEY_CMD_LIST) ----------------
KEY_CMD_ID_LIST = 0
KEY_CMD_ATTRIBUTE = 1
KEY_CMD_DEBOUNCE = 2
KEY_CMD_ASSIGN = 3                     # implemented (read)
KEY_CMD_ANALOG_ACTUATION_POINT = 4
KEY_CMD_FN_LOCK = 5
KEY_WIN_LOCK_MAC_STATUS = 6
KEY_PERFORMACE = 7
KEY_CMD_BULK_ASSIGN = 8                # not used — see PROTOCOL.md
KEY_CMD_SOCD_STATUS = 9

LAYER_BASE = 0
LAYER_FN = 1


def build_get_key_assign(key_id, layer, profile_id=DEFAULT_PROFILE_ID):
    """KEY_CMD_ASSIGN|GET_CMD — what one key does on one layer.

    Port of tgdevice.js `GetKeyAssign`. `layer` is LAYER_BASE or LAYER_FN;
    those numbers are the vendor driver's, and reading both back from this
    keyboard matched the profile's `default-function-*` and
    `default-fn-function-*` fields, which is what identifies which is which.

    Confirmed on hardware: all 83 keys answered on both layers.
    """
    pkt = _new_packet()
    pkt[HDR_STATUS] = TARGET_ID
    pkt[HDR_SIZE] = 8
    pkt[HDR_CLASS] = CLASS_KEY
    pkt[HDR_COMMAND] = KEY_CMD_ASSIGN | GET_CMD
    pkt[HDR_PROFILE] = profile_id
    pkt[PAYLOAD_BASE + 0] = key_id
    pkt[PAYLOAD_BASE + 1] = layer
    return bytes(pkt)


def _byte(name, value):
    """Reject anything that would be truncated on its way into a packet byte."""
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{name} must be an int, got {value!r}")
    if not 0 <= value <= 255:
        raise ValueError(f"{name} must be 0..255, got {value}")
    return value


def build_set_key_assign(key_id, layer, function_id, data,
                         profile_id=DEFAULT_PROFILE_ID):
    """KEY_CMD_ASSIGN|SET_CMD — port of tgdevice.js `SetKeyAssign`.

    The header is byte-identical to `build_get_key_assign`, which is confirmed
    on hardware for all 166 assignments; only the command byte and three extra
    payload bytes differ. Payload offsets [0] and [1] — keyId and layer — are
    therefore already proven to address the right key. [2] and [3..7] are not.

    **This writes the keyboard's persistent key map.** Every argument is
    bounds-checked rather than trusted: a five-byte `data` that arrives with
    four would put a zero where the keyboard expects a modifier, and a `key_id`
    outside 0..255 would be truncated into addressing a *different key* than
    the caller named. Neither failure announces itself — `HIDIOCSFEATURE`
    succeeds either way.

    The way back is `Fn`+`Esc`, the factory reset this firmware binds itself
    (function id 44, read from the live key map). It runs on the keyboard and
    needs nothing from this code — which `restore` cannot claim, since restore
    is this same command. See PROTOCOL.md's `SetKeyAssign` section.
    """
    if layer not in (LAYER_BASE, LAYER_FN):
        raise ValueError(f"layer must be LAYER_BASE or LAYER_FN, got {layer!r}")
    data = list(data)
    if len(data) != 5:
        raise ValueError(f"data must be exactly 5 bytes, got {len(data)}")

    pkt = _new_packet()
    pkt[HDR_STATUS] = TARGET_ID
    pkt[HDR_SIZE] = 8
    pkt[HDR_CLASS] = CLASS_KEY
    pkt[HDR_COMMAND] = KEY_CMD_ASSIGN | SET_CMD
    pkt[HDR_PROFILE] = _byte("profile_id", profile_id)
    pkt[PAYLOAD_BASE + 0] = _byte("key_id", key_id)
    pkt[PAYLOAD_BASE + 1] = layer
    pkt[PAYLOAD_BASE + 2] = _byte("function_id", function_id)
    for i, value in enumerate(data):
        pkt[PAYLOAD_BASE + 3 + i] = _byte(f"data[{i}]", value)
    return bytes(pkt)


def parse_key_assign_response(resp):
    """Decode a KEY_CMD_ASSIGN reply into the same shape the device profile uses.

    `data` is five bytes whose meaning depends on `function_id` — see
    core/keymap.py, which is the only place that interprets them.
    """
    return {
        "function_id": resp[PAYLOAD_BASE + 2],
        "data": list(resp[PAYLOAD_BASE + 3:PAYLOAD_BASE + 8]),
    }



# --- CLASS_PROFILE subcommands (tgdevice.js: CLASS_PROFILE_CMD_LIST) --------
PFL_CMD_ID_LIST = 0                    # implemented (read)
PFL_CMD_CREATE = 1                     # write, persistent, untested undo
PFL_CMD_DELETE = 2                     # the undo for CREATE, itself untested
PFL_CMD_ACTIVE = 3                     # implemented (read); the SET is not
PFL_CMD_NAME = 4                       # no GetProfileName found in the source
PFL_CMD_RESET = 5                      # write, destroys a profile's contents


def build_get_profile_id_list_probe(profile_id=0):
    """Port of tgdevice.js `GetProfileIdList` — a GetMultiPacketCmd probe.

    The vendor passes ProfileId 0, the same as `GetLedRegionIdList`: asking the
    keyboard which profiles exist is not a question about one of them.

    Only the probe is built here. `device.get_multipacket` derives the chunk
    requests from the same (profile_id, class, command) triple, which is why
    this is named `_probe` and its LED sibling is too.

    CONFIRMED ON HARDWARE: returns [1] on this keyboard — one profile, which is
    also the active one. The vendor's Windows app offers Profile 1/2/3; the
    other two have to be created with PFL_CMD_CREATE, which this project does
    not send.
    """
    return build_multipacket_probe(profile_id, CLASS_PROFILE, PFL_CMD_ID_LIST)


def parse_profile_id_list(data):
    """The assembled byte array *is* the list — no filtering, deliberately.

    `GetProfileIdList` ends with `ProfileList = new Uint8Array(DataArray)` and
    nothing else. Its sibling `parse_led_region_id_list` collapses ids 0 and 1;
    that is the LED list's own quirk and copying it here would silently swallow
    a profile. The two are tested against one shared input so the difference is
    asserted rather than trusted to this comment.

    This function exists for the layer rule rather than for the work: callers in
    `lighting.py` must not unpack raw bytes themselves.
    """
    return list(data)


def build_get_active_profile():
    """PFL_CMD_ACTIVE|GET_CMD — port of tgdevice.js `GetActiveProfileId`.

    Writes HDR_STATUS, HDR_CLASS and HDR_COMMAND, leaving **both** HDR_SIZE and
    HDR_PROFILE at 0. Neither zero is incidental: the request carries no payload
    for HDR_SIZE to describe, and asking *which* profile is active cannot take a
    profile id as its input.

    The zero profile byte is shared with `build_get_battery_status`; the zero
    size is not — that one sets HDR_SIZE=3. Half a resemblance.

    Confirmed on hardware: this keyboard accepted the packet and replied ready
    with `02 00 05 83 01 00 01 00...`, reporting profile 1 as active. That
    confirms the *request*. It does not confirm where the answer lives — see
    `parse_active_profile_response`, which this unit cannot discriminate.
    """
    pkt = _new_packet()
    pkt[HDR_STATUS] = TARGET_ID
    pkt[HDR_SIZE] = 0
    pkt[HDR_CLASS] = CLASS_PROFILE
    pkt[HDR_COMMAND] = PFL_CMD_ACTIVE | GET_CMD
    return bytes(pkt)


def parse_active_profile_response(resp):
    """The active profile id, read from the reply's **header**.

    `A.ProfileId = A.Data[DATA_INDEX.HDR_PROFILE]` — byte 4, where the request
    would have carried a profile id had it sent one. Every other parser in this
    module reads from PAYLOAD_BASE, so this is the one place where following a
    sibling's shape yields the wrong byte.

    Read on hardware, the reply was `02 00 05 83 01 00 01 00...`: this keyboard
    puts the id in byte 4 **and** byte 6, so it cannot tell the two readings
    apart. The vendor driver is the only reason to prefer the header, and that
    is enough — but do not record this as "the header was confirmed". It was
    not; this unit simply agrees either way, and a sibling model with only one
    of the two filled in is what would decide it.
    """
    return resp[HDR_PROFILE]


# --- CLASS_MACRO subcommands (tgdevice.js: CLASS_MACRO_CMD_LIST) ------------
MCO_CMD_SOTRAGE_INFO = 0               # declared by the vendor, never sent [sic]
MCO_CMD_ID_LIST = 1                    # implemented (read)
MCO_CMD_CREATE = 2                     # write, persistent
MCO_CMD_DELETE = 3                     # write, persistent
MCO_CMD_NAME = 4                       # the vendor reads it and discards it
MCO_CMD_MEMORY = 5                     # implemented (read); the SET is not
MCO_CMD_MINI_DELAY = 6                 # declared by the vendor, never sent


def build_get_macro_id_list_probe(profile_id=0):
    """Port of tgdevice.js `GetMacroIdList` — a GetMultiPacketCmd probe.

    ProfileId 0, like the LED and profile id lists: which macros exist is not a
    question about one profile.
    """
    return build_multipacket_probe(profile_id, CLASS_MACRO, MCO_CMD_ID_LIST)


def parse_macro_id_list(data):
    """Drop every zero — `DataArray.filter(A => 0 !== A)`, verbatim.

    The third id list over this transport and the third post-processing rule.
    `parse_led_region_id_list` collapses ids 0 and 1; `parse_profile_id_list`
    filters nothing at all; this one drops zeros. A test asserts all three
    disagree on one shared input, because the temptation to write any of them by
    analogy with its neighbour is exactly what that test exists to defeat.
    """
    return [value for value in data if value != 0]


def build_get_macro_data_probe(macro_id, profile_id=0):
    """Port of `GetMacroData` — `GetMultiPacketCmd(0, CLASS_MACRO, 5|GET,
    [macroId], out, 2)`.

    First command here to pass GetMultiPacketCmd an argument, and the only one
    so far to use a two-byte length: a macro's data can exceed the 255 bytes a
    single-byte Total could describe. The id sits at PAYLOAD_BASE and the
    Total/Offset pairs the chunk requests add come after it — see
    `build_multipacket_chunk`, which already takes `args` and `width`.

    CONFIRMED ON HARDWARE, which the plan for this slice predicted it would not
    be: it assumed a keyboard with no macros would leave the combination
    untestable. This unit reports one macro and returned its 27 bytes, so the
    argument-plus-two-byte-length path is exercised end to end rather than only
    by the byte-match tests.
    """
    return build_multipacket_probe(profile_id, CLASS_MACRO, MCO_CMD_MEMORY,
                                   args=bytes([_byte("macro_id", macro_id)]))
