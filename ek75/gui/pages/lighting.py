# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Mateus Andrade
"""The lighting page — the one part of the keyboard this project can fully drive.

Everything on this page maps to CLASS_LIGHTING commands that exist in
core/protocol.py. Where a control drives a byte whose meaning is not confirmed
on hardware (Direction, which is the packet's `Flag`), the UI says so instead of
presenting a guess as a feature — see PROTOCOL.md.
"""
import tkinter as tk
from tkinter import ttk

from ...core import protocol
from .. import i18n, theme
from ..keyboard_view import KeyboardView
from ..widgets import (ColorPicker, ColorSlots, EffectGrid, LabeledScale,
                        ScrollFrame, SegmentedButtons)

# Friendly names for the regions this hardware is known to have. Anything else
# discovered at runtime is shown as "Region N" rather than guessed at.
REGION_LABELS = {
    protocol.REGION_KEYS: "backlight",
    protocol.REGION_SIDE_LIGHT: "side_light",
}

# Which effects show a colour picker is not a guess: it is
# protocol.supports_color(), ported from the vendor software's own
# CheckSupportCustomColor.

# Two buttons, not four: the official software's SetDirctionButtonState enables
# left/right OR up/down depending on the effect, and the value it sends is 0 or
# 1 either way — see protocol.EFFECT_DIRECTION_AXIS.
DIRECTION_ARROWS = {
    protocol.DIRECTION_HORIZONTAL: [(protocol.DIRECTION_FORWARD, "→"),
                                     (protocol.DIRECTION_REVERSE, "←")],
    protocol.DIRECTION_VERTICAL: [(protocol.DIRECTION_FORWARD, "↓"),
                                   (protocol.DIRECTION_REVERSE, "↑")],
}

# What to offer when neither the keyboard's LED_CMD_ATTRIBUTE reply nor the
# vendor device profile says which effects a region supports.
FALLBACK_EFFECTS = [protocol.EFFECT_STATIC, protocol.EFFECT_BREATHING]


class RegionState:
    """The UI's idea of one region, kept while the user switches tabs."""

    def __init__(self, region_id, profile_index):
        self.region_id = region_id
        self.profile_index = profile_index
        self.effect = protocol.EFFECT_STATIC
        self.colors = [(255, 0, 0)]
        self.flag = protocol.DIRECTION_FORWARD
        self.speed = protocol.SPEED_NORMAL
        self.brightness = 120        # the vendor's own default for region 1
        self.effects = list(FALLBACK_EFFECTS)
        self.effects_source = "fallback"
        self.matrix = None          # (rows, columns) from LED_CMD_ATTRIBUTE
        self.loaded = False


class LightingPage(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master)
        self.app = app
        self.controller = app.controller
        self.profile = app.profile

        self._regions = {}
        self._order = []
        self._current = None
        self._tab_buttons = {}

        self._build()

    # --- construction --------------------------------------------------------

    def _build(self):
        # Left: what to show (effect + colour). Right: the preview and the
        # knobs that tune it. The official software stacks all of this in one
        # left column, which does not fit a 700px-tall window without hiding
        # the sliders below the fold — so the tuning controls live under the
        # preview here, where there is room for them.
        left = ttk.Frame(self, width=330)
        left.pack(side="left", fill="y", padx=(0, 14))
        left.pack_propagate(False)

        self._tabs = ttk.Frame(left)
        self._tabs.pack(fill="x", pady=(0, 10))

        scroller = ScrollFrame(left)
        scroller.pack(fill="both", expand=True)
        self._grid = EffectGrid(scroller.body, self._on_effect_selected,
                                protocol.EFFECT_NAMES)
        self._grid.pack(fill="x")

        self._effects_note = ttk.Label(left, text="", style="Muted.TLabel")
        self._effects_note.pack(anchor="w", pady=(6, 8))

        self._color_holder = ttk.Frame(left)
        self._color_holder.pack(fill="x")
        self._color_section = ttk.Frame(self._color_holder)
        self._color_section.pack(fill="x")
        ttk.Label(self._color_section, text=i18n.t("color"),
                  style="Heading.TLabel").pack(anchor="w", pady=(0, 6))
        # Shown only for the effects that actually use more than one colour —
        # Breathing and Starlit. For everything else the firmware draws
        # colors[0] and ignores the rest, so offering a list would be offering
        # something the keyboard will not do.
        self._slots = ColorSlots(self._color_section, self._on_slots_changed,
                                  self._on_slot_selected)
        self._slots_note = ttk.Label(self._color_section, text=i18n.t("color_list_note"),
                                      style="Muted.TLabel", wraplength=300,
                                      justify="left")
        self._color = ColorPicker(self._color_section, self._on_color_changed)
        self._color.pack(fill="x")
        self._color_absent = ttk.Label(self._color_holder, text="",
                                        style="Muted.TLabel", wraplength=300,
                                        justify="left")

        right = ttk.Frame(self)
        right.pack(side="left", fill="both", expand=True)

        self._view = KeyboardView(right, self.profile)
        self._view.pack(fill="both", expand=True)
        ttk.Label(right, text=i18n.t("preview_note"),
                  style="Muted.TLabel").pack(anchor="e", pady=(4, 10))

        ttk.Separator(right, orient="horizontal").pack(fill="x", pady=(0, 10))
        ttk.Label(right, text=i18n.t("advanced"),
                  style="Heading.TLabel").pack(anchor="w", pady=(0, 6))

        knobs = ttk.Frame(right)
        knobs.pack(fill="x")
        for column in range(3):
            knobs.grid_columnconfigure(column, weight=1, uniform="knob")

        # 1-100, the same range the official software's slider declares. The
        # wire carries 0-255; protocol.brightness_* converts at the boundary.
        self._brightness = LabeledScale(
            knobs, f"{i18n.t('brightness')} (%)", 1, 100,
            self._on_brightness_changed, initial=50,
            note=i18n.t("brightness_note"))
        self._brightness.grid(row=0, column=0, sticky="ew", padx=(0, 14))

        speed_cell = ttk.Frame(knobs)
        speed_cell.grid(row=0, column=1, sticky="ew", padx=(0, 14))
        self._speed = LabeledScale(
            speed_cell, i18n.t("speed"), protocol.SPEED_MIN, protocol.SPEED_MAX,
            self._on_speed_changed, initial=protocol.SPEED_NORMAL,
            note=f"{i18n.t('speed_slow')} · {i18n.t('speed_normal')} · "
                 f"{i18n.t('speed_fast')}")
        self._speed.pack(fill="x")
        self._speed_absent = ttk.Label(speed_cell, text=i18n.t("no_speed"),
                                        style="Muted.TLabel", wraplength=210,
                                        justify="left")

        direction_cell = ttk.Frame(knobs)
        direction_cell.grid(row=0, column=2, sticky="ew")
        ttk.Label(direction_cell, text=i18n.t("direction")).pack(anchor="w")
        self._direction = SegmentedButtons(
            direction_cell, DIRECTION_ARROWS[protocol.DIRECTION_HORIZONTAL],
            self._on_direction_changed, initial=protocol.DIRECTION_FORWARD)
        self._direction.pack(anchor="w", pady=(2, 0))
        self._direction_note = ttk.Label(
            direction_cell, text=f"byte 8 (Flag) — {i18n.t('from_windows_app')}",
            style="Muted.TLabel", wraplength=210, justify="left")
        self._direction_note.pack(anchor="w", fill="x")

        actions = ttk.Frame(right)
        actions.pack(fill="x", pady=(14, 0))
        self._live = tk.BooleanVar(value=True)
        ttk.Checkbutton(actions, text=i18n.t("apply_live"),
                        variable=self._live).pack(side="left")
        ttk.Button(actions, text=i18n.t("apply"), style="Accent.TButton",
                   command=lambda: self._apply(force=True)).pack(side="right")
        self._off_button = ttk.Button(actions, text=i18n.t("turn_off"),
                                       command=self._on_turn_off)
        self._off_button.pack(side="right", padx=(0, 8))

    # --- device data ---------------------------------------------------------

    def refresh(self):
        """Re-read every region from the keyboard."""
        self.app.set_status(i18n.t("reading"))
        self.controller.submit("read-lighting", self._read_all,
                               on_done=self._on_loaded,
                               on_error=self.app.report_error)

    @staticmethod
    def _read_all(session):
        ids, source = session.region_ids()
        out = []
        for region in ids:
            out.append((region, session.region_attribute(region),
                        session.read_region(region)))
        return source, out

    def _on_loaded(self, payload):
        source, rows = payload
        self._order = []
        for index, (region_id, attribute, info) in enumerate(rows):
            state = self._regions.setdefault(region_id,
                                             RegionState(region_id, index))
            state.profile_index = index
            if attribute:
                state.matrix = attribute["matrix"]
            if attribute and attribute["effects"]:
                state.effects = attribute["effects"]
                state.effects_source = "LED_CMD_ATTRIBUTE"
            else:
                from_profile = self.profile.custom_effect_list(index)
                if from_profile:
                    state.effects = from_profile
                    state.effects_source = f"{self.profile.pid}.json"
                else:
                    state.effects = list(FALLBACK_EFFECTS)
                    state.effects_source = "fallback"
            if info:
                state.effect = info["effect"]
                # An empty list is the RGB mode, not "no data" — `or
                # state.colors` here used to turn every RGB region into the
                # default red the moment the app re-read the keyboard.
                state.colors = [tuple(c) for c in info["colors"]]
                state.flag = info["flag"]
                state.speed = info["speed"]
                if info["brightness"] is not None:
                    state.brightness = info["brightness"]
            state.loaded = True
            self._order.append(region_id)

        self._rebuild_tabs()
        if self._order:
            self._select_region(self._current if self._current in self._regions
                                else self._order[0])
        self.app.set_status(i18n.t("region_source", source=source), kind="ok")

    def _rebuild_tabs(self):
        for widget in self._tabs.winfo_children():
            widget.destroy()
        self._tab_buttons.clear()
        for region_id in self._order:
            key = REGION_LABELS.get(region_id)
            text = i18n.t(key) if key else i18n.t("region_n", n=region_id)
            button = tk.Label(self._tabs, text=text, bg=theme.BG,
                              fg=theme.FG_MUTED, font=theme.FONT_HEADING,
                              padx=10, pady=6, cursor="hand2")
            button.pack(side="left")
            button.bind("<Button-1>",
                        lambda _e, r=region_id: self._select_region(r))
            self._tab_buttons[region_id] = button

    # --- region switching ----------------------------------------------------

    def _select_region(self, region_id):
        self._current = region_id
        state = self._regions[region_id]
        for rid, button in self._tab_buttons.items():
            selected = rid == region_id
            button.configure(fg=theme.ACCENT if selected else theme.FG_MUTED)

        self._grid.set_effects(state.effects)
        self._grid.set_selected(state.effect)
        self._effects_note.configure(
            text=f"{len(state.effects)} effects · {state.effects_source}")
        self._color.set_colors(state.colors)
        self._brightness.set_value(protocol.brightness_to_percent(state.brightness))
        self._speed.set_value(max(protocol.SPEED_MIN,
                                   min(protocol.SPEED_MAX, state.speed
                                       or protocol.SPEED_NORMAL)))
        self._sync_effect_controls(state)
        self._update_preview()

    @property
    def _state(self):
        return self._regions.get(self._current)

    def _sync_effect_controls(self, state):
        """Show only the controls this effect actually has.

        The official software does the same: SetLedParamControllerState disables
        the speed slider for effects without one, and SetDirctionButtonState
        collapses the direction control entirely. Offering a control the
        firmware ignores is worse than not offering it.
        """
        effect = state.effect
        # Three cases: the effect has no colour of its own, this hardware is
        # known to ignore the colour here, or the picker applies normally.
        if protocol.color_is_ignored(state.region_id, effect):
            # This zone renders a fixed pattern here whatever we send.
            self._color_section.pack_forget()
            self._color_absent.configure(text=i18n.t("color_ignored"))
            self._color_absent.pack(fill="x")
        elif not protocol.supports_color(effect):
            # The firmware colours this effect itself — RGB only.
            self._color_section.pack_forget()
            self._color_absent.configure(text=i18n.t("color_rgb_only"))
            self._color_absent.pack(fill="x")
        else:
            self._color_absent.pack_forget()
            self._color_section.pack(fill="x")
            limit = protocol.max_colors_for(effect)
            self._slots.configure_limit(limit)
            # Hidden in RGB mode too: an empty list is the firmware colouring
            # the effect itself, which is not a list with zero entries. Leaving
            # the row up would show swatches that no longer describe anything.
            if limit > 1 and state.colors:
                self._slots.set_colors(state.colors)
                self._slots.pack(fill="x", pady=(0, 4), before=self._color)
                self._slots_note.pack(anchor="w", pady=(0, 6), before=self._color)
            else:
                self._slots.pack_forget()
                self._slots_note.pack_forget()

        if protocol.has_speed(effect):
            self._speed_absent.pack_forget()
            self._speed.pack(fill="x")
        else:
            self._speed.pack_forget()
            self._speed_absent.pack(anchor="w", fill="x")

        # Effect 0 (Off) is not universal: this keyboard's firmware lists it for
        # the side light but not for the key matrix, so the button follows the
        # region's own LED_CMD_ATTRIBUTE list rather than assuming.
        self._off_button.state(
            ["!disabled"] if protocol.EFFECT_OFF in state.effects else ["disabled"])

        axis = protocol.direction_axis(effect)
        if axis is None:
            self._direction.pack_forget()
            self._direction_note.configure(text=i18n.t("no_direction"))
        else:
            self._direction.set_options(DIRECTION_ARROWS[axis])
            self._direction.set_selected(
                state.flag if state.flag in (protocol.DIRECTION_FORWARD,
                                              protocol.DIRECTION_REVERSE) else 0)
            self._direction.pack(anchor="w", pady=(2, 0))
            # Honest label: the byte round-trips through the firmware but was
            # confirmed not to change what the keyboard renders on this model.
            self._direction_note.configure(text=i18n.t("direction_inert"))

    # --- control callbacks ---------------------------------------------------

    def _on_effect_selected(self, effect_id):
        state = self._state
        if state is None:
            return
        state.effect = effect_id
        self._grid.set_selected(effect_id)
        self._sync_effect_controls(state)
        self._update_preview()
        self._apply()

    def _on_color_changed(self, colors):
        """`colors` is [] for RGB mode, or [(r, g, b)] — see widgets.ColorPicker.

        On a multi-colour effect the picker edits whichever slot is selected,
        so its single colour is folded into the list rather than replacing it.
        RGB mode ([]) still clears the whole list: it is the firmware colouring
        the effect itself, which is not one entry in a list.
        """
        state = self._state
        if state is None:
            return
        multi = protocol.max_colors_for(state.effect) > 1
        if colors and multi and self._slots.winfo_manager():
            self._slots.set_selected_color(colors[0])
            return                      # set_selected_color re-enters via slots
        state.colors = list(colors)
        self._update_preview()
        self._apply()
        if multi:
            # Entering or leaving RGB mode changes whether the list exists at
            # all, so the row has to be re-decided rather than left as it was.
            self._sync_color_slots()

    def _sync_color_slots(self):
        """Show the slot row only when there is a list for it to describe."""
        state = self._state
        if state is None:
            return
        if protocol.max_colors_for(state.effect) > 1 and state.colors:
            self._slots.set_colors(state.colors)
            self._slots.pack(fill="x", pady=(0, 4), before=self._color)
            self._slots_note.pack(anchor="w", pady=(0, 6), before=self._color)
        else:
            self._slots.pack_forget()
            self._slots_note.pack_forget()

    def _on_slots_changed(self, colors):
        state = self._state
        if state is None:
            return
        state.colors = list(colors)
        self._update_preview()
        self._apply()

    def _on_slot_selected(self, rgb):
        """Point the picker at the chip the user just clicked, without letting
        that look like an edit — `set_color` must not fire `_on_color_changed`
        or clicking a chip would rewrite the slot it just selected."""
        self._color.set_colors([rgb], notify=False)

    def _on_brightness_changed(self, percent, final):
        state = self._state
        if state is None:
            return
        state.brightness = protocol.brightness_from_percent(percent)
        self._update_preview()
        if final:
            self._apply_brightness()

    def _on_speed_changed(self, value, final):
        state = self._state
        if state is None:
            return
        state.speed = value
        if final:
            self._apply()

    def _on_direction_changed(self, value):
        state = self._state
        if state is None:
            return
        state.flag = value
        self._apply()

    def _on_turn_off(self):
        state = self._state
        if state is None:
            return
        state.effect = protocol.EFFECT_OFF
        self._grid.set_selected(protocol.EFFECT_OFF)
        self._sync_effect_controls(state)
        self._update_preview()
        self._apply(force=True)

    # --- device writes -------------------------------------------------------

    def _apply(self, force=False):
        state = self._state
        if state is None or (not force and not self._live.get()):
            return
        region = state.region_id
        effect = state.effect
        colors = [] if effect == protocol.EFFECT_OFF else list(state.colors)
        flag, speed = state.flag, state.speed

        def work(session):
            return session.set_effect(region, effect, colors, flag=flag, speed=speed)

        self.controller.submit(f"set-effect-{region}", work,
                               on_done=lambda ok: self._on_applied(region, ok),
                               on_error=self.app.report_error)

    def _apply_brightness(self):
        state = self._state
        if state is None or not self._live.get():
            return
        region, value = state.region_id, state.brightness

        def work(session):
            return session.set_brightness(region, value)

        self.controller.submit(f"set-brightness-{region}", work,
                               on_done=lambda ok: self._on_applied(region, ok),
                               on_error=self.app.report_error)

    def _on_applied(self, region, ok):
        if ok:
            self.app.set_status(i18n.t("applied", region=region), kind="ok")
        else:
            self.app.set_status(i18n.t("apply_failed"), kind="warn")

    # --- preview -------------------------------------------------------------

    def _update_preview(self):
        state = self._state
        if state is None:
            return
        is_side = state.region_id == protocol.REGION_SIDE_LIGHT
        if is_side and state.matrix:
            self._view.set_side_segments(state.matrix[1])
        self._view.set_preview(state.effect, state.colors,
                               brightness=state.brightness, side=is_side)

    def destroy(self):
        self._view.stop()
        super().destroy()
