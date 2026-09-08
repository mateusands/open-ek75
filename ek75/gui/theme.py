# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Mateus Andrade
"""Dark theme for the tkinter UI.

ttk's built-in themes are light and platform-dependent; this configures the
'clam' theme (the one ttk lets you restyle most freely) into a flat dark look
in the spirit of the keyboard's official software, without pulling in a theme
library. Colours are plain constants so a future light mode is a dict swap.
"""
import tkinter as tk
from tkinter import ttk

BG = "#232529"            # window background
BG_PANEL = "#2b2e33"      # cards, side panels
BG_RAISED = "#34383e"     # controls at rest
BG_RAISED_RGB = (0x34, 0x38, 0x3e)   # same, for the canvas preview's "off" state
BG_HOVER = "#3d424a"
BG_SUNKEN = "#1b1d20"     # the keyboard canvas, inputs
ACCENT = "#ee5a24"        # the orange the official software uses
ACCENT_DIM = "#8a3a19"
FG = "#e7e9ec"
FG_MUTED = "#9aa1ab"
FG_FAINT = "#6b727c"
OK = "#4caf50"
WARN = "#e0a030"
ERROR = "#e05c5c"
BORDER = "#3a3e45"

FONT = ("Sans", 10)
FONT_SMALL = ("Sans", 9)
FONT_TINY = ("Sans", 8)
FONT_TITLE = ("Sans", 15, "bold")
FONT_HEADING = ("Sans", 11, "bold")
FONT_MONO = ("Monospace", 9)


def apply(root):
    """Style `root` and every ttk widget under it. Returns the ttk.Style."""
    root.configure(bg=BG)
    style = ttk.Style(root)
    style.theme_use("clam")

    style.configure(".", background=BG, foreground=FG, font=FONT,
                    borderwidth=0, focuscolor=BG)
    style.configure("TFrame", background=BG)
    style.configure("Panel.TFrame", background=BG_PANEL)
    style.configure("Sunken.TFrame", background=BG_SUNKEN)

    style.configure("TLabel", background=BG, foreground=FG)
    style.configure("Panel.TLabel", background=BG_PANEL, foreground=FG)
    style.configure("Title.TLabel", background=BG, foreground=FG, font=FONT_TITLE)
    style.configure("Heading.TLabel", background=BG, foreground=ACCENT,
                    font=FONT_HEADING)
    style.configure("Muted.TLabel", background=BG, foreground=FG_MUTED,
                    font=FONT_SMALL)
    style.configure("PanelMuted.TLabel", background=BG_PANEL, foreground=FG_MUTED,
                    font=FONT_SMALL)
    style.configure("Value.TLabel", background=BG, foreground=FG, font=FONT_MONO)

    style.configure("TButton", background=BG_RAISED, foreground=FG,
                    padding=(12, 6), borderwidth=0)
    style.map("TButton",
              background=[("pressed", ACCENT_DIM), ("active", BG_HOVER),
                          ("disabled", BG_PANEL)],
              foreground=[("disabled", FG_FAINT)])

    style.configure("Accent.TButton", background=ACCENT, foreground="#ffffff",
                    padding=(16, 7))
    style.map("Accent.TButton",
              background=[("pressed", ACCENT_DIM), ("active", "#ff6b33"),
                          ("disabled", BG_PANEL)],
              foreground=[("disabled", FG_FAINT)])

    style.configure("TCheckbutton", background=BG, foreground=FG)
    style.map("TCheckbutton",
              background=[("active", BG)],
              indicatorcolor=[("selected", ACCENT), ("!selected", BG_RAISED)])

    style.configure("Horizontal.TScale", background=BG, troughcolor=BG_SUNKEN,
                    borderwidth=0, lightcolor=ACCENT, darkcolor=ACCENT)
    style.map("Horizontal.TScale", background=[("active", BG)])

    style.configure("TSeparator", background=BORDER)
    style.configure("Vertical.TScrollbar", background=BG_RAISED,
                    troughcolor=BG, arrowcolor=FG_MUTED, borderwidth=0)
    style.map("Vertical.TScrollbar", background=[("active", BG_HOVER)])

    style.configure("TCombobox", fieldbackground=BG_RAISED, background=BG_RAISED,
                    foreground=FG, arrowcolor=FG, selectbackground=ACCENT,
                    selectforeground="#ffffff", padding=(8, 4))
    root.option_add("*TCombobox*Listbox.background", BG_RAISED)
    root.option_add("*TCombobox*Listbox.foreground", FG)
    root.option_add("*TCombobox*Listbox.selectBackground", ACCENT)
    root.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")
    return style


def hex_color(rgb):
    """(r, g, b) -> '#rrggbb'."""
    r, g, b = (max(0, min(255, int(v))) for v in rgb)
    return f"#{r:02x}{g:02x}{b:02x}"


def parse_hex(text):
    """'#rrggbb' or 'rrggbb' -> (r, g, b). Raises ValueError on anything else."""
    text = text.strip().lstrip("#")
    if len(text) != 6:
        raise ValueError(f"not a 6-digit hex colour: {text!r}")
    return tuple(int(text[i:i + 2], 16) for i in (0, 2, 4))


def mix(color_a, color_b, ratio):
    """Blend two (r, g, b) tuples; ratio 0 gives a, 1 gives b."""
    return tuple(a + (b - a) * ratio for a, b in zip(color_a, color_b))


def scale(rgb, factor):
    """Multiply a colour's brightness, clamped to the 0-255 range."""
    return tuple(max(0, min(255, v * factor)) for v in rgb)


class HoverMixin:
    """Cursor + background feedback for the plain tk widgets used as buttons.

    ttk gives this for free but the effect tiles and swatches are tk.Canvas /
    tk.Frame, which do not have widget states.
    """

    def bind_hover(self, widget, normal, hover):
        widget.bind("<Enter>", lambda _e: widget.configure(bg=hover), add="+")
        widget.bind("<Leave>", lambda _e: widget.configure(bg=normal), add="+")
        widget.configure(cursor="hand2")


def rounded_rect_points(x1, y1, x2, y2, radius, steps=4):
    """Corner points for a rounded rectangle drawn as a smoothed polygon.

    tkinter's Canvas has no rounded-rectangle primitive; create_polygon with
    smooth=True and these points is the usual way to fake one.
    """
    radius = max(0, min(radius, (x2 - x1) / 2, (y2 - y1) / 2))
    if radius <= 0:
        return [x1, y1, x2, y1, x2, y2, x1, y2]
    points = []
    corners = (
        (x1 + radius, y1 + radius, 180, 270),
        (x2 - radius, y1 + radius, 270, 360),
        (x2 - radius, y2 - radius, 0, 90),
        (x1 + radius, y2 - radius, 90, 180),
    )
    import math
    for cx, cy, start, end in corners:
        for i in range(steps + 1):
            angle = math.radians(start + (end - start) * i / steps)
            points.extend((cx + radius * math.cos(angle),
                           cy + radius * math.sin(angle)))
    return points
