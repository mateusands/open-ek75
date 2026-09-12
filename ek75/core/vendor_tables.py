# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Mateus Andrade
"""Colour tables read out of the vendor's own Windows application.

These are not protocol — nothing here is ever sent to the keyboard. They are
what the firmware *shows*, transcribed so this project's preview can match the
hardware instead of approximating it with a generic HSV ramp.

Provenance: `Products/TK51G0101.dll`, the plugin the official software loads
for this exact PID. The values were recovered from the constructor's IL, where
each entry is a literal `Color.FromRgb(r, g, b)` — see PROTOCOL.md, "A second
vendor source". Model-specific: a different PID ships a different plugin with
its own tables.
"""

# `_ledShowColor` — sixteen fixed colours, one per LED of the side light strip
# (whose LED_CMD_ATTRIBUTE reply reports a 1x16 matrix). This is the pattern the
# side light renders under `Static` no matter what colour is written to it,
# which is why `protocol.COLOR_IGNORED` exists.
SIDE_LIGHT_FIXED = (
    (0, 0, 255), (0, 255, 0), (255, 0, 0), (255, 200, 16),
    (255, 0, 255), (255, 128, 255), (0, 0, 255), (0, 255, 0),
    (0, 255, 0), (0, 0, 255), (255, 0, 255), (255, 128, 255),
    (255, 200, 16), (255, 0, 0), (0, 255, 0), (0, 0, 255),
)

# `_waveColorTabel` — the 24-step ramp the animated effects cycle through. Note
# it is not a plain HSV sweep: the steps are uneven (255,20,0 then 255,85,0 then
# 255,150,0), which is why an HSV approximation never quite looked right.
WAVE_COLORS = (
    (255, 0, 0), (255, 20, 0), (255, 85, 0), (255, 150, 0),
    (255, 255, 0), (150, 255, 0), (85, 255, 0), (20, 255, 0),
    (0, 255, 0), (0, 255, 20), (0, 255, 85), (0, 255, 150),
    (0, 255, 255), (0, 150, 255), (0, 85, 255), (0, 20, 255),
    (0, 0, 255), (20, 0, 255), (85, 0, 255), (150, 0, 255),
    (255, 0, 255), (255, 0, 150), (255, 0, 85), (255, 0, 20),
)


def wave_color(position):
    """The ramp sampled at `position` (0-1), wrapping, with linear blending."""
    span = (position % 1.0) * len(WAVE_COLORS)
    low = int(span) % len(WAVE_COLORS)
    high = (low + 1) % len(WAVE_COLORS)
    ratio = span - int(span)
    return tuple(a + (b - a) * ratio
                 for a, b in zip(WAVE_COLORS[low], WAVE_COLORS[high]))


def side_light_color(index):
    """The fixed colour of one side-light LED, by position along the strip."""
    return SIDE_LIGHT_FIXED[index % len(SIDE_LIGHT_FIXED)]

# --- the key matrix: which key sits at each LED position ---------------------
# `TK51G0101::_matrixIds`, a 90-entry int32 array in the product DLL's FieldRva
# data. Six rows of fifteen, row-major, holding the KeyID at each LED position
# and 0 where the matrix has no key. Region 1 reports itself as a 6x15 matrix
# through LED_CMD_ATTRIBUTE, which is where the shape comes from independently.
#
# This is what `LED_CMD_FRAME` indexes: its payload[3] and payload[4] are the
# first and last LED in a packet, and the colours that follow are in this order.
# Without it, per-key colour has no way to say which key it means.
#
# Independently re-extracted from the DLL a second time, by a separate pass that
# had not seen this table, and compared element by element: identical. That is a
# different kind of check from the one below — it catches a transcription slip,
# where the `0101.json` comparison catches a misread of the format itself.
#
# Transcribed like the colour tables above, and checked against `0101.json` —
# which is public data this project already ships — by
# `test_the_led_matrix_matches_the_public_key_list`: every id in it exists
# there, none is repeated, and the only keys it leaves out are the three knob
# controls (170-172), which have no LED.
KEY_MATRIX_ROWS = 6
KEY_MATRIX_COLS = 15
KEY_MATRIX = (
      1,   2,   3,   4,   5,   6,   7,   8,   9,  10,  11,  12,  13,   0,   0,
     17,  18,  19,  20,  21,  22,  23,  24,  25,  26,  27,  28,  29,  31,  34,
     39,  40,  41,  42,  43,  44,  45,  46,  47,  48,  49,  50,  51,  52,  53,
     60,  61,  62,  63,  64,  65,  66,  67,  68,  69,  70,  71,   0,  73,  55,
     78,  80,  81,  82,  83,  84,  85,  86,  87,  88,  89,  91,  92,   0,   0,
     97,  98,  99,   0,   0, 102,   0,   0,   0, 106, 107, 109, 110, 111, 112,
)


def key_at_led(index):
    """The KeyID lit by LED `index`, or None where the matrix has no key."""
    if not 0 <= index < len(KEY_MATRIX):
        return None
    return KEY_MATRIX[index] or None


def led_for_key(key_id):
    """The LED index that lights `key_id`, or None — the knob has no LED."""
    try:
        return KEY_MATRIX.index(key_id)
    except ValueError:
        return None
