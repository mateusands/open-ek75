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

    `colors` is a list of (r, g, b) tuples, at most MAX_COLORS of them. Static
    and Breathing take exactly one; multi-colour effects (untested here) may
    take more — the wire format supports it (byte PAYLOAD_BASE+4 is the colour
    count).

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


def parse_key_assign_response(resp):
    """Decode a KEY_CMD_ASSIGN reply into the same shape the device profile uses.

    `data` is five bytes whose meaning depends on `function_id` — see
    core/keymap.py, which is the only place that interprets them.
    """
    return {
        "function_id": resp[PAYLOAD_BASE + 2],
        "data": list(resp[PAYLOAD_BASE + 3:PAYLOAD_BASE + 8]),
    }

