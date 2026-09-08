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
