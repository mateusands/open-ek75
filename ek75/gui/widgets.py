# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Mateus Andrade
"""Small reusable widgets: a scrollable frame, the effect grid, colour controls.

Plain tkinter/ttk only. Anything that needs a look ttk cannot style (the effect
tiles, the colour swatches) is a tk.Canvas or tk.Frame painted by hand.
"""
import tkinter as tk
from tkinter import colorchooser, ttk

from . import i18n, theme


class ScrollFrame(ttk.Frame):
    """A vertically scrollable container. Put content in `.body`.

    `background` matters when this sits inside a Card, whose panel colour
    differs from the page's — otherwise the scrolling area shows up as a darker
    rectangle behind the content.
    """

    def __init__(self, master, background=None, body_style=None, **kwargs):
        super().__init__(master, **kwargs)
        background = background or theme.BG
        self._canvas = tk.Canvas(self, bg=background, highlightthickness=0, bd=0)
        # A hand-drawn scrollbar: ttk's is nearly invisible on this dark theme,
        # and a grid of 18 effects that scrolls with no visible sign of it just
        # looks like a grid that is missing effects.
        self._bar = tk.Canvas(self, width=8, bg=theme.BG_SUNKEN,
                              highlightthickness=0, bd=0)
        self._thumb = self._bar.create_rectangle(1, 0, 7, 0, fill=theme.FG_FAINT,
                                                 width=0)
        self._canvas.configure(yscrollcommand=self._on_scroll)
        # Pack the bar FIRST. `pack` fills the cavity in order, so a canvas
        # packed first with expand=True claims all of it and leaves the bar a
        # 1x1 unmapped strip — which is exactly why the scrollbar was invisible
        # here for as long as this widget existed.
        self._bar.pack(side="right", fill="y", padx=(4, 0))
        self._canvas.pack(side="left", fill="both", expand=True)
        self._bar.bind("<Configure>", lambda _e: self._draw_thumb())
        self._fraction = (0.0, 1.0)

        self.body = ttk.Frame(self._canvas, style=body_style or "TFrame")
        self._window = self._canvas.create_window((0, 0), window=self.body,
                                                  anchor="nw")
        self.body.bind("<Configure>", self._on_body_configure)
        self._canvas.bind("<Configure>", self._on_canvas_configure)
        self._bind_wheel(self._canvas)
        self._bind_wheel(self.body)

    def _on_scroll(self, first, last):
        self._fraction = (float(first), float(last))
        self._draw_thumb()

    def _draw_thumb(self):
        """Size and place the scroll thumb; hide the track when nothing scrolls."""
        first, last = self._fraction
        height = self._bar.winfo_height()
        if height <= 1:
            return
        if last - first >= 0.999:
            self._bar.itemconfigure(self._thumb, state="hidden")
            self._bar.configure(bg=theme.BG)
            return
        self._bar.itemconfigure(self._thumb, state="normal")
        self._bar.configure(bg=theme.BG_SUNKEN)
        top = first * height
        bottom = max(top + 18, last * height)      # never a sliver too small to see
        self._bar.coords(self._thumb, 1, top, 7, bottom)

    def _on_body_configure(self, _event):
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))
        self._draw_thumb()
        self.rebind_wheel()

    def _on_canvas_configure(self, event):
        self._canvas.itemconfigure(self._window, width=event.width)

    WHEEL_STEP = 3          # rows per notch; 1 felt like dragging

    def _bind_wheel(self, widget):
        """Bind the wheel on `widget` and everything inside it.

        The obvious approach — `bind_all` on <Enter> and unbind on <Leave> —
        does not work here: in Tk, moving the pointer onto a *child* sends
        <Leave> to the parent, so the wheel died the moment the cursor touched
        any of the labels the list is made of. Binding each descendant has no
        such hole, and leaves other scrollable areas alone.
        """
        for sequence in ("<Button-4>", "<Button-5>", "<MouseWheel>"):
            widget.bind(sequence, self._on_wheel, add="+")
        for child in widget.winfo_children():
            self._bind_wheel(child)

    def rebind_wheel(self):
        """Re-bind after the content changed — new children need it too."""
        self._bind_wheel(self.body)

    def _on_wheel(self, event):
        if not self._scrollable():
            return None
        if event.num == 4 or getattr(event, "delta", 0) > 0:
            self._canvas.yview_scroll(-self.WHEEL_STEP, "units")
        elif event.num == 5 or getattr(event, "delta", 0) < 0:
            self._canvas.yview_scroll(self.WHEEL_STEP, "units")
        return "break"          # don't let an outer scroller move as well

    def _scrollable(self):
        first, last = self._fraction
        return last - first < 0.999


class EffectTile(tk.Frame):
    """One selectable effect in the grid: a glyph, a name, a selected state."""

    def __init__(self, master, effect_id, name, glyph, on_click):
        super().__init__(master, bg=theme.BG_RAISED, highlightthickness=1,
                         highlightbackground=theme.BORDER, cursor="hand2")
        self.effect_id = effect_id
        self._selected = False

        self._glyph = tk.Label(self, text=glyph, bg=theme.BG_RAISED,
                               fg=theme.FG, font=("Sans", 15))
        self._glyph.pack(pady=(9, 1))
        self._name = tk.Label(self, text=name, bg=theme.BG_RAISED,
                              fg=theme.FG_MUTED, font=theme.FONT_TINY,
                              wraplength=86, justify="center")
        self._name.pack(pady=(0, 8), padx=3)

        for widget in (self, self._glyph, self._name):
            widget.bind("<Button-1>", lambda _e: on_click(self.effect_id))
            widget.bind("<Enter>", lambda _e: self._hover(True))
            widget.bind("<Leave>", lambda _e: self._hover(False))

    def _hover(self, on):
        if self._selected:
            return
        self._paint(theme.BG_HOVER if on else theme.BG_RAISED,
                    theme.FG, theme.FG_MUTED, theme.BORDER)

    def set_selected(self, selected):
        self._selected = selected
        if selected:
            self._paint(theme.ACCENT, "#ffffff", "#ffe8dd", theme.ACCENT)
        else:
            self._paint(theme.BG_RAISED, theme.FG, theme.FG_MUTED, theme.BORDER)

    def _paint(self, bg, glyph_fg, name_fg, border):
        self.configure(bg=bg, highlightbackground=border)
        self._glyph.configure(bg=bg, fg=glyph_fg)
        self._name.configure(bg=bg, fg=name_fg)


# A glyph per effect, so the grid reads at a glance the way the official
# software's icon grid does. Purely cosmetic; keyed by TG_LIGHT_EFFECT_INDEX.
EFFECT_GLYPHS = {
    0: "○", 1: "■", 2: "◍", 3: "❋", 4: "◉", 5: "≋", 6: "❞", 7: "◈",
    8: "◎", 9: "▸", 10: "↻", 11: "✦", 12: "▲", 19: "◐", 20: "◔",
    21: "〰", 22: "⇉", 23: "⏻", 24: "▣", 25: "▤", 26: "⇊", 27: "⌷",
    28: "♥", 29: "◇", 30: "♡", 31: "☾", 32: "☆",
}


class EffectGrid(ttk.Frame):
    """A grid of EffectTiles, rebuilt whenever the available effects change."""

    COLUMNS = 3

    def __init__(self, master, on_select, effect_names):
        super().__init__(master)
        self._on_select = on_select
        self._effect_names = effect_names
        self._tiles = {}
        self._selected = None

    def set_effects(self, effect_ids):
        for tile in self._tiles.values():
            tile.destroy()
        self._tiles.clear()
        for index, effect_id in enumerate(effect_ids):
            english = self._effect_names.get(effect_id, f"#{effect_id}")
            tile = EffectTile(self, effect_id, i18n.effect_label(english),
                              EFFECT_GLYPHS.get(effect_id, "◆"), self._on_select)
            tile.grid(row=index // self.COLUMNS, column=index % self.COLUMNS,
                      sticky="nsew", padx=3, pady=3)
            self._tiles[effect_id] = tile
        for column in range(self.COLUMNS):
            self.grid_columnconfigure(column, weight=1, uniform="effect")
        self.set_selected(self._selected)

    def set_selected(self, effect_id):
        self._selected = effect_id
        for eid, tile in self._tiles.items():
            tile.set_selected(eid == effect_id)

    @property
    def effect_ids(self):
        return list(self._tiles)


PRESET_COLORS = [
    (255, 0, 0), (255, 106, 0), (255, 216, 0), (0, 255, 0), (0, 200, 255),
    (0, 64, 255), (140, 0, 255), (255, 0, 170), (255, 255, 255),
]


class ColorPicker(ttk.Frame):
    """Colour selection, including the firmware-picked "RGB" mode.

    Sending an **empty** colour list is how the wire says "you choose" — it is
    what this keyboard ships with for `Wave`, and it is the only way to get the
    rainbow that the official software calls RGB. So this widget's value is a
    *list*: `[]` for RGB, `[(r, g, b)]` for a colour.
    """

    SWATCH = 22

    def __init__(self, master, on_change, initial=(255, 0, 0)):
        super().__init__(master)
        self._on_change = on_change
        self._color = tuple(initial)
        self._rainbow = False

        top = ttk.Frame(self)
        top.pack(fill="x")
        self._preview = tk.Canvas(top, width=44, height=26, bd=0,
                                  highlightthickness=1,
                                  highlightbackground=theme.BORDER)
        self._preview.pack(side="left")
        self._label = ttk.Label(top, text="", style="Value.TLabel")
        self._label.pack(side="left", padx=8)
        self._pick = ttk.Button(top, text=i18n.t("pick_color"),
                                command=self._open_dialog)
        self._pick.pack(side="right")

        swatches = ttk.Frame(self)
        swatches.pack(fill="x", pady=(8, 0))

        # The RGB swatch comes first and is visibly not a colour.
        self._rgb_swatch = tk.Canvas(swatches, width=self.SWATCH * 2 + 4,
                                     height=self.SWATCH, bd=0,
                                     highlightthickness=2,
                                     highlightbackground=theme.BORDER,
                                     cursor="hand2")
        self._rgb_swatch.grid(row=0, column=0, padx=(0, 8))
        self._paint_rainbow(self._rgb_swatch, self.SWATCH * 2 + 4, self.SWATCH)
        self._rgb_swatch.bind("<Button-1>", lambda _e: self.set_colors([], notify=True))

        self._solid = []
        for index, rgb in enumerate(PRESET_COLORS):
            canvas = tk.Canvas(swatches, width=self.SWATCH, height=self.SWATCH,
                               bg=theme.hex_color(rgb), bd=0,
                               highlightthickness=1,
                               highlightbackground=theme.BORDER, cursor="hand2")
            canvas.grid(row=0, column=index + 1, padx=2)
            canvas.bind("<Button-1>",
                        lambda _e, c=rgb: self.set_colors([c], notify=True))
            self._solid.append(canvas)
        self._render()

    @property
    def colors(self):
        """`[]` when RGB mode is on, otherwise `[(r, g, b)]`."""
        return [] if self._rainbow else [self._color]

    def set_colors(self, colors, notify=False):
        self._rainbow = not colors
        if colors:
            self._color = tuple(int(v) for v in colors[0])
        self._render()
        if notify:
            self._on_change(self.colors)

    @staticmethod
    def _paint_rainbow(canvas, width, height):
        """A hue ramp, drawn as vertical slices — Canvas has no gradient fill."""
        import colorsys
        for x in range(int(width)):
            r, g, b = colorsys.hsv_to_rgb(x / max(1.0, width - 1), 0.95, 1.0)
            canvas.create_line(x, 0, x, height,
                               fill=theme.hex_color((r * 255, g * 255, b * 255)))

    def _render(self):
        if self._rainbow:
            self._preview.delete("all")
            self._preview.configure(bg=theme.BG_SUNKEN)
            self._paint_rainbow(self._preview, 44, 26)
            self._label.configure(text=i18n.t("rgb_mode"))
            self._rgb_swatch.configure(highlightbackground=theme.ACCENT)
            self._pick.state(["disabled"])
        else:
            self._preview.delete("all")
            self._preview.configure(bg=theme.hex_color(self._color))
            self._label.configure(text=theme.hex_color(self._color).upper())
            self._rgb_swatch.configure(highlightbackground=theme.BORDER)
            self._pick.state(["!disabled"])

    def _open_dialog(self):
        chosen = colorchooser.askcolor(color=theme.hex_color(self._color),
                                       parent=self)
        if chosen and chosen[0]:
            self.set_colors([tuple(int(v) for v in chosen[0])], notify=True)


class LabeledScale(ttk.Frame):
    """A slider with a caption and a live numeric readout."""

    def __init__(self, master, label, from_, to, on_change, initial=0,
                 note=None):
        super().__init__(master)
        header = ttk.Frame(self)
        header.pack(fill="x")
        ttk.Label(header, text=label).pack(side="left")
        self._value_label = ttk.Label(header, text=str(initial),
                                      style="Value.TLabel")
        self._value_label.pack(side="right")

        self._on_change = on_change
        self._var = tk.DoubleVar(value=initial)
        self._scale = ttk.Scale(self, from_=from_, to=to, variable=self._var,
                                command=self._on_slide)
        self._scale.pack(fill="x", pady=(2, 0))
        self._scale.bind("<ButtonRelease-1>", self._on_release)

        if note:
            # Wrapped: these notes name a protocol field and its confidence, and
            # the three sliders sit side by side in a narrow column each.
            ttk.Label(self, text=note, style="Muted.TLabel",
                      wraplength=210, justify="left").pack(anchor="w", fill="x")
        self._pending = None

    @property
    def value(self):
        return int(round(self._var.get()))

    def set_value(self, value, notify=False):
        self._var.set(value)
        self._value_label.configure(text=str(int(round(value))))
        if notify:
            self._on_change(self.value, final=True)

    def _on_slide(self, _value):
        self._value_label.configure(text=str(self.value))
        self._on_change(self.value, final=False)

    def _on_release(self, _event):
        self._on_change(self.value, final=True)


class SegmentedButtons(ttk.Frame):
    """A small row of mutually-exclusive buttons (used for Direction)."""

    def __init__(self, master, options, on_select, initial=None):
        super().__init__(master)
        self._buttons = {}
        self._on_select = on_select
        self._selected = initial
        self.set_options(options)

    def set_options(self, options):
        """Rebuild the row — the direction axis depends on the selected effect."""
        for button in self._buttons.values():
            button.destroy()
        self._buttons.clear()
        for index, (value, label) in enumerate(options):
            button = tk.Label(self, text=label, bg=theme.BG_RAISED, fg=theme.FG,
                              font=theme.FONT, padx=12, pady=3, cursor="hand2")
            button.grid(row=0, column=index, padx=2)
            button.bind("<Button-1>", lambda _e, v=value: self._select(v))
            self._buttons[value] = button
        self._repaint()

    def _select(self, value):
        self._selected = value
        self._repaint()
        self._on_select(value)

    def set_selected(self, value):
        self._selected = value
        self._repaint()

    def _repaint(self):
        for value, button in self._buttons.items():
            selected = value == self._selected
            button.configure(bg=theme.ACCENT if selected else theme.BG_RAISED,
                             fg="#ffffff" if selected else theme.FG)


class Card(ttk.Frame):
    """A titled panel."""

    def __init__(self, master, title):
        super().__init__(master, style="Panel.TFrame", padding=14)
        ttk.Label(self, text=title, style="Heading.TLabel",
                  background=theme.BG_PANEL).pack(anchor="w", pady=(0, 8))
        self.body = ttk.Frame(self, style="Panel.TFrame")
        self.body.pack(fill="both", expand=True)


class ColorSlots(ttk.Frame):
    """The colour list for effects that actually use more than one.

    `Breathing` was watched doing it — one colour per breath, in order, looping.
    `Starlit` is on the vendor's list for it and has not been looked at here.
    `Static` and `Wave` were watched drawing `colors[0]` and ignoring the rest,
    so this row stays hidden for them and the single `ColorPicker` is the whole
    control. How many slots each effect gets is `protocol.max_colors_for`; see
    PROTOCOL.md, "The colour list is used by some effects, over time".

    One chip per colour, click to pick which one the `ColorPicker` edits. The
    list never empties: an effect with no colours at all is RGB mode, which is a
    different thing reached by the picker itself, not by deleting chips.
    """

    CHIP = 26

    def __init__(self, master, on_change, on_select):
        super().__init__(master)
        self._on_change = on_change
        self._on_select = on_select
        self._colors = [(255, 0, 0)]
        self._index = 0
        self._limit = 1
        self._chips = ttk.Frame(self)
        self._chips.pack(side="left")
        self._add = tk.Label(self, text="+", bg=theme.BG_RAISED, fg=theme.FG,
                             font=theme.FONT, width=2, cursor="hand2")
        self._add.bind("<Button-1>", lambda _e: self._append())
        self._add.pack(side="left", padx=(6, 0))
        self._remove = tk.Label(self, text="−", bg=theme.BG_RAISED, fg=theme.FG,
                                font=theme.FONT, width=2, cursor="hand2")
        self._remove.bind("<Button-1>", lambda _e: self._drop())
        self._remove.pack(side="left", padx=(4, 0))

    # --- state ---------------------------------------------------------------

    def configure_limit(self, limit):
        """Set the cap. Truncates silently and does NOT notify.

        It is called while syncing the UI to a newly selected effect, and
        `_on_change` reaches the device: firing it here turned choosing an
        effect into two writes, the second one undoing part of the first.
        A caller that needs the truncated list sends it itself.
        """
        self._limit = max(1, limit)
        if len(self._colors) > self._limit:
            self._colors = self._colors[:self._limit]
            self._index = min(self._index, len(self._colors) - 1)
        self._redraw()

    def set_colors(self, colors):
        """Adopt a list read from the device. Empty means RGB mode, which this
        row cannot represent — it keeps one editable chip so the picker has
        something to edit, and the page decides what to send."""
        self._colors = [tuple(c) for c in colors][:self._limit] or [(255, 0, 0)]
        self._index = 0
        self._redraw()

    def colors(self):
        return list(self._colors)

    def selected_index(self):
        return self._index

    def set_selected_color(self, rgb):
        self._colors[self._index] = tuple(rgb)
        self._redraw()
        self._on_change(list(self._colors))

    # --- interaction ---------------------------------------------------------

    def _append(self):
        if len(self._colors) >= self._limit:
            return
        self._colors.append(self._colors[self._index])
        self._index = len(self._colors) - 1
        self._redraw()
        self._on_change(list(self._colors))
        self._on_select(self._colors[self._index])

    def _drop(self):
        if len(self._colors) <= 1:
            return                      # never empty: see the class docstring
        del self._colors[self._index]
        self._index = min(self._index, len(self._colors) - 1)
        self._redraw()
        self._on_change(list(self._colors))
        self._on_select(self._colors[self._index])

    def _pick(self, index):
        self._index = index
        self._redraw()
        self._on_select(self._colors[index])

    def _redraw(self):
        for child in self._chips.winfo_children():
            child.destroy()
        for i, rgb in enumerate(self._colors):
            chip = tk.Label(self._chips, bg=theme.hex_color(rgb), width=3,
                            cursor="hand2",
                            relief="solid" if i == self._index else "flat",
                            bd=2 if i == self._index else 0,
                            highlightbackground=theme.ACCENT,
                            highlightthickness=2 if i == self._index else 0)
            chip.pack(side="left", padx=2, ipady=4)
            chip.bind("<Button-1>", lambda _e, n=i: self._pick(n))
        full = len(self._colors) >= self._limit
        self._add.configure(fg=theme.FG_MUTED if full else theme.FG)
        self._remove.configure(
            fg=theme.FG_MUTED if len(self._colors) <= 1 else theme.FG)
