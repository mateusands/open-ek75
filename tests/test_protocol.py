# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Mateus Andrade
"""Byte-match tests: every packet builder against a payload confirmed on real
hardware (a Husky HTG-series unit, PID 0101). No packet ships without one of
these — see PROTOCOL.md and CLAUDE.md.
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ek75.core import protocol


def _padded(prefix_bytes):
    """A 64-byte packet: the given leading bytes, zero-padded to REPORT_SIZE."""
    pkt = bytearray(protocol.REPORT_SIZE)
    pkt[:len(prefix_bytes)] = prefix_bytes
    return bytes(pkt)


def test_set_static_red_region1():
    """Confirmed live on hardware: keyboard matrix turned solid red."""
    expected = _padded(bytes.fromhex("0008030201000101000001ff0000"))
    got = protocol.build_set_lighting_effect(
        region_id=1, effect=protocol.EFFECT_STATIC, colors=[(255, 0, 0)])
    assert got == expected


def test_set_static_cyan_region4():
    """The packet this repo sends for region 4 Static, pinned byte for byte.

    CORRECTED: an earlier version of this docstring said the side light "turned
    solid cyan-ish blue". That claim did not survive re-testing. The side light
    *does* light under Static, but it renders a fixed multi-colour pattern and
    ignores the colour list — verified by sending pure white and then pure red,
    neither of which changed it (see PROTOCOL.md, "The side light ignores the
    colour under Static").

    What this test still pins is real and worth keeping: the byte layout the
    firmware accepts and acknowledges for this command. It is no longer
    presented as evidence about what the LEDs show.
    """
    expected = _padded(bytes.fromhex("000803020100040100000100c8ff"))
    got = protocol.build_set_lighting_effect(
        region_id=4, effect=protocol.EFFECT_STATIC, colors=[(0, 200, 255)])
    assert got == expected


def test_get_lighting_effect_region1():
    """Read request for region 1.

    Not byte-matched against a raw capture (unlike the writes above): the
    request layout is deduced from the same DATA_INDEX/CMD_CLASS fields the
    writes confirm, ported directly from tgdevice.js. What IS confirmed live
    on hardware is the round trip this packet is part of: sending it and
    reading the reply back returned the exact state written by
    test_set_static_red_region1 (see PROTOCOL.md, "Reading the state
    back"). This test only pins the byte layout so a future edit cannot
    silently change it.
    """
    expected = _padded(bytes.fromhex("00010382010001"))
    got = protocol.build_get_lighting_effect(region_id=1)
    assert got == expected


def test_parse_lighting_effect_response_matches_hardware_reading():
    """Response fields as actually read back live for region 1, right after
    test_set_static_red_region1's packet was sent to real hardware: Effect=1
    (Static), Flag=0, Speed=0, one colour (255, 0, 0). This exact tuple is
    what the keyboard returned — see PROTOCOL.md.
    """
    resp = _padded(bytes.fromhex("02" + "0803020100" + "01" + "01000001ff0000"))
    # HDR_STATUS low nibble == 2 marks a ready reply (see is_response_ready).
    info = protocol.parse_lighting_effect_response(resp)
    assert info["effect"] == protocol.EFFECT_STATIC
    assert info["flag"] == 0
    assert info["speed"] == 0
    assert info["colors"] == [(255, 0, 0)]


def test_is_response_ready():
    ready = bytearray(protocol.REPORT_SIZE)
    ready[protocol.HDR_STATUS] = 0x02
    assert protocol.is_response_ready(bytes(ready))

    not_ready = bytearray(protocol.REPORT_SIZE)
    not_ready[protocol.HDR_STATUS] = 0x00
    assert not protocol.is_response_ready(bytes(not_ready))


def test_effect_names_cover_every_defined_constant():
    """Catches a forgotten entry when a new EFFECT_* constant is added."""
    defined = {v for k, v in vars(protocol).items()
               if k.startswith("EFFECT_") and isinstance(v, int)}
    assert defined == set(protocol.EFFECT_NAMES)


# --- ported from tgdevice.js, NOT yet replayed on hardware -------------------
# The tests below pin builders whose byte layout is a line-by-line port of the
# vendor driver. Unlike the two Static writes above, no packet here has been
# sent to a real keyboard yet, so these tests prove "we transcribed the driver
# correctly", not "the hardware accepted this". Where a command is read-only
# that distinction is cheap to close; the brightness *write* is the one to be
# careful with. See PROTOCOL.md.

def test_set_lighting_brightness_region1():
    """Port of tgdevice.js SetLightingBrightness. UNCONFIRMED on hardware.

    HDR_SIZE=2, LED_CMD_BRIGHTNESS(3)|SET_CMD(0x00), profile 1, payload
    RegionId then Brightness.
    """
    expected = _padded(bytes.fromhex("0002030301000178"))
    got = protocol.build_set_lighting_brightness(region_id=1, brightness=120)
    assert got == expected


def test_get_led_region_attribute_region1():
    """Port of tgdevice.js GetLedRegionAttribute — read-only.

    Note HDR_PROFILE (byte 4) stays 0: the vendor driver does not set it for
    this command, unlike every other lighting command. Transcribed, not
    captured.
    """
    expected = _padded(bytes.fromhex("00010381000001"))
    got = protocol.build_get_led_region_attribute(region_id=1)
    assert got == expected


def test_parse_led_region_attribute_response():
    """The driver drops effects 13-18 (CustomFrame1-5, StreamingFrame) from the
    list it shows the user, because those need per-frame payloads. `effects_raw`
    keeps what the firmware actually reported so nothing is silently lost.
    """
    # 6 header bytes (status=ready), then the payload: RegionId echo, Type=1,
    # FPS=30, Matrix=(6,16), effect count=4, effects 1, 2, 13, 20.
    resp = _padded(bytes.fromhex("02" + "00030100" + "00"
                                 + "01"          # PAYLOAD_BASE+0  RegionId echo
                                 + "01"          # +1  Type
                                 + "1e"          # +2  FPS
                                 + "0610"        # +3,+4  Matrix
                                 + "04"          # +5  effect count
                                 + "01020d14"))  # +6..  effects
    info = protocol.parse_led_region_attribute_response(resp)
    assert info["type"] == 1
    assert info["fps"] == 30
    assert info["matrix"] == (6, 16)
    assert info["effects_raw"] == [1, 2, 13, 20]
    assert info["effects"] == [1, 2, 20]


def test_get_led_region_id_list_probe():
    """Port of tgdevice.js GetLedRegionIdList's GetMultiPacketCmd probe.

    Read-only. ProfileId is 0 here, which is what the driver passes — not the
    active profile.
    """
    expected = _padded(bytes.fromhex("0001038000"))
    got = protocol.build_get_led_region_id_list_probe()
    assert got == expected


def test_multipacket_chunk_layout():
    """Port of GetMultiPacketCmd's chunk request: Total then Offset (1 byte each
    at width=1) right after the command's own arguments, HDR_SIZE covering
    chunk + args + 2*width.
    """
    got = protocol.build_multipacket_chunk(
        profile_id=0, cmd_class=protocol.CLASS_LIGHTING,
        command=protocol.LED_CMD_ID_LIST, total=2, offset=0, chunk_len=2)
    expected = _padded(bytes.fromhex("0004038000" + "00" + "0200"))
    assert got == expected
    assert protocol.multipacket_chunk_offset() == protocol.PAYLOAD_BASE + 2


def test_parse_led_region_id_list_collapses_0_and_1():
    """Verbatim port of the driver's own filter: ids 0 and 1 collapse to
    whichever appears first; every other id is kept. Reproduced rather than
    second-guessed — the JS gives no reason for it.
    """
    assert protocol.parse_led_region_id_list(bytes([1, 4])) == [1, 4]
    assert protocol.parse_led_region_id_list(bytes([0, 1, 4])) == [0, 4]
    assert protocol.parse_led_region_id_list(bytes([1, 0, 4, 5])) == [1, 4, 5]


def test_parse_multipacket_total_width():
    resp = _padded(bytes.fromhex("02" + "0000000000" + "0102"))
    assert protocol.parse_multipacket_total(resp, nargs=0, width=1) == 1
    assert protocol.parse_multipacket_total(resp, nargs=0, width=2) == 0x0102


# --- recovered from the official Husky Windows application -------------------
# A second, independent vendor implementation of the same protocol (see
# PROTOCOL.md, "A second vendor source"). Where it agrees with the web
# driver, confidence in a byte layout goes up; where it says something the web
# driver never did — what `flag` means, the colour-count limit, the brightness
# scale — that is new information, and these tests pin it.

def test_set_lighting_effect_direction_goes_in_flag():
    """`Flag` (byte 8) is the animation direction.

    From the Windows app's PageLedRegionTg.SetLedDirection, which passes the
    direction argument straight into SetLedEffect's `flag` parameter, and from
    TgUsbHidDevice.SetLedEffect, which writes that parameter to buffer index 9
    — index 0 there being the HID report-number byte, so it is byte 8 of the
    64-byte packet, exactly where this project already put `flag`.

    Not replayed on hardware: this pins the transcription, not the behaviour.
    """
    forward = protocol.build_set_lighting_effect(
        region_id=1, effect=protocol.EFFECT_WAVE, colors=[(255, 0, 0)],
        flag=protocol.DIRECTION_FORWARD)
    reverse = protocol.build_set_lighting_effect(
        region_id=1, effect=protocol.EFFECT_WAVE, colors=[(255, 0, 0)],
        flag=protocol.DIRECTION_REVERSE)
    assert forward[protocol.PAYLOAD_BASE + 2] == 0
    assert reverse[protocol.PAYLOAD_BASE + 2] == 1
    # Nothing else moves: direction is one byte, not a different packet.
    assert forward[:protocol.PAYLOAD_BASE + 2] == reverse[:protocol.PAYLOAD_BASE + 2]
    assert forward[protocol.PAYLOAD_BASE + 3:] == reverse[protocol.PAYLOAD_BASE + 3:]


def test_direction_axis_matches_the_windows_app():
    """SetDirctionButtonState enables left/right for effect 5, up/down for 130,
    and hides the control for everything else.
    """
    assert protocol.direction_axis(protocol.EFFECT_WAVE) == protocol.DIRECTION_HORIZONTAL
    assert protocol.direction_axis(130) == protocol.DIRECTION_VERTICAL
    for effect in (protocol.EFFECT_STATIC, protocol.EFFECT_BREATHING,
                   protocol.EFFECT_STARLIT, protocol.EFFECT_OFF):
        assert protocol.direction_axis(effect) is None


def test_colour_list_is_capped_at_five():
    """TgUsbHidDevice.SetLedEffect: `if (colorList.Count / 3 > 5) return 0;`

    The web driver has no such check. The app is what ships against this
    firmware, so the builder refuses rather than sending a packet the vendor's
    own software would not.
    """
    five = [(1, 2, 3)] * protocol.MAX_COLORS
    pkt = protocol.build_set_lighting_effect(1, protocol.EFFECT_STATIC, five)
    assert pkt[protocol.HDR_SIZE] == 5 + 3 * 5
    assert pkt[protocol.PAYLOAD_BASE + 4] == 5

    try:
        protocol.build_set_lighting_effect(1, protocol.EFFECT_STATIC, five + [(4, 5, 6)])
    except ValueError:
        pass
    else:
        raise AssertionError("six colours should be refused")


def test_brightness_percent_matches_the_official_slider():
    """The vendor's DefaultProfile.xml for this exact model ships
    Brightness=120 for region 1 and 70 for region 4 — the same two values this
    project read back from real hardware. The official UI shows 120 as "47",
    which is 120/255 as a percentage; that is the whole mapping.
    """
    assert protocol.brightness_to_percent(120) == 47
    assert protocol.brightness_from_percent(47) == 120
    assert protocol.brightness_to_percent(0) == 0
    assert protocol.brightness_to_percent(255) == 100
    assert protocol.brightness_from_percent(100) == 255
    # Out-of-range input is clamped, not wrapped into a wrong byte.
    assert protocol.brightness_from_percent(150) == 255
    assert protocol.brightness_from_percent(-10) == 0


def test_vendor_default_profile_round_trips():
    """The two regions of the vendor's own DefaultProfile.xml, rebuilt.

    RegionId 1: effect 5 (Wave), flag 0, speed 0, no colours.
    RegionId 4: effect 2 (Breathing), flag 0, speed 0, white.
    This is the factory state this project independently read off the hardware,
    so it doubles as a check that the builder produces what the keyboard ships
    with.
    """
    keys = protocol.build_set_lighting_effect(
        region_id=1, effect=protocol.EFFECT_WAVE, colors=[], flag=0, speed=0)
    assert keys == _padded(bytes.fromhex("000503020100010500000000"))

    side = protocol.build_set_lighting_effect(
        region_id=4, effect=protocol.EFFECT_BREATHING, colors=[(255, 255, 255)],
        flag=0, speed=0)
    assert side == _padded(bytes.fromhex("0008030201000402000001ffffff"))


# --- values read back from real hardware -------------------------------------
# The strongest kind of evidence this project has: not a transcription of vendor
# code, but what the keyboard itself answered. Captured with `open-ek75 probe`
# against a Husky HTG-series unit (PID 0101).

def test_parse_region1_attribute_as_read_from_hardware():
    """Region 1's real LED_CMD_ATTRIBUTE reply: Type=4, FPS=33, Matrix 6x15,
    19 effects of which 18 survive the driver's 13-18 filter.

    Note what is NOT in the list: effect 0 (Off). The key matrix does not
    advertise it, while region 4 does — see PROTOCOL.md.
    """
    raw = [1, 2, 5, 11, 4, 9, 6, 3, 10, 20, 21, 22, 26, 24, 25, 27, 28, 29, 18]
    payload = bytes([1, 4, 33, 6, 15, len(raw)]) + bytes(raw)
    resp = _padded(bytes.fromhex("02" + "0003" + "8100" + "00") + payload)

    info = protocol.parse_led_region_attribute_response(resp)
    assert info["type"] == 4
    assert info["fps"] == 33
    assert info["matrix"] == (6, 15)
    assert info["effects_raw"] == raw
    assert len(info["effects"]) == 18
    assert protocol.EFFECT_STREAMING_FRAME not in info["effects"]
    assert protocol.EFFECT_OFF not in info["effects"]
    # The order is the official software's grid order — do not sort it.
    assert info["effects"][:4] == [protocol.EFFECT_STATIC, protocol.EFFECT_BREATHING,
                                    protocol.EFFECT_WAVE, protocol.EFFECT_STARLIT]


def test_parse_region4_attribute_as_read_from_hardware():
    """Region 4's real reply: a 1x16 strip that supports only Off, Static and
    Breathing — which is why the device profile's CustomEffectList for it is
    empty, and why the side light gets three tiles and not eighteen.
    """
    raw = [0, 2, 1, 18]
    payload = bytes([4, 4, 33, 1, 16, len(raw)]) + bytes(raw)
    resp = _padded(bytes.fromhex("02" + "0003" + "8100" + "00") + payload)

    info = protocol.parse_led_region_attribute_response(resp)
    assert info["matrix"] == (1, 16)
    assert info["effects"] == [protocol.EFFECT_OFF, protocol.EFFECT_BREATHING,
                               protocol.EFFECT_STATIC]


def test_device_profile_effect_list_disagrees_with_the_firmware():
    """A regression guard for a real trap.

    `0101.json`'s CustomEffectList is the web UI's curated menu, not the
    firmware's capability list, and the two genuinely differ: the hardware
    supports four effects the JSON omits and lacks one the JSON offers. Code
    that treats the profile as authoritative would hide working effects and
    offer a broken one, so this pins the difference rather than letting someone
    "simplify" the runtime query away.
    """
    from ek75.core import layout

    from_profile = set(layout.load().custom_effect_list(0))
    from_firmware = {1, 2, 5, 11, 4, 9, 6, 3, 10, 20, 21, 22, 26, 24, 25, 27, 28, 29}

    assert from_firmware - from_profile == {
        protocol.EFFECT_NEON, protocol.EFFECT_ROTATE,
        protocol.EFFECT_WATERFALL, protocol.EFFECT_FLUXAY,
    }
    assert from_profile - from_firmware == {protocol.EFFECT_LAP}


def test_restore_writes_brightness_too():
    """Regression: `restore` used to re-apply the effect and silently skip the
    brightness, so a region restored after an `off` came back at whatever
    brightness it was left at — dim enough to look like the restore had failed.

    The snapshot records brightness (state.py), so the way back has to send it.
    Exercised against a fake session rather than hardware: what is being pinned
    is that restore issues the brightness write at all.
    """
    from ek75.core import lighting

    class FakeSession(lighting.Session):
        def __init__(self):
            self.effects = []
            self.brightnesses = []

        def set_effect(self, region_id, effect, colors, flag=0, speed=0):
            self.effects.append((region_id, effect, colors, flag, speed))
            return True

        def set_brightness(self, region_id, brightness):
            self.brightnesses.append((region_id, brightness))
            return True

    session = FakeSession()
    result = session.restore({
        4: {"effect": protocol.EFFECT_STATIC, "colors": [(0, 200, 255)],
            "flag": 0, "speed": 0, "brightness": 70},
    })

    assert session.effects == [(4, protocol.EFFECT_STATIC, [(0, 200, 255)], 0, 0)]
    assert session.brightnesses == [(4, 70)]
    assert result == [(4, True)]


def test_restore_without_a_recorded_brightness_still_works():
    """Older backup files have no brightness field; restore must not crash or
    invent one.
    """
    from ek75.core import lighting

    class FakeSession(lighting.Session):
        def __init__(self):
            self.brightnesses = []

        def set_effect(self, *a, **k):
            return True

        def set_brightness(self, region_id, brightness):
            self.brightnesses.append((region_id, brightness))
            return True

    session = FakeSession()
    assert session.restore({1: {"effect": 1, "colors": [(1, 2, 3)]}}) == [(1, True)]
    assert session.brightnesses == []


def test_vendor_colour_tables_match_the_hardware_they_describe():
    """The two colour tables lifted out of the vendor's TK51G0101.dll.

    Read from the constructor's IL, where each entry is a literal
    Color.FromRgb(r, g, b). Pinned here because they are transcribed data: a
    typo in one would silently make the preview wrong in a way no other test
    would catch.
    """
    from ek75.core import vendor_tables

    # One colour per LED of the side light, whose LED_CMD_ATTRIBUTE reply
    # reports a 1x16 matrix — read off the hardware, independently.
    assert len(vendor_tables.SIDE_LIGHT_FIXED) == 16
    assert vendor_tables.SIDE_LIGHT_FIXED[0] == (0, 0, 255)
    assert vendor_tables.SIDE_LIGHT_FIXED[3] == (255, 200, 16)
    assert vendor_tables.SIDE_LIGHT_FIXED[-1] == (0, 0, 255)

    # The animated ramp: 24 steps, deliberately uneven.
    assert len(vendor_tables.WAVE_COLORS) == 24
    assert vendor_tables.WAVE_COLORS[0] == (255, 0, 0)
    assert vendor_tables.WAVE_COLORS[12] == (0, 255, 255)
    assert vendor_tables.wave_color(0.0) == (255.0, 0.0, 0.0)
    # Wraps rather than clamping, so a sweep never stalls at the end.
    assert vendor_tables.wave_color(1.0) == vendor_tables.wave_color(0.0)


def test_only_observed_effects_are_marked_colourless():
    """Regression guard for a wrong inference that shipped and was caught.

    `EFFECTS_WITHOUT_COLOR` once held seven effects, ported from the Windows
    app's `CheckSupportCustomColor`. That method gates the app's saved-swatch
    palette UI, not whether an effect honours a colour, and the result was a
    GUI that hid the colour picker on `Wave` — which accepts a colour perfectly
    well on real hardware.

    So this test pins the *shortness* of the list as much as its contents: only
    effects actually observed to ignore a colour belong here.
    """
    assert not protocol.supports_color(protocol.EFFECT_OFF)
    assert not protocol.supports_color(protocol.EFFECT_NEON)

    for effect in (protocol.EFFECT_STATIC, protocol.EFFECT_BREATHING,
                   protocol.EFFECT_WAVE, protocol.EFFECT_RUNNING_LIGHT,
                   protocol.EFFECT_ROTATE, protocol.EFFECT_HEARTBEAT,
                   protocol.EFFECT_FLUXAY, protocol.EFFECT_WATERFALL,
                   protocol.EFFECT_STARLIT, protocol.EFFECT_SCANNING):
        assert protocol.supports_color(effect), effect


def test_fn_layer_decodes_to_the_shortcuts_printed_nowhere():
    """The Fn layer as decoded from the DEVICE PROFILE (`0101.json`).

    CORRECTED: this docstring used to say "Fn+I really is Print Screen on this
    keyboard". It tests no such thing — it decodes the vendor's JSON, and the
    keyboard was later measured disagreeing with that JSON on 23 assignments.
    `Fn`+`Space` below is one of them: the profile says "cycle brightness", the
    keyboard says Space. The assertion stays because decoding the profile
    correctly is still worth pinning; the claim about hardware does not.

    What the keyboard actually reports is covered by the CLASS_KEY tests and by
    `open-ek75 keys --diff`. See PROTOCOL.md.
    """
    from ek75.core import keymap, layout

    profile = layout.load()
    shortcuts = dict(keymap.fn_shortcuts(profile))

    assert shortcuts["I"] == ("Print Screen", "Print Screen")
    assert shortcuts["K"] == ("Home", "Home")
    assert shortcuts["L"] == ("End", "End")
    assert shortcuts["F7"] == ("Play / Pause", "Play / Pausar")
    assert shortcuts["F11"] == ("Mute", "Mudo")
    # NOT what the keyboard does — see the docstring. This pins the decoder.
    assert shortcuts["Space"] == ("Cycle brightness", "Trocar brilho")

    # Pass-throughs must not be listed: Fn+Tab is still Tab, and 11 such keys
    # would bury the 38 real shortcuts.
    assert "Tab" not in shortcuts
    assert "Enter" not in shortcuts
    assert len(shortcuts) < len(profile.keys)


def test_media_keys_decode_from_a_two_byte_consumer_usage():
    """MediaKeys (function id 8) stores a Consumer-page usage split across the
    first two data bytes: usage = (data[0] << 8) | data[1]. F1's [1, 148] is
    0x194, "My computer" — which is what the key does.
    """
    from ek75.core import keymap, layout

    f1 = next(k for k in layout.load().keys if k.label == "F1")
    assert f1.fn_function_id == 8
    assert f1.fn_function_data[:2] == [1, 148]
    assert keymap.describe_fn(f1) == ("My computer", "Meu computador")


# --- app settings, kept apart from device state ------------------------------

def test_settings_survive_a_round_trip_and_ignore_junk():
    """Preferences persist, and a corrupt or hostile file cannot break startup.

    `settings.py` is deliberately forgiving: refusing to launch because a
    preferences file got truncated would be a worse failure than ignoring it.
    """
    import tempfile
    from ek75.core import settings

    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "settings.json")

        assert settings.load(path) == settings.DEFAULTS
        assert settings.DEFAULTS["language"] == "en"   # English is the default

        settings.update(path, language="pt")
        assert settings.load(path)["language"] == "pt"

        # Unknown keys are dropped rather than stored and handed back later.
        settings.save({"language": "pt", "trojan": "x"}, path)
        assert "trojan" not in settings.load(path)

        with open(path, "w") as f:
            f.write("{not json")
        assert settings.load(path) == settings.DEFAULTS

        assert settings.load(os.path.join(tmp, "absent.json")) == settings.DEFAULTS


# --- CLASS_POWER, read-only --------------------------------------------------
# Both builders are transcribed from tgdevice.js and both were then exercised
# against the real keyboard, so the replies below are values the device actually
# returned — the strongest tier this project has short of a visual confirmation,
# which does not apply to a read.

def test_get_battery_status_writes_no_profile():
    """GetBatteryStatus: HDR_SIZE=3, CLASS_POWER(7), PWR_CMD_BAT_STATUS(0)|GET.

    It takes no profile argument because the vendor driver writes none —
    tgdevice.js's `GetBatteryStatus` sets HDR_STATUS, HDR_SIZE, HDR_CLASS and
    HDR_COMMAND and stops, leaving HDR_PROFILE at 0. Battery is a property of
    the keyboard, not of a profile.
    """
    expected = _padded(bytes.fromhex("000307800000"))
    assert protocol.build_get_battery_status() == expected


def test_parse_battery_status_as_read_from_hardware():
    """The reply this keyboard actually returned, plugged in and full:
    Status=1, Level=100, MaxLevel=100, Critical=0.
    """
    resp = _padded(bytes.fromhex("02" + "0407" + "8000" + "00" + "01646400"))
    info = protocol.parse_battery_status_response(resp)
    assert info["status"] == 1
    assert info["level"] == 100
    assert info["max_level"] == 100
    assert info["critical"] == 0
    assert info["percent"] == 100


def test_battery_percent_is_scaled_by_max_level_not_assumed_to_be_100():
    """MaxLevel is a field, so the percentage divides by it. A device reporting
    Level=3 of MaxLevel=4 is at 75%, not 3%.
    """
    resp = _padded(bytes.fromhex("02" + "0407" + "8000" + "00" + "01030400"))
    assert protocol.parse_battery_status_response(resp)["percent"] == 75

    # MaxLevel 0 must not divide by zero — the percentage is simply unknown.
    resp = _padded(bytes.fromhex("02" + "0407" + "8000" + "00" + "01000000"))
    assert protocol.parse_battery_status_response(resp)["percent"] is None


def test_get_time_to_sleep_carries_the_profile():
    """GetTimeToSleep: HDR_SIZE=3, CLASS_POWER(7), PWR_CMD_TIME_2_SLEEP(2)|GET,
    HDR_PROFILE set — unlike the battery read, the sleep timer is per profile,
    which is what tgdevice.js's `D[HDR_PROFILE] = A.ProfileId` says.
    """
    expected = _padded(bytes.fromhex("000307820100"))
    assert protocol.build_get_time_to_sleep() == expected           # profile 1 default
    assert protocol.build_get_time_to_sleep(profile_id=1) == expected


def test_parse_time_to_sleep_as_read_from_hardware():
    """What this keyboard returned for profile 1: Control=1, Second=180.

    180 s is 3 minutes, which is exactly MinSleepTime in the vendor's
    TK51G0101.dll — the wire is in seconds and the official slider is in
    minutes. See PROTOCOL.md.
    """
    resp = _padded(bytes.fromhex("02" + "0307" + "8201" + "00" + "0100b4"))
    info = protocol.parse_time_to_sleep_response(resp)
    assert info["enabled"] is True
    assert info["seconds"] == 180
    assert info["minutes"] == 3


def test_time_to_sleep_disabled_reports_no_time():
    """Control==0 means the timer is off, and the vendor driver then reports
    Second as 0 without reading the two bytes. USB_TIME_2_SLEEP came back this
    way on the cable.
    """
    resp = _padded(bytes.fromhex("02" + "0307" + "8201" + "00" + "00ffff"))
    info = protocol.parse_time_to_sleep_response(resp)
    assert info["enabled"] is False
    assert info["seconds"] == 0
    assert info["minutes"] == 0


# --- CLASS_KEY, read-only ----------------------------------------------------

def test_get_key_assign_layout():
    """GetKeyAssign: HDR_SIZE=8, CLASS_KEY(1), KEY_CMD_ASSIGN(3)|GET, profile in
    the header, then keyId and layer as the first two payload bytes.

    Transcribed from tgdevice.js. Layer 0 is the base map, 1 is the Fn layer —
    confirmed by reading both from the keyboard and matching them against the
    vendor profile's `default-function-*` and `default-fn-function-*` fields.
    """
    assert protocol.build_get_key_assign(1, 0) == _padded(
        bytes.fromhex("0008018301000100"))
    assert protocol.build_get_key_assign(1, 1) == _padded(
        bytes.fromhex("0008018301000101"))
    # KeyIDs are not a 1..83 range: this keyboard's run to 172 with gaps.
    assert protocol.build_get_key_assign(172, 1) == _padded(
        bytes.fromhex("000801830100ac01"))


def test_parse_key_assign_as_read_from_hardware():
    """Esc on the base layer, exactly as this keyboard replied: FunctionId 6
    (a plain key) with HID usage 41, which is Escape.
    """
    resp = _padded(bytes.fromhex("02" + "0801830100" + "01" + "00"
                                 + "06" + "0029000000"))
    info = protocol.parse_key_assign_response(resp)
    assert info["function_id"] == 6
    assert info["data"] == [0, 41, 0, 0, 0]


def test_hid_keys_covers_every_usage_this_keyboard_emits():
    """The base layer is mostly letters and digits, and the Fn-layer decoder
    dropped those on purpose as noise. Reused unchanged for the base layer it
    would leave 66 of 79 keys undescribed, so the table has to be complete.

    This asserts against the keyboard's own profile rather than a hand-written
    list, so a future device that emits a usage nobody thought of fails here.
    """
    from ek75.core import keymap, layout

    used = set()
    for key in layout.load().keys:
        for fid, data in ((key.function_id, key.function_data),
                          (key.fn_function_id, key.fn_function_data)):
            if fid == 6 and data[1]:
                used.add(data[1])

    missing = sorted(u for u in used if u not in keymap.HID_KEYS)
    assert not missing, f"usages with no label: {missing}"


def test_describe_takes_raw_values_so_the_rule_exists_once():
    """`describe_fn` decoded a Key's stored JSON fields; live data arrives as a
    (function_id, data) pair with no Key around it. One decoder answers both, or
    the rule drifts between them.
    """
    from ek75.core import keymap

    assert keymap.describe(6, [0, 41, 0, 0, 0]) == ("Esc", "Esc")
    assert keymap.describe(6, [0, 4, 0, 0, 0]) == ("A", "A")
    assert keymap.describe(6, [0, 70, 0, 0, 0]) == ("Print Screen", "Print Screen")
    assert keymap.describe(8, [1, 148, 0, 0, 0]) == ("My computer", "Meu computador")
    assert keymap.describe(54, [1, 0, 0, 0, 0])[0] == "Cycle brightness"

    # This line used to assert `is None` for a bare modifier. That was the old
    # behaviour, and it was wrong rather than merely terse: see
    # test_a_modifier_is_part_of_the_assignment_not_noise below. The filtering
    # it stood for now lives in `is_bare_modifier`, where the shortcut lists
    # that actually want it can ask for it.
    assert keymap.describe(6, [2, 0, 0, 0, 0]) == ("Left Shift", "Shift esquerdo")
    assert keymap.is_bare_modifier(6, [2, 0, 0, 0, 0]) is True


def test_a_modifier_is_part_of_the_assignment_not_noise():
    """`data[0]` is the HID modifier bitmask and dropping it reports a wrong key.

    `describe` read only `data[1]`, the usage. For a key assigned Ctrl+C the
    reply is `[0x01, 0x06, ...]` and the old code called that "C" — not an
    incomplete answer but a false one, in the command whose entire purpose is
    telling the user what a key does.

    Two independent sources agree on the bitmask, neither of them this code:

    1. The USB HID boot-keyboard report's modifier byte, bit 0 through bit 7 =
       LCtrl LShift LAlt LGUI RCtrl RShift RAlt RGUI.
    2. This keyboard, read live over KEY_CMD_ASSIGN. Its eight modifier keys
       answered on the base layer with exactly those single-bit values:
       L-Ctrl 1, L-Shift 2, L-Alt 4, L-Win 8, R-Ctrl 16, R-Shift 32, R-Alt 64.
       (No key on this model carries bit 7, Right GUI.)
    """
    from ek75.core import keymap

    # Source 2, transcribed from the live read, key label -> data[0].
    measured = {"L-Ctrl": 1, "L-Shift": 2, "L-Alt": 4, "L-Win": 8,
                "R-Ctrl": 16, "R-Shift": 32, "R-Alt": 64}
    expected_en = {"L-Ctrl": "Left Ctrl", "L-Shift": "Left Shift",
                   "L-Alt": "Left Alt", "L-Win": "Left Win",
                   "R-Ctrl": "Right Ctrl", "R-Shift": "Right Shift",
                   "R-Alt": "Right Alt"}
    for label, bit in measured.items():
        described = keymap.describe(6, [bit, 0, 0, 0, 0])
        assert described is not None, f"{label} (data[0]={bit}) went undescribed"
        assert described[0] == expected_en[label]
        assert keymap.is_bare_modifier(6, [bit, 0, 0, 0, 0]) is True

    # The defect this test exists for: a modifier combined with a usage.
    assert keymap.describe(6, [0x01, 0x06, 0, 0, 0]) == ("Left Ctrl + C",
                                                         "Ctrl esquerdo + C")
    assert keymap.is_bare_modifier(6, [0x01, 0x06, 0, 0, 0]) is False

    # Several at once, in bit order regardless of how they were set.
    assert keymap.describe(6, [0x03, 0x06, 0, 0, 0])[0] == "Left Ctrl + Left Shift + C"

    # Bit 7 has no key on this model but the decoder must not silently drop it.
    assert keymap.describe(6, [0x80, 0, 0, 0, 0])[0] == "Right Win"

    # Neither a modifier nor a usage is genuinely nothing.
    assert keymap.describe(6, [0, 0, 0, 0, 0]) is None


def test_function_id_47_is_named_because_the_keyboard_emits_it():
    """`Fn`+`L-Win` answers with function id 47, which had no name.

    It surfaced the way these always will: reading the live base and Fn layers
    and looking for rows that fell through to the raw `fid=NN` fallback. The
    vendor's index in `docs/vendor-reference/device.js` calls 47 `LockWin`,
    sitting between `ShowBatteryLevel` (46) and `LightingSpeed` (48) — both
    already in the table, which is what makes the identification an id lookup
    in a list this project already trusts rather than an inference.

    The device profile does not carry this assignment, so no profile-driven
    test could have caught it; only the keyboard knows.
    """
    from ek75.core import keymap

    assert keymap.describe(47, [2, 0, 0, 0, 0]) == ("Lock the Windows key",
                                                     "Travar a tecla Windows")


def test_set_key_assign_layout():
    """Port of tgdevice.js `SetKeyAssign(profileId, keyId, layer, fid, data[5])`.

    Byte-identical to the confirmed `GetKeyAssign` header, with SET_CMD instead
    of GET_CMD and three more payload bytes. Expected bytes composed by hand
    from the vendor source, not by running the builder:

      00 status | 08 size | 01 class | 03 cmd (3 | SET=0) | 01 profile | 00 pad
      32 keyId(50) | 01 layer(Fn) | 06 functionId | 00 2f 00 00 00 data

    The value used is the real one this keyboard stores for `Fn`+`[` — plain
    `[`, HID usage 0x2f — because that is the assignment the hardware round
    trip in PROTOCOL.md actually writes.
    """
    expected = _padded(bytes.fromhex("000801030100" + "320106" + "002f000000"))
    got = protocol.build_set_key_assign(
        key_id=50, layer=protocol.LAYER_FN, function_id=6,
        data=[0, 0x2F, 0, 0, 0], profile_id=1)
    assert got == expected

    # Same header as the GET that is already confirmed on hardware, except for
    # the command byte and the size. If these ever diverge, one of them is wrong.
    get = protocol.build_get_key_assign(50, protocol.LAYER_FN, profile_id=1)
    assert got[protocol.HDR_CLASS] == get[protocol.HDR_CLASS]
    assert got[protocol.HDR_PROFILE] == get[protocol.HDR_PROFILE]
    assert got[protocol.HDR_SIZE] == get[protocol.HDR_SIZE] == 8
    assert got[protocol.HDR_COMMAND] == protocol.KEY_CMD_ASSIGN | protocol.SET_CMD
    assert get[protocol.HDR_COMMAND] == protocol.KEY_CMD_ASSIGN | protocol.GET_CMD


def test_set_key_assign_refuses_anything_it_cannot_put_on_the_wire():
    """Every input is bounds-checked, because this one writes persistent memory.

    A four-byte `data` is the dangerous case: it would silently send a zero
    where the keyboard expects the fifth byte, and nothing downstream would
    notice. An out-of-range `key_id` is worse — truncated into a byte it would
    address a *different key*, changing something the caller never named.
    """
    ok = dict(key_id=50, layer=protocol.LAYER_FN, function_id=6,
              data=[0, 0x2F, 0, 0, 0])

    def rejects(**overrides):
        bad = dict(ok, **overrides)
        try:
            protocol.build_set_key_assign(**bad)
        except ValueError:
            return True
        return False

    assert rejects(data=[0, 0x2F, 0, 0])            # four bytes
    assert rejects(data=[0, 0x2F, 0, 0, 0, 0])      # six
    assert rejects(data=[0, 256, 0, 0, 0])          # not a byte
    assert rejects(data=[0, -1, 0, 0, 0])
    assert rejects(layer=2)                          # neither base nor Fn
    assert rejects(key_id=256)
    assert rejects(key_id=-1)
    assert rejects(function_id=256)

    # And the valid call still works, so the guard is not simply refusing all.
    assert len(protocol.build_set_key_assign(**ok)) == protocol.REPORT_SIZE


def test_backup_round_trips_a_key_map_through_json():
    """`read_key_map` is keyed by (key_id, layer) tuples; JSON keys are strings.

    `json.dump` raises TypeError on a tuple key, so the composite string is
    load-bearing and not cosmetic. This asserts the tuples come back as tuples
    of ints — a version that returned strings would let a caller build a packet
    addressing key "50" instead of key 50.
    """
    import tempfile
    from ek75.core import state

    keys = {(50, 1): {"function_id": 6, "data": [0, 47, 0, 0, 0]},
            (1, 0): {"function_id": 6, "data": [0, 41, 0, 0, 0]},
            (170, 1): None}
    regions = {1: {"effect": 1, "flag": 0, "speed": 2,
                   "colors": [[255, 0, 0]], "brightness": 153}}

    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "backup.json")
        state.save(path, regions, keys=keys)
        assert state.load(path) == regions
        assert state.load_keys(path) == keys


def test_the_real_settle_actually_waits():
    """The burst test replaces `device.settle`, so nothing there runs this one.

    Without this, a `settle` that raised, returned early, or lost its `time`
    import would pass every other test in the file — the fakes would keep
    counting calls to something that no longer waits.
    """
    import time as _time
    from ek75.core import device

    assert device.SETTLE_AFTER_BURST >= 0.1, (
        "measured: 50 ms was still wrong 4 times in 8, 100 ms was clean")

    start = _time.monotonic()
    device.settle()
    waited = _time.monotonic() - start
    assert waited >= device.SETTLE_AFTER_BURST * 0.9, (
        f"settle returned after {waited:.3f}s, expected "
        f"{device.SETTLE_AFTER_BURST}s")


def test_an_aborted_lighting_restore_still_settles():
    """The same guarantee as the key-map burst, on the other burst producer.

    Reviewed and found untested: `Explodes` only ever ran against
    `restore_key_map`, so `restore`'s own `finally` was asserted by nothing.
    """
    from ek75.core import lighting

    naps = []

    class Explodes:
        settle = staticmethod(lambda: naps.append(1))

        @staticmethod
        def command_process(fd, packet, **kw):
            raise OSError("the device went away mid-burst")

    real = lighting.device
    session = lighting.Session.__new__(lighting.Session)
    session.fd = None
    try:
        lighting.device = Explodes
        try:
            session.restore({1: {"effect": 1, "flag": 0, "speed": 0,
                                 "colors": [(255, 0, 0)], "brightness": 100}})
        except OSError:
            pass
        else:
            raise AssertionError("the error should not have been swallowed")
        assert len(naps) == 1, "an aborted lighting restore skipped the settle"

        # A malformed entry raises before anything is sent, so there is no
        # burst to recover from and no reason to wait 150 ms.
        naps.clear()
        try:
            session.restore({1: {"colors": [(255, 0, 0)]}})   # no "effect"
        except KeyError:
            pass
        else:
            raise AssertionError("a missing key should have raised")
        assert naps == [], "settled after sending nothing"

        # The same on the key-map side, which is the case review named.
        naps.clear()
        try:
            session.restore_key_map({(1, 0): {}})            # no "function_id"
        except KeyError:
            pass
        else:
            raise AssertionError("a missing key should have raised")
        assert naps == [], "settled after sending nothing"
    finally:
        lighting.device = real


def test_assign_key_reports_what_the_keyboard_stored_not_what_was_asked():
    """Write, let the link settle, then read — and return the read.

    The requested value and the stored value can differ, and only the second one
    is true. Returning the request would make the UI a mirror of its own input,
    which is the exact failure `HIDIOCSFEATURE` invites: the ioctl succeeds
    whether or not the firmware liked the packet.

    The settle sits between the two because a user clicking Apply repeatedly
    turns single writes into a burst, and a read inside a burst returns a
    coherent earlier state. One isolated write then a read was measured correct
    30/30, but "isolated" is not something this method can promise.
    """
    from ek75.core import lighting, protocol

    calls = []

    class Keyboard:
        """Stores the write, and answers the read with something different."""
        settle = staticmethod(lambda: calls.append("settle"))

        @staticmethod
        def command_process(fd, packet, **kw):
            is_get = packet[protocol.HDR_COMMAND] & protocol.GET_CMD
            calls.append("read" if is_get else "write")
            if not is_get:
                return packet
            reply = bytearray(protocol.REPORT_SIZE)
            reply[protocol.HDR_STATUS] = 0x02
            reply[protocol.PAYLOAD_BASE + 2] = 6
            reply[protocol.PAYLOAD_BASE + 3:protocol.PAYLOAD_BASE + 8] = \
                bytes([0, 99, 0, 0, 0])              # NOT what was requested
            return bytes(reply)

    real = lighting.device
    session = lighting.Session.__new__(lighting.Session)
    session.fd = None
    try:
        lighting.device = Keyboard
        got = session.assign_key(50, protocol.LAYER_FN, 6, [0, 71, 0, 0, 0])
    finally:
        lighting.device = real

    assert calls == ["write", "settle", "read"], calls
    assert got == {"function_id": 6, "data": [0, 99, 0, 0, 0]}, (
        "returned the requested value instead of the stored one")


def test_assign_key_says_nothing_rather_than_guessing_when_the_write_is_refused():
    """A write the firmware never acknowledged must not be followed by a read
    that happens to succeed and looks like confirmation."""
    from ek75.core import lighting, protocol

    calls = []

    class Refuses:
        settle = staticmethod(lambda: calls.append("settle"))

        @staticmethod
        def command_process(fd, packet, **kw):
            calls.append("write")
            return None

    real = lighting.device
    session = lighting.Session.__new__(lighting.Session)
    session.fd = None
    try:
        lighting.device = Refuses
        got = session.assign_key(50, protocol.LAYER_FN, 6, [0, 71, 0, 0, 0])
    finally:
        lighting.device = real

    assert got is None
    assert calls == ["write"], f"kept going after a refused write: {calls}"


def test_the_keys_that_must_not_be_remapped_are_found_in_the_live_map():
    """The escape hatch is `Fn`+`Esc`, so BOTH of those keys have to be locked.

    An earlier version of this plan locked only the `Fn` key. That leaves the
    hatch just as breakable from the other end: remap `Esc` and `Fn`+`Esc` no
    longer reaches the factory reset, which is the recovery path every other
    safety claim about key writing rests on.

    Derived from the live map rather than from hardcoded ids, because the ids
    are this PID's. The keyboard names them itself: one key carries the `Fn`
    modifier (function id 10) and one carries `Factory reset` (44). On the unit
    this was written against those are 107 and 1, and nothing here says so.
    """
    from ek75.core import keymap

    key_map = {
        (1, 0): {"function_id": 6, "data": [0, 41, 0, 0, 0]},    # Esc
        (1, 1): {"function_id": 44, "data": [0, 0, 0, 0, 0]},    # Fn+Esc = reset
        (107, 0): {"function_id": 10, "data": [64, 0, 0, 0, 0]},  # Fn
        (107, 1): {"function_id": 10, "data": [64, 0, 0, 0, 0]},
        (61, 0): {"function_id": 6, "data": [0, 4, 0, 0, 0]},     # A, remappable
        (61, 1): None,
    }
    assert keymap.locked_keys(key_map) == {1, 107}

    # A keyboard that reports neither locks nothing — and a caller that then
    # writes has no hatch, which is the page's problem to say out loud, not
    # something to paper over here with a guessed id.
    assert keymap.locked_keys({(61, 0): {"function_id": 6,
                                          "data": [0, 4, 0, 0, 0]}}) == set()
    assert keymap.locked_keys({}) == set()
    assert keymap.locked_keys({(9, 0): None}) == set()


def test_only_vetted_functions_can_be_copied_from_one_key_to_another():
    """Copying bytes the keyboard produced is safe only if the *function* is.

    "Replay what this device reported" keeps the write inside validated byte
    patterns, but it says nothing about whether the result is sane. Copying
    `Factory reset` (44) onto a letter means one stray keystroke wipes the
    keyboard; copying `Knob rotation` (39) onto a key that cannot rotate is
    nonsense; copying the `Fn` modifier (10) makes a second Fn.

    So the copy source is an allowlist, not everything the device reports.
    Lighting and layout toggles are on it because losing one costs a setting;
    resets, pairing and the knob are off it because losing one costs the
    keyboard, the connection, or nothing sensible at all.
    """
    from ek75.core import keymap

    for safe in (45, 46, 47, 48, 49, 53, 54, 55):
        assert keymap.is_copyable(safe), f"function {safe} should be copyable"

    for unsafe, why in ((44, "factory reset"), (10, "the Fn modifier"),
                        (41, "Bluetooth pairing"), (42, "2.4G pairing"),
                        (39, "knob rotation"), (40, "knob press"),
                        (1, "mouse button"), (32, "mouse cursor")):
        assert not keymap.is_copyable(unsafe), f"{why} must not be copyable"

    # 6 and 8 are the keyboard and media usages, which the picker offers
    # directly and builds itself — they are not reached through the copy path.
    assert not keymap.is_copyable(6)
    assert not keymap.is_copyable(8)


def test_a_burst_leaves_the_link_quiet_exactly_once():
    """A run of writes settles at the end, not per item, and not never.

    Measured: writes always land, but while a burst is in flight a *read*
    returns a coherent earlier state — 4/8 wrong at 0 ms and at 50 ms after a
    24-command burst, 0/8 at 100 ms. See PROTOCOL.md, "Under sustained traffic,
    reads trail the keyboard's real state".

    Once, at the end: 166 x 150 ms per item would add 25 s to a key-map
    restore. In a `finally`: a burst cut short by an exception is exactly when
    the caller is most likely to read straight afterwards to find out what
    happened. And not at all when nothing was sent, because there is then no
    burst to recover from.
    """
    from ek75.core import device, lighting

    naps = []

    class Recorder:
        SETTLE_AFTER_BURST = device.SETTLE_AFTER_BURST

        @staticmethod
        def settle():
            naps.append(1)

        @staticmethod
        def command_process(fd, packet, **kw):
            return packet

    class Explodes(Recorder):
        @staticmethod
        def command_process(fd, packet, **kw):
            raise OSError("the device went away mid-burst")

    real = lighting.device
    session = lighting.Session.__new__(lighting.Session)
    session.fd = None
    try:
        lighting.device = Recorder
        session.restore({1: {"effect": 1, "flag": 0, "speed": 0,
                             "colors": [(255, 0, 0)], "brightness": 100},
                         4: {"effect": 1, "flag": 0, "speed": 0,
                             "colors": [(0, 255, 0)], "brightness": 200}})
        assert len(naps) == 1, f"two regions settled {len(naps)} times"

        naps.clear()
        session.restore_key_map({(50, 1): {"function_id": 6,
                                            "data": [0, 47, 0, 0, 0]},
                                  (60, 0): {"function_id": 6,
                                            "data": [0, 57, 0, 0, 0]}})
        assert len(naps) == 1, f"two keys settled {len(naps)} times"

        # Nothing sent means no burst to recover from.
        naps.clear()
        session.restore({})
        session.restore_key_map({(99, 1): None})     # the only entry is skipped
        assert naps == [], "settled without having sent anything"

        # An exception mid-burst must still leave the link quiet.
        naps.clear()
        lighting.device = Explodes
        try:
            session.restore_key_map({(50, 1): {"function_id": 6,
                                                "data": [0, 47, 0, 0, 0]}})
        except OSError:
            pass
        else:
            raise AssertionError("the error should not have been swallowed")
        assert len(naps) == 1, "an aborted burst skipped the settle"
    finally:
        lighting.device = real


def test_restore_keeps_an_empty_colour_list_instead_of_painting_it_black():
    """An empty colour list is the RGB/rainbow mode, not "no colour chosen".

    `restore` did `info["colors"] or [(0, 0, 0)]`, and `[]` is falsy, so every
    region saved in rainbow mode came back solid black. The backup recorded the
    state correctly; the restore threw it away — the worst shape for this bug,
    because the file looks right and the keyboard does not.

    The firmware takes an empty list and reports it back as empty: sending
    `colors=[]` to region 1 with Wave read back as `colors=[]` on hardware, so
    there is nothing to substitute and no reason to.

    The `or` was not arbitrary — `set_effect` needs at least one colour for
    effects that take one. That case is a missing/None list, which is a
    different thing from an empty one, and only it gets the fallback.
    """
    from ek75.core import lighting

    sent = []

    class Recorder:
        settle = staticmethod(lambda: None)          # the burst's quiet period

        @staticmethod
        def command_process(fd, packet, **kw):
            sent.append(packet)
            return packet

    real = lighting.device
    try:
        lighting.device = Recorder
        session = lighting.Session.__new__(lighting.Session)
        session.fd = None
        session.restore({1: {"effect": 5, "flag": 0, "speed": 2,
                             "colors": [], "brightness": 153}})
    finally:
        lighting.device = real

    # The first packet is the effect write; its colour count must be zero.
    effect_packet = sent[0]
    assert effect_packet[protocol.PAYLOAD_BASE + 1] == 5          # Wave
    assert effect_packet[protocol.PAYLOAD_BASE + 4] == 0, (
        "restore substituted a colour for the rainbow mode")

    # And a genuinely absent list still gets the fallback it was there for.
    sent.clear()
    try:
        lighting.device = Recorder
        session.restore({1: {"effect": 1, "flag": 0, "speed": 0,
                             "colors": None, "brightness": 100}})
    finally:
        lighting.device = real
    assert sent[0][protocol.PAYLOAD_BASE + 4] == 1


def test_restore_key_map_reports_each_key_rather_than_one_verdict():
    """166 writes that mostly worked is not a success, and must not look like one.

    `restore` already reports per-region for the same reason. A caller handed a
    single boolean cannot say which key was left wrong, and the honest failure
    mode for a key map is partial: one NAK in the middle leaves the keyboard in
    a state that is neither the old one nor the new one.

    Entries recorded as None are skipped, not written: None means "this key did
    not answer when the backup was taken", and turning it into
    `function_id=0, data=[0]*5` would assign the key *nothing* — a real and
    destructive assignment rather than a missing one.
    """
    from ek75.core import lighting

    written = []

    class OneKeyRefuses:
        """Acknowledges everything except key 70, which never replies."""
        settle = staticmethod(lambda: None)

        @staticmethod
        def command_process(fd, packet, **kw):
            key_id = packet[protocol.PAYLOAD_BASE + 0]
            layer = packet[protocol.PAYLOAD_BASE + 1]
            written.append((key_id, layer))
            return None if key_id == 70 else packet

    key_map = {
        (50, 1): {"function_id": 6, "data": [0, 47, 0, 0, 0]},
        (70, 1): {"function_id": 6, "data": [0, 51, 0, 0, 0]},
        (60, 0): {"function_id": 6, "data": [0, 57, 0, 0, 0]},
        (99, 1): None,
    }

    real = lighting.device
    try:
        lighting.device = OneKeyRefuses
        session = lighting.Session.__new__(lighting.Session)
        session.fd = None
        results = session.restore_key_map(key_map)
    finally:
        lighting.device = real

    assert dict(results) == {(50, 1): True, (70, 1): False, (60, 0): True}
    assert (99, 1) not in dict(results)              # None was skipped...
    assert (99, 1) not in written                    # ...and never reached the wire
    assert sorted(written) == [(50, 1), (60, 0), (70, 1)]


def test_saving_lighting_alone_does_not_destroy_a_saved_key_map():
    """`keys=None` means "nothing to say about keys", not "delete them".

    The GUI's backup button calls `state.save(path, regions)` with no key map,
    and `--lighting-only` does the same. Both write to the same default path the
    CLI uses. Without this, backing up lighting from the GUI silently discards
    166 key assignments the CLI had saved there — destroying a backup is a much
    worse outcome than failing to make one, and it happens with no error.

    The rule lives in `save` rather than at each call site, so a future third
    caller cannot reintroduce it by forgetting.
    """
    import tempfile
    from ek75.core import state

    keys = {(50, 1): {"function_id": 6, "data": [0, 47, 0, 0, 0]}}
    first = {1: {"effect": 1, "flag": 0, "speed": 2,
                 "colors": [[255, 0, 0]], "brightness": 100}}
    second = {1: {"effect": 3, "flag": 0, "speed": 1,
                  "colors": [], "brightness": 200}}

    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "backup.json")
        state.save(path, first, keys=keys)
        state.save(path, second)                     # lighting only, as the GUI does

        assert state.load(path) == second            # the lighting did update
        assert state.load_keys(path) == keys         # and the key map survived

    # An explicitly empty map is a different statement and must be honoured.
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "backup.json")
        state.save(path, first, keys=keys)
        state.save(path, second, keys={})
        assert state.load_keys(path) == {}

    # The same rule on the other axis: `backup --keys-only` must not wipe the
    # lighting it was told not to touch. Same decision, so it lives in the same
    # place rather than being fixed once per direction.
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "backup.json")
        state.save(path, first, keys=keys)
        state.save(path, None, keys={(1, 0): {"function_id": 6,
                                               "data": [0, 41, 0, 0, 0]}})
        assert state.load(path) == first             # the lighting survived
        assert state.load_keys(path) == {(1, 0): {"function_id": 6,
                                                   "data": [0, 41, 0, 0, 0]}}


def test_a_backup_written_before_keys_existed_still_loads():
    """Every backup on disk today has no "keys" section, and `load` had no guard.

    Two separate promises: `load` keeps returning the regions it always did,
    and `load_keys` says None rather than raising KeyError or inventing {}.
    None and {} must stay distinguishable — one means "this file predates key
    backups", the other "a key map was recorded and was empty", and a caller
    about to write to hardware should treat them differently.
    """
    import json as _json
    import tempfile
    from ek75.core import state

    legacy = {"timestamp": "2026-09-07T23:31:00",
              "regions": {"1": {"effect": 1, "flag": 0, "speed": 2,
                                 "colors": [[0, 255, 0]], "brightness": 200}}}
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "old.json")
        with open(path, "w") as f:
            _json.dump(legacy, f)

        assert state.load(path) == {1: legacy["regions"]["1"]}
        assert state.load_keys(path) is None

        # A lighting-only backup written today must look the same to load_keys.
        fresh = os.path.join(tmp, "fresh.json")
        state.save(fresh, {1: legacy["regions"]["1"]})
        assert state.load_keys(fresh) is None


def test_how_many_colours_each_effect_actually_uses():
    """Per-effect, from the vendor's own table — and it matches the hardware.

    `OEMDriver.Pages.PageLedTg::CheckCustomColorCount` in the Windows app
    reduces to: effects 1, 4, 9, 20, 21, 22 and 132 take one colour; `Starlit`
    (11) and `Breathing` (2) take more; everything else takes one. The `Ws`,
    `Qf` and `Jm` pages carry the identical method, so it is a framework rule
    rather than this model's quirk.

    Three independent agreements with what a human saw on this keyboard:
    `Static` showed one colour (listed as 1), `Wave` showed one (the default
    branch), and `Breathing` cycled red, green and blue in order (listed as
    multi). The table was read out of the binary after those observations, not
    used to predict them.

    Each number is the largest one something can vouch for, and they do not
    share a source. `Breathing` gets 3 because three were watched cycling; the
    vendor's 2 is its UI's limit, not the firmware's. 4 and 5 are not offered,
    because the wire allowing them is not evidence that they render.

    `Starlit` gets the vendor's 2 and no more. An earlier draft gave it
    MAX_COLORS purely because it shares a branch with `Breathing` in that table
    — which says nothing about `Starlit`, which nobody has looked at. That is
    the "inventing capability" this project exists to not do.
    """
    assert protocol.max_colors_for(protocol.EFFECT_BREATHING) == 3
    assert protocol.max_colors_for(protocol.EFFECT_STARLIT) == 2
    assert all(n <= protocol.MAX_COLORS
               for n in protocol.COLORS_PER_EFFECT.values())

    for single in (protocol.EFFECT_STATIC, protocol.EFFECT_REACTIVE,
                   protocol.EFFECT_RUNNING_LIGHT, protocol.EFFECT_RAINBOW_W,
                   protocol.EFFECT_LIGHT_WAVE, protocol.EFFECT_STEADY_STREAM,
                   protocol.EFFECT_WAVE):
        assert protocol.max_colors_for(single) == 1, f"effect {single}"

    # An effect nobody has classified falls to the safe answer, not to five.
    assert protocol.max_colors_for(200) == 1


def test_the_packet_carries_every_colour_it_is_handed():
    """The packet carries every colour; the effects checked draw `colors[0]` alone.

    Both halves are asserted here because they are separate facts and the
    project keeps getting caught conflating them. Sent, stored and read back:
    two, three and five colours, byte-identical, on `Static`, `Wave`,
    `Breathing` and `RainbowW`. Looked at by a human: `Static` with red+green+
    blue showed all red, and `Wave` with the same three showed all red sweeping.

    `Wave` is the load-bearing half of that. A still effect ignoring a list
    explains itself away; an animated one is where bands or a gradient would be
    unmistakable, and it drew one colour too.

    Confirmed for `Static` and `Wave` only, and NOT true in general — see
    `test_how_many_colours_each_effect_actually_uses` above. `Breathing` draws
    the whole list, one colour per breath, which is what an earlier version of
    this docstring got wrong by generalising from two effects.

    This test is about the packet, which must carry every colour regardless of
    what any one effect does with them.
    """
    packet = protocol.build_set_lighting_effect(
        1, protocol.EFFECT_STATIC,
        [(255, 0, 0), (0, 255, 0), (0, 0, 255)], flag=0, speed=2)

    assert packet[protocol.PAYLOAD_BASE + 4] == 3, "the count must be the real one"
    assert list(packet[protocol.PAYLOAD_BASE + 5:protocol.PAYLOAD_BASE + 14]) == \
        [255, 0, 0, 0, 255, 0, 0, 0, 255], "every colour must reach the wire"

    # At the cap itself, which three colours would not have caught: a builder
    # that silently stopped after three would satisfy every assertion above.
    full = [(1, 2, 3), (4, 5, 6), (7, 8, 9), (10, 11, 12), (13, 14, 15)]
    packet = protocol.build_set_lighting_effect(1, protocol.EFFECT_STATIC, full)
    assert packet[protocol.PAYLOAD_BASE + 4] == protocol.MAX_COLORS
    end = protocol.PAYLOAD_BASE + 5 + 3 * protocol.MAX_COLORS
    assert list(packet[protocol.PAYLOAD_BASE + 5:end]) == list(range(1, 16))
    assert packet[end] == 0, "nothing may trail the last colour"

    # The cap is the vendor's own: its Windows app refuses to send a sixth.
    try:
        protocol.build_set_lighting_effect(
            1, protocol.EFFECT_STATIC, [(1, 1, 1)] * (protocol.MAX_COLORS + 1))
    except ValueError:
        pass
    else:
        raise AssertionError("six colours should have been refused")


# --- CLASS_MACRO (6), read-only ---------------------------------------------

def test_get_macro_id_list_probe():
    """Port of `GetMacroIdList` — GetMultiPacketCmd(0, CLASS_MACRO, 1|GET, null).

    Expected bytes read off the vendor source, not off the builder:
      00 status | 01 size | 06 class | 81 cmd (1 | GET) | 00 profile
    """
    expected = _padded(bytes.fromhex("0001068100"))
    assert protocol.build_get_macro_id_list_probe() == expected


def test_three_id_lists_over_one_transport_are_decoded_three_ways():
    """The clearest reason in this project not to port by analogy.

    `LED_CMD_ID_LIST`, `PFL_CMD_ID_LIST` and `MCO_CMD_ID_LIST` all ride
    GetMultiPacketCmd, all return a byte array of ids, and all post-process it
    differently in the vendor's own driver:

        LED      collapses ids 0 and 1 into whichever appears first
        PROFILE  filters nothing at all
        MACRO    drops every zero  (`DataArray.filter(x => x !== 0)`)

    Asserted on one shared input so the difference is a fact rather than three
    separate descriptions that can drift apart.
    """
    shared = bytes([0, 1, 0, 4, 0, 7])
    assert protocol.parse_led_region_id_list(shared) == [0, 4, 7]
    assert protocol.parse_profile_id_list(shared) == [0, 1, 0, 4, 0, 7]
    assert protocol.parse_macro_id_list(shared) == [1, 4, 7]

    assert protocol.parse_macro_id_list(b"") == []
    assert protocol.parse_macro_id_list(bytes([0, 0, 0])) == []


def test_get_macro_data_probe_carries_the_macro_id_as_an_argument():
    """`GetMacroData` is the first command here to use GetMultiPacketCmd's
    `args` — `GetMultiPacketCmd(0, CLASS_MACRO, 5|GET, [macroId], out, 2)`.

    The id goes at PAYLOAD_BASE, before the Total/Offset fields that the chunk
    requests then write after it:
      00 status | 01 size | 06 class | 85 cmd (5 | GET) | 00 profile | 00 pad
      03 macroId
    """
    expected = _padded(bytes.fromhex("00010685" + "0000" + "03"))
    assert protocol.build_get_macro_data_probe(3) == expected


def test_macro_data_chunks_place_total_and_offset_after_the_macro_id():
    """width=2 AND one argument byte, a combination nothing has exercised live.

    The hardware does answer — this unit stores one macro and returned its 27
    bytes, so the combination is not untested live. But 27 bytes is a *single*
    chunk: the offset arithmetic below, the second chunk request and the
    two-byte length decoding are still reached by nothing but these packets.
    So they are spelled out rather than trusted to the parameters lining up.

    Total and Offset are two bytes each, big-endian, starting right after the
    one argument byte — PAYLOAD_BASE+1 — and HDR_SIZE covers
    chunk + args + 2*width = 48 + 1 + 4 = 53 (0x35):

      00 | 35 | 06 | 85 | 00 | 00 | 03 | 00 64 | 00 00
                                      id  total   offset
    """
    got = protocol.build_multipacket_chunk(
        profile_id=0, cmd_class=protocol.CLASS_MACRO,
        command=protocol.MCO_CMD_MEMORY, total=0x0064, offset=0,
        chunk_len=48, args=bytes([3]), width=2)
    assert got == _padded(bytes.fromhex("0035068500" + "00" + "03"
                                         + "0064" + "0000"))

    # A non-zero offset moves only the second pair.
    got = protocol.build_multipacket_chunk(
        profile_id=0, cmd_class=protocol.CLASS_MACRO,
        command=protocol.MCO_CMD_MEMORY, total=0x0064, offset=0x0030,
        chunk_len=0x34, args=bytes([3]), width=2)
    assert got == _padded(bytes.fromhex("0039068500" + "00" + "03"
                                         + "0064" + "0030"))

    # Where the reply's payload starts, and where the total is read from.
    assert protocol.multipacket_chunk_offset(nargs=1, width=2) == \
        protocol.PAYLOAD_BASE + 1 + 4
    reply = _padded(bytes.fromhex("02" + "0000000000" + "03" + "0164"))
    assert protocol.parse_multipacket_total(reply, nargs=1, width=2) == 0x0164


# --- CLASS_PROFILE (5), read-only -------------------------------------------

def test_get_profile_id_list_probe():
    """Port of tgdevice.js `GetProfileIdList`, which is a GetMultiPacketCmd probe.

    The vendor calls `GetMultiPacketCmd(0, CLASS_PROFILE, PFL_CMD_ID_LIST|GET,
    null, out)` — ProfileId 0, exactly like `GetLedRegionIdList`, and no
    arguments. GetMultiPacketCmd's probe writes HDR_SIZE=1.

    Expected bytes read off the vendor source, not off the builder:
      00 status | 01 size | 05 class | 80 cmd (0 | GET) | 00 profile
    """
    expected = _padded(bytes.fromhex("0001058000"))
    assert protocol.build_get_profile_id_list_probe() == expected


def test_profile_id_list_is_not_filtered_like_the_led_region_list():
    """The two id lists look alike and are decoded differently. On purpose.

    `GetLedRegionIdList` post-processes its byte array, collapsing ids 0 and 1
    into whichever appears first. `GetProfileIdList` does
    `ProfileList = new Uint8Array(DataArray)` and filters nothing at all.

    Writing the profile parser by analogy with its sibling — the obvious move,
    since both are multi-packet id lists — would silently swallow a profile.
    This asserts the difference on one shared input rather than describing it.
    """
    both = bytes([0, 1, 4])
    assert protocol.parse_led_region_id_list(both) == [0, 4]     # filtered
    assert protocol.parse_profile_id_list(both) == [0, 1, 4]     # not filtered

    assert protocol.parse_profile_id_list(bytes([1])) == [1]
    assert protocol.parse_profile_id_list(b"") == []


def test_get_active_profile_writes_neither_a_size_nor_a_profile():
    """`GetActiveProfileId` sets HDR_SIZE=0 and never touches HDR_PROFILE.

    Both zeros are load-bearing and neither is an accident of the vendor's code:
    asking *which* profile is active cannot take a profile id as input, and the
    request carries no payload for HDR_SIZE to describe.

    HDR_SIZE=0 is NOT shared with `build_get_battery_status`, the other
    profile-less read in this file — that one sets HDR_SIZE=3. The two are
    alike in the profile byte only, which is the kind of half-resemblance that
    gets a 3 written here by analogy.

    Expected bytes read off the vendor source:
      00 status | 00 size | 05 class | 83 cmd (3 | GET) | 00 profile
    """
    expected = _padded(bytes.fromhex("0000058300"))
    got = protocol.build_get_active_profile()
    assert got == expected
    assert got[protocol.HDR_SIZE] == 0
    assert got[protocol.HDR_PROFILE] == 0
    assert protocol.build_get_battery_status()[protocol.HDR_SIZE] == 3


def test_active_profile_comes_back_in_the_header_not_the_payload():
    """`A.ProfileId = A.Data[DATA_INDEX.HDR_PROFILE]` — byte 4, not PAYLOAD_BASE.

    Every other parser in this file reads from PAYLOAD_BASE, so this is the one
    place where copying a sibling's shape gives the wrong byte. The test pins
    the distinction by putting a different value in each position: a parser that
    read the payload would return 7.

    The packet is synthetic on purpose, and that is worth stating plainly. The
    real reply from this keyboard was `02 00 05 83 01 00 01 00...` — the id in
    byte 4 and byte 6 both — so the hardware available here cannot distinguish
    the two readings and does not confirm the header. Only the vendor driver
    does. This test locks in the vendor's choice; it does not prove it.
    """
    resp = _padded(bytes([0x02, 0x00, 0x05, 0x83, 0x01, 0x00, 0x07]))
    assert protocol.parse_active_profile_response(resp) == 1


def test_read_profiles_reports_nothing_rather_than_a_plausible_default():
    """A timeout must surface as None, per field, not as "profile 1, obviously".

    The two reads are separate commands and either can fail alone, so the
    result carries two independent Nones. Defaulting to 1 would make the very
    assumption this read exists to test — and this project has already been
    caught believing the vendor's idea of the hardware over the hardware.

    An *empty* id list is not a failure: `get_multipacket` returns b"" when the
    device answers "zero bytes follow", so `ids` is [] and not None. The two
    outcomes mean different things and the test pins both.
    """
    from ek75.core import lighting

    class Silent:
        """Every read times out, which `device` reports as None."""
        @staticmethod
        def get_multipacket(*a, **k):
            return None

        @staticmethod
        def command_process(*a, **k):
            return None

    class AnswersEmpty(Silent):
        @staticmethod
        def get_multipacket(*a, **k):
            return b""

    real = lighting.device
    try:
        lighting.device = Silent
        session = lighting.Session.__new__(lighting.Session)
        session.fd = None
        assert session.read_profiles() == {"ids": None, "active": None}

        lighting.device = AnswersEmpty
        assert session.read_profiles() == {"ids": [], "active": None}
    finally:
        lighting.device = real


def test_speed_range_matches_what_the_firmware_produces():
    """1-3, and this is the strong tier of evidence, not the XAML one.

    `Fn`+`Left`/`Right` are bound to LightingSpeed (48) on this keyboard — which
    the device profile does not show; it was found by reading the live key map.
    Pressing them under `open-ek75 watch 1` made the firmware walk its own stored
    value 3 -> 2 -> 1 -> 2 -> 3 -> 2, never reaching 0 and never exceeding 3.

    A stored 0 does exist — it was the value before the first keypress — so the
    constants bound what the UI offers, not what the field can physically hold.
    """
    assert protocol.SPEED_MIN == 1
    assert protocol.SPEED_MAX == 3
    assert protocol.SPEED_MIN <= protocol.SPEED_NORMAL <= protocol.SPEED_MAX

    # A stored 0 must survive being read back rather than being clamped on the
    # way in: the device reports it, and rewriting it here would hide the state.
    resp = _padded(bytes.fromhex("02" + "0803020100" + "01" + "05000000"))
    assert protocol.parse_lighting_effect_response(resp)["speed"] == 0
