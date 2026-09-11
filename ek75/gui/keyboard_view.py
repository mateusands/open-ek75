# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Mateus Andrade
"""A drawing of the keyboard, with an animated preview of the selected effect.

The geometry is Dareu's own (`core.layout`, from the vendor device profile), so
this is the shape of the real hardware rather than a hand-made approximation.

The *animation*, on the other hand, is this project's own approximation: the
firmware renders the actual effect and there is no protocol command to ask it
what each LED currently shows. A preview here is a plausible illustration of
"Wave" or "Starlit", not a readback — the UI says so next to it, and nothing in
this module is ever sent to the keyboard.
"""
import colorsys
import math
import random
import tkinter as tk

from ..core import protocol, vendor_tables
from . import theme

FPS = 20
_FRAME_MS = int(1000 / FPS)

# Keys the device profile gives a border-radius this large are not keys: they
# are the rotary volume encoder, described as three overlapping round "keys".
KNOB_RADIUS = 18

# How each effect is previewed. These are illustrations, not readbacks — the
# firmware renders the real thing and there is no command to ask it what each
# LED currently shows. Grouped by the *shape* of the animation so a wrong
# grouping (previewing Waterfall as a horizontal wave, say) is easy to spot.
# Numbers are TG_LIGHT_EFFECT_INDEX (core/protocol.py).
SWEEP_HORIZONTAL = (5, 20, 21, 22, 19, 27)   # Wave, RainbowW, LightWave,
                                              # SteadyStream, Lap, Scanning
SWEEP_VERTICAL = (26,)                        # Waterfall — falls, not sideways
RUNNING = (9,)                                # RunningLight — one moving column
RADIAL = (10, 8, 7)                           # Rotate/"Difusão", Ripple, Gather
PULSE = (2, 30, 31, 32)                       # Breathing and the *Breath family
HEARTBEAT = (28,)                             # a double thump, not a sine
TWINKLE = (11, 6, 29)                         # Starlit, Raindrop, Fluxay
REACTIVE = (4, 24, 25)                        # only light on a keypress; idle
CYCLE = (3,)                                  # Neon — whole board, hue cycling


class KeyboardView(tk.Canvas):
    """Draws the key matrix plus the side light bar, and previews an effect."""

    def __init__(self, master, profile, on_key_click=None, **kwargs):
        super().__init__(master, bg=theme.BG_SUNKEN, highlightthickness=0,
                         bd=0, **kwargs)
        self.profile = profile
        self.on_key_click = on_key_click

        self._key_items = {}        # KeyID -> (polygon id, text id)
        self._selected_id = None    # outlined by select(), survives _paint
        self._side_items = []
        # Replaced with the real count once LED_CMD_ATTRIBUTE answers: on this
        # keyboard the side light reports a 1x16 matrix, so drawing 16 segments
        # shows the strip's actual resolution rather than a smooth gradient it
        # cannot produce.
        self._side_segments = 16
        self._scale = 1.0
        self._offset = (0, 0)

        self._effect = 1
        self._colors = [(255, 0, 0)]
        self._brightness = 1.0
        self._side_effect = 1
        self._side_colors = [(0, 200, 255)]
        self._side_brightness = 1.0
        self._phase = 0.0
        self._twinkle = {}
        self._animating = False
        self._after_id = None

        self.bind("<Configure>", lambda _e: self._redraw())
        self.bind("<Button-1>", self._on_click)

    # --- public API ----------------------------------------------------------

    def set_preview(self, effect, colors, brightness=None, side=False):
        """Show `effect` with `colors`; `brightness` is 0-255 or None to keep."""
        # An empty list is meaningful — it is the wire's "you choose" (RGB),
        # which the preview renders as a rainbow. Do not substitute a colour.
        colors = [tuple(c) for c in colors]
        if side:
            self._side_effect, self._side_colors = effect, colors
            if brightness is not None:
                self._side_brightness = max(0.15, brightness / 255.0)
        else:
            self._effect, self._colors = effect, colors
            if brightness is not None:
                self._brightness = max(0.15, brightness / 255.0)
        self._ensure_animating()
        self._paint()

    def select(self, key_id):
        """Outline one key, or none when `key_id` is None.

        Uses the polygon's `outline`, which `_paint` never touches — it sets
        `fill` on the polygon and the label, every animation tick. A selection
        drawn as a fill would be repainted away within 30 ms.
        """
        if self._selected_id == key_id:
            return
        self._selected_id = key_id
        for kid, item in self._key_items.items():
            chosen = kid == key_id
            self.itemconfigure(item[0],
                               outline=theme.ACCENT if chosen else theme.BORDER,
                               width=2 if chosen else 1)

    def set_side_segments(self, count):
        """How many LEDs the side light strip actually has (its matrix width)."""
        count = max(1, int(count))
        if count != self._side_segments:
            self._side_segments = count
            self._redraw()

    def stop(self):
        """Cancel the animation — call before the window is destroyed."""
        if self._after_id is not None:
            try:
                self.after_cancel(self._after_id)
            except tk.TclError:
                pass
            self._after_id = None
        self._animating = False

    # --- geometry ------------------------------------------------------------

    def _layout_metrics(self):
        w, h = self.winfo_width(), self.winfo_height()
        pw, ph = self.profile.width, self.profile.height
        if w <= 1 or h <= 1 or pw <= 0 or ph <= 0:
            return None
        pad = 18
        side_bar = 26          # room under the keys for the side light strip
        scale = min((w - 2 * pad) / pw, (h - 2 * pad - side_bar) / ph)
        draw_w, draw_h = pw * scale, ph * scale
        return scale, (w - draw_w) / 2, (h - draw_h - side_bar) / 2

    def _redraw(self):
        self.delete("all")
        selected, self._selected_id = self._selected_id, None
        self._key_items.clear()
        self._side_items.clear()
        metrics = self._layout_metrics()
        if metrics is None:
            return
        scale, ox, oy = metrics
        self._scale, self._offset = scale, (ox, oy)

        knob_keys = [k for k in self.profile.keys if k.radius >= KNOB_RADIUS]
        for key in self.profile.keys:
            if key in knob_keys:
                continue
            x1, y1 = ox + key.x * scale, oy + key.y * scale
            x2, y2 = x1 + key.w * scale, y1 + key.h * scale
            radius = max(2.0, (key.radius or 5) * scale * 0.5)
            points = theme.rounded_rect_points(x1 + 1, y1 + 1, x2 - 1, y2 - 1, radius)
            poly = self.create_polygon(points, smooth=True, splinesteps=8,
                                       fill=theme.BG_RAISED, outline=theme.BORDER)
            label = self.create_text((x1 + x2) / 2, (y1 + y2) / 2,
                                     text=self._short_label(key),
                                     fill=theme.FG, font=self._label_font(key, scale))
            self._key_items[key.id] = (poly, label)

        if knob_keys:
            self._draw_knob(knob_keys, scale, ox, oy)

        if selected is not None:                 # the polygons are new objects
            self.select(selected)                # so the outline has to be redrawn

        # The side light bar: the profile has no geometry for it (it is a
        # physical strip, not a key), so it is drawn as a strip the width of
        # the keyboard, just below it — enough to preview region 4's colour.
        bar_y = oy + self.profile.height * scale + 8
        segments = max(1, self._side_segments)
        seg_w = (self.profile.width * scale) / segments
        for i in range(segments):
            x1 = ox + i * seg_w
            self._side_items.append(
                self.create_rectangle(x1, bar_y, x1 + seg_w + 1, bar_y + 8,
                                      fill=theme.BG_RAISED, width=0))
        self._paint()

    def _draw_knob(self, keys, scale, ox, oy):
        """Draw the volume knob as a knob, not as three stacked rectangles.

        The device profile describes it as three overlapping "keys" at almost
        the same coordinates (Volume +, Volume - and Mute, all 52x52-ish with a
        border-radius of half their size). Rendering them as separate rounded
        rectangles produced one grey box labelled "Mute" — the profile's way of
        saying "a rotary encoder that also clicks", drawn literally.
        """
        x1 = ox + min(k.x for k in keys) * scale
        y1 = oy + min(k.y for k in keys) * scale
        x2 = ox + max(k.x + k.w for k in keys) * scale
        y2 = oy + max(k.y + k.h for k in keys) * scale
        # The three profile "keys" span slightly more than the knob does, and
        # their box overlaps the row beneath (Page Up). Shrink a little and pin
        # the circle to the top of the box rather than centring in it.
        cx = (x1 + x2) / 2
        r = min(x2 - x1, y2 - y1) / 2 - 3
        cy = y1 + r

        body = self.create_oval(cx - r, cy - r, cx + r, cy + r,
                                fill=theme.BG_RAISED, outline=theme.BORDER,
                                width=1)
        # A recessed centre and a tick, so it reads as something you turn.
        self.create_oval(cx - r * 0.55, cy - r * 0.55, cx + r * 0.55,
                         cy + r * 0.55, fill=theme.BG_SUNKEN, outline="")
        self.create_line(cx, cy - r * 0.9, cx, cy - r * 0.6,
                         fill=theme.FG_MUTED, width=max(1, int(r * 0.12)))
        label = self.create_text(cx, cy, text="\u266a", fill=theme.FG_MUTED,
                                 font=("Sans", max(6, int(r * 0.5))))
        # All three ids point at the same drawing, so whichever one the
        # lighting code colours, the knob lights up.
        for key in keys:
            self._key_items[key.id] = (body, label)

    @staticmethod
    def _short_label(key):
        # Long labels do not fit a 38px key at any sane font size.
        return {"Backspace": "Bksp", "Caps Lock": "Caps", "L-Shift": "Shift",
                "R-Shift": "Shift", "L-Ctrl": "Ctrl", "R-Ctrl": "Ctrl",
                "L-Alt": "Alt", "R-Alt": "AltGr", "L-Win": "Win",
                "Page Up": "PgUp", "Page Down": "PgDn", "Delete": "Del",
                "Volume +": "Vol+", "Volume -": "Vol-", "Space": ""
                }.get(key.label, key.label)

    @staticmethod
    def _label_font(key, scale):
        size = max(5, int(min(key.w, key.h) * scale * 0.22))
        return ("Sans", min(size, 9))

    def _on_click(self, event):
        if self.on_key_click is None:
            return
        scale, ox, oy = self._scale, *self._offset
        if scale <= 0:
            return
        px, py = (event.x - ox) / scale, (event.y - oy) / scale
        for key in self.profile.keys:
            if key.x <= px <= key.x + key.w and key.y <= py <= key.y + key.h:
                self.on_key_click(key)
                return

    # --- animation -----------------------------------------------------------

    def _ensure_animating(self):
        if not self._animating:
            self._animating = True
            self._tick()

    def _tick(self):
        if not self._animating:
            return
        self._phase += 1.0 / FPS
        self._paint()
        self._after_id = self.after(_FRAME_MS, self._tick)

    def _paint(self):
        if not self._key_items:
            return
        pw = max(1.0, float(self.profile.width))
        ph = max(1.0, float(self.profile.height))
        for key in self.profile.keys:
            item = self._key_items.get(key.id)
            if item is None:
                continue
            rgb = self._key_color(key, key.x / pw, key.y / ph)
            self.itemconfigure(item[0], fill=theme.hex_color(rgb))
            self.itemconfigure(item[1], fill=self._text_color(rgb))

        # The side light under Static renders a hardcoded 16-colour pattern and
        # ignores whatever colour was written to it. Drawing the written colour
        # there would be drawing something the user will never see.
        fixed = protocol.color_is_ignored(protocol.REGION_SIDE_LIGHT,
                                          self._side_effect)
        span = max(1, len(self._side_items) - 1)
        for i, item in enumerate(self._side_items):
            if fixed:
                rgb = theme.scale(vendor_tables.side_light_color(i),
                                  self._side_brightness)
            else:
                rgb = self._region_color(self._side_effect, self._side_colors,
                                         self._side_brightness, i / span, 0.0)
            self.itemconfigure(item, fill=theme.hex_color(rgb))

    def _key_color(self, key, u, v):
        return self._region_color(self._effect, self._colors, self._brightness,
                                  u, v, key_id=key.id)

    def _region_color(self, effect, colors, brightness, u, v, key_id=None):
        """The colour one LED shows, at normalised position (u, v), right now.

        `colors` empty means the firmware picks the colours itself (the "RGB"
        mode — a rainbow, not black), which is what an empty ColorList means on
        the wire and what this keyboard ships with for Wave.
        """
        t = self._phase
        rainbow = not colors
        base = colors[0] if colors else (255, 255, 255)

        if effect == protocol.EFFECT_OFF:
            return theme.BG_RAISED_RGB

        if effect in HEARTBEAT:
            # The keyboard draws a scrolling ECG trace, so the preview does too:
            # each column's brightness is the waveform sampled at that column,
            # with the whole trace moving left. A plain sine made the board
            # breathe instead of beat, which is not what the hardware shows.
            level = self._ecg((u - t * 0.35) % 1.0)
            return self._dim(self._tint(u, t, colors, rainbow, level), brightness)

        if effect in PULSE:
            level = 0.15 + 0.85 * (0.5 + 0.5 * math.sin(t * 2.0))
            return self._dim(self._tint(u, t, colors, rainbow, level), brightness)

        if effect in SWEEP_HORIZONTAL:
            return self._dim(self._sweep(u, t, colors, rainbow), brightness)

        if effect in SWEEP_VERTICAL:
            # Waterfall falls: the gradient runs down the board, not across it.
            return self._dim(self._sweep(v, t, colors, rainbow, speed=0.45),
                             brightness)

        if effect in RUNNING:
            # One bright column travelling left to right, the rest near-dark.
            head = (t * 0.4) % 1.0
            distance = min(abs(u - head), 1.0 - abs(u - head))
            level = max(0.06, 1.0 - distance * 7.0)
            return self._dim(self._tint(u, t, colors, rainbow, level), brightness)

        if effect in RADIAL:
            # Rings spreading from the middle — Rotate ("Difusão"), Ripple, Gather.
            du, dv = u - 0.5, (v - 0.5) * 0.45
            level = 0.15 + 0.85 * (0.5 + 0.5 * math.sin(
                math.hypot(du, dv) * 16.0 - t * 3.0))
            return self._dim(self._tint(u, t, colors, rainbow, level), brightness)

        if effect in TWINKLE:
            level = self._twinkle_level(key_id if key_id is not None else -1, t)
            return self._dim(self._tint(u, t, colors, rainbow, level), brightness)

        if effect in CYCLE:
            # Neon: the whole board on one hue, cycling together.
            if rainbow:
                hue = (t * 0.12) % 1.0
                rgb = tuple(c * 255 for c in colorsys.hsv_to_rgb(hue, 0.95, 1.0))
            else:
                rgb = base
            return self._dim(rgb, brightness)

        if effect in REACTIVE:
            # Reactive effects only light on a keypress; idle is a dim base.
            return self._dim(theme.scale(base, 0.18), brightness)

        return self._dim(base, brightness)              # Static and friends

    @staticmethod
    def _ecg(x):
        """One cycle of an ECG-shaped envelope, 0-1, sampled at `x` in [0, 1).

        Baseline, a small P bump, the tall QRS spike with its downward
        undershoot, then a broader T bump — the shape the effect draws.
        """
        def bump(centre, width, height):
            return height * math.exp(-((x - centre) ** 2) / width)

        # Widths are tuned for the resolution this actually renders at: the key
        # matrix is 15 columns wide, so a feature narrower than ~1/15 of the
        # board would fall between LEDs and flicker instead of showing.
        level = 0.06                                   # the flat baseline
        level += bump(0.26, 0.0016, 0.26)              # P
        level += bump(0.40, 0.0010, 0.94)              # R, the spike
        level -= bump(0.47, 0.0013, 0.40)              # S, the undershoot
        level += bump(0.62, 0.0060, 0.40)              # T
        return max(0.04, min(1.0, level))

    @staticmethod
    def _sweep(position, t, colors, rainbow, speed=0.25):
        """A gradient travelling along one axis.

        In RGB mode this samples the firmware's own 24-step ramp
        (`vendor_tables.WAVE_COLORS`) rather than a generic HSV sweep — the
        vendor's steps are deliberately uneven, which is why an HSV
        approximation never looked quite like the hardware.
        """
        if rainbow:
            return vendor_tables.wave_color(position * 0.9 - t * speed)
        if len(colors) > 1:
            span = ((position - t * speed) % 1.0) * (len(colors) - 1)
            low = int(span)
            return theme.mix(colors[low], colors[min(low + 1, len(colors) - 1)],
                             span - low)
        # A single colour still has to move, or "Wave" looks like "Static":
        # sweep its brightness instead of its hue.
        level = 0.15 + 0.85 * (0.5 + 0.5 * math.sin(
            (position - t * speed) * 2 * math.pi))
        return theme.scale(colors[0], level)

    @staticmethod
    def _tint(position, t, colors, rainbow, level):
        """`level` (0-1) applied to the effect's colour at this position."""
        if rainbow:
            rgb = vendor_tables.wave_color(position * 0.35 + t * 0.08)
        else:
            rgb = colors[0]
        return theme.scale(rgb, level)

    def _twinkle_level(self, key_id, t):
        start, span = self._twinkle.get(key_id, (None, None))
        if start is None or t - start > span:
            start = t + random.uniform(0.0, 1.2)
            span = random.uniform(0.6, 1.8)
            self._twinkle[key_id] = (start, span)
            return 0.05
        if t < start:
            return 0.05
        phase = (t - start) / span
        return 0.05 + 0.95 * math.sin(phase * math.pi) ** 2

    @staticmethod
    def _dim(rgb, brightness):
        return theme.scale(rgb, brightness)

    @staticmethod
    def _text_color(rgb):
        # Rec. 601 luma — keep the legend readable on both a lit and a dark key.
        luma = 0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]
        return "#101215" if luma > 140 else theme.FG
