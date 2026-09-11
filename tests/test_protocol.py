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
    assert keymap.describe(6, [2, 0, 0, 0, 0]) is None       # a bare modifier
