# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Mateus Andrade
"""Remapping a key, from the keyboard's own answer about what it currently does.

Every byte the **picker** can send is either built from a public HID usage table
or copied from an assignment this keyboard reported. It cannot invent a function
id's data bytes, because most of the vendor's 57 ids have no documented
semantics — see `core/keymap.COPYABLE_FUNCTIONS`.

**Revert is the one exception, and deliberately so**: it writes whatever the
backup file holds, which is a file on the user's disk and can be edited. That is
the same trust level `open-ek75 restore` already works at, and narrowing it
would mean a Revert that refuses to put back the very thing it recorded. What it
cannot do is produce a malformed packet — `build_set_key_assign` bounds-checks
every byte regardless of where it came from.

Two keys are never writable: the one carrying the `Fn` modifier and the one
carrying `Factory reset`. Together they are `Fn`+`Esc`, the only way back from a
key write that goes wrong which does not run a line of this project's code.
"""
import tkinter as tk
from tkinter import ttk

from ...core import keymap, protocol, state
from .. import i18n, theme
from ..keyboard_view import KeyboardView
from ..widgets import Card, ScrollFrame, SegmentedButtons

# The four left-hand modifiers, named without their side: this row cannot offer
# the right-hand ones, so "Left" would be the same word on every box. Language
# independent on purpose — Ctrl, Shift, Alt and Win are these keys' legends on
# the physical keyboard in both languages this app speaks.
MODIFIER_LABELS = {0x01: "Ctrl", 0x02: "Shift", 0x04: "Alt", 0x08: "Win"}

SOURCE_KEY = "key"
SOURCE_MEDIA = "media"
SOURCE_COPY = "copy"


class KeysPage(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master)
        self.app = app
        self.controller = app.controller
        self.profile = app.profile

        self._key_map = None
        self._locked = set()
        self._selected_key = None
        self._layer = protocol.LAYER_BASE
        self._source = SOURCE_KEY
        self._target = None                 # (function_id, data) or None
        self._busy = False

        ttk.Label(self, text=i18n.t("nav_keys"), style="Title.TLabel").pack(anchor="w")
        ttk.Label(self, text=i18n.t("keys_blurb"), style="Muted.TLabel",
                  justify="left").pack(anchor="w", pady=(2, 10))

        columns = ttk.Frame(self)
        columns.pack(fill="both", expand=True)
        left = ttk.Frame(columns)
        left.pack(side="left", fill="both", expand=True)
        right = ttk.Frame(columns, width=330)
        right.pack(side="left", fill="y", padx=(14, 0))
        right.pack_propagate(False)

        self._view = KeyboardView(left, self.profile, on_key_click=self._on_key_click)
        self._view.pack(fill="both", expand=True)
        # Opts the view into hover: a pointer cursor, an outline under the
        # cursor, and a tip saying what the key does. On this page the keys ARE
        # controls, and a control with a click handler and no feedback is the
        # defect the design review names. The lighting page does not call this —
        # there the same view is a preview and its keys are not clickable.
        self._view.set_hover_text(self._hover_text)
        # A flat, unlit look: this page is about assignments, not about light.
        self._view.set_preview(1, [(60, 66, 74)], brightness=255)
        self._view.set_preview(1, [(48, 52, 58)], brightness=255, side=True)

        self._summary = ttk.Label(left, text=i18n.t("keys_click"),
                                   style="Value.TLabel", justify="left")
        self._summary.pack(anchor="w", pady=(8, 0))

        self._build_editor(right)

    # --- construction --------------------------------------------------------

    def _build_editor(self, parent):
        card = Card(parent, i18n.t("keys_assign"))
        card.pack(fill="both", expand=True)

        ttk.Label(card.body, text=i18n.t("keys_layer"),
                  style="PanelMuted.TLabel").pack(anchor="w")
        self._layer_buttons = SegmentedButtons(
            card.body,
            [(protocol.LAYER_BASE, i18n.t("keys_base")),
             (protocol.LAYER_FN, i18n.t("keys_fn"))],
            on_select=self._on_layer, initial=protocol.LAYER_BASE)
        self._layer_buttons.pack(anchor="w", pady=(2, 10))

        ttk.Label(card.body, text=i18n.t("keys_source"),
                  style="PanelMuted.TLabel").pack(anchor="w")
        self._source_buttons = SegmentedButtons(
            card.body,
            [(SOURCE_KEY, i18n.t("keys_source_key")),
             (SOURCE_MEDIA, i18n.t("keys_source_media")),
             (SOURCE_COPY, i18n.t("keys_source_copy"))],
            on_select=self._on_source, initial=SOURCE_KEY)
        self._source_buttons.pack(anchor="w", pady=(2, 8))

        # Modifiers apply to a keyboard usage only — `data[0]` is the HID
        # modifier bitmask of `CombineKey` (6). The media and copy sources carry
        # their own five bytes and this row is hidden for them.
        self._modifier_row = ttk.Frame(card.body, style="Panel.TFrame")
        self._modifier_vars = {}
        for bit, names in keymap.HID_MODIFIERS:
            if bit > 0x08:               # the left-hand four; "Ctrl+C" means left
                continue
            var = tk.IntVar(value=0)
            # NOT `names[...].split()[-1]`. That takes the last word, which is
            # right in English ("Left Ctrl" -> "Ctrl") and wrong in every
            # language that puts the side second: "Ctrl esquerdo",
            # "Shift esquerdo", "Alt esquerdo" and "Win esquerdo" all became
            # "esquerdo", four identical checkboxes 340px wide in a 302px row.
            # The row only ever offers the left-hand modifiers, so the side is
            # noise in any language and the bare name is what belongs here.
            short = MODIFIER_LABELS[bit]
            tk.Checkbutton(self._modifier_row, text=short, variable=var,
                           command=self._on_modifier, bg=theme.BG_PANEL,
                           fg=theme.FG, selectcolor=theme.BG_SUNKEN,
                           activebackground=theme.BG_PANEL,
                           activeforeground=theme.FG, font=theme.FONT,
                           highlightthickness=0, bd=0).pack(side="left")
            self._modifier_vars[bit] = var
        self._modifier_row.pack(anchor="w", pady=(0, 8))

        # Everything with a fixed height is packed to the BOTTOM first, so the
        # list gets what is left over instead of claiming it all. Packed the
        # other way round — which is how this page shipped — `_list_holder`'s
        # height=230 plus expand=True ate the cavity and Tk silently declined to
        # map the note below it: at the default 1120x680 the Fn+Esc safety text
        # was simply not drawn, and at the 940x600 minimum the Apply button fell
        # outside the content area. Same lesson `ScrollFrame` already carries.
        self._note = ttk.Label(card.body, text="", style="PanelMuted.TLabel",
                                justify="left", wraplength=300)
        self._note.pack(side="bottom", anchor="w", pady=(10, 0))

        buttons = ttk.Frame(card.body, style="Panel.TFrame")
        buttons.pack(side="bottom", anchor="w")

        self._chosen = ttk.Label(card.body, text=i18n.t("keys_pick_target"),
                                  style="PanelMuted.TLabel", justify="left",
                                  wraplength=300)
        self._chosen.pack(side="bottom", anchor="w", pady=(8, 6))

        self._list_holder = ttk.Frame(card.body, style="Panel.TFrame")
        self._list_holder.pack(fill="both", expand=True)
        self._list = None
        self._apply_button = ttk.Button(buttons, text=i18n.t("keys_apply"),
                                         command=self._on_apply, state="disabled")
        self._apply_button.pack(side="left", padx=(0, 8))
        self._revert_button = ttk.Button(buttons, text=i18n.t("keys_revert"),
                                          command=self._on_revert, state="disabled")
        self._revert_button.pack(side="left")

    # --- data ----------------------------------------------------------------

    def _alive(self):
        try:
            return bool(self.winfo_exists())
        except tk.TclError:
            return False

    def refresh(self):
        if self._key_map is not None:
            return                          # cached for the session, as elsewhere
        self.app.request_key_map(self._store_key_map)

    def _store_key_map(self, key_map):
        if not self._alive():
            return
        self._key_map = key_map
        if key_map is None:
            self._summary.configure(text=i18n.t("fn_needs_device"))
            self._update_buttons()      # or the note stays blank, which the
            return                      # docstring there promises never happens
        self._locked = keymap.locked_keys(key_map)
        self._fill_list()
        self._update_buttons()

    # --- selection -----------------------------------------------------------

    def _on_key_click(self, key):
        if self._key_map is None:
            self._summary.configure(text=i18n.t("fn_reading"))
            return
        self._selected_key = key
        self._view.select(key.id)
        self._show_summary()
        self._update_buttons()

    def _hover_text(self, key):
        """One line for the tip: the key, then what each layer does.

        Reads the same live map the panel does, so the tip cannot disagree with
        the selection summary. Before the map arrives it says so rather than
        showing the vendor profile's answer, which is wrong here 23 times.
        """
        if self._key_map is None:
            return f"{key.label}  ·  {i18n.t('fn_reading')}"
        locked = "  ·  🔒" if key.id in self._locked else ""
        base = self._describe(self._key_map.get((key.id, protocol.LAYER_BASE)))
        fn = self._describe(self._key_map.get((key.id, protocol.LAYER_FN)))
        return (f"{key.label}   (KeyID {key.id}){locked}\n"
                f"{i18n.t('keys_base')}: {base}\n{i18n.t('keys_fn')}: {fn}")

    def _describe(self, assignment):
        return keymap.describe_assignment(assignment, i18n.LANG)

    def _show_summary(self):
        key = self._selected_key
        parts = [f"KeyID {key.id}  ·  {key.label}"]
        for layer, name in ((protocol.LAYER_BASE, i18n.t("keys_base")),
                            (protocol.LAYER_FN, i18n.t("keys_fn"))):
            parts.append(f"{name}: {self._describe(self._key_map.get((key.id, layer)))}")
        self._summary.configure(text="   ·   ".join(parts))

    def _on_layer(self, layer):
        self._layer = layer
        self._update_buttons()

    def _on_source(self, source):
        self._source = source
        self._target = None
        self._chosen.configure(text=i18n.t("keys_pick_target"))
        if source == SOURCE_KEY:
            self._modifier_row.pack(anchor="w", pady=(0, 8),
                                    before=self._list_holder)
        else:
            self._modifier_row.pack_forget()
        self._fill_list()
        self._update_buttons()

    def _modifier_mask(self):
        if self._source != SOURCE_KEY:
            return 0
        return sum(bit for bit, var in self._modifier_vars.items() if var.get())

    def _on_modifier(self):
        """Re-apply the mask to whatever is already chosen, rather than making
        the user pick the key again after ticking a box."""
        if self._target is None:
            self._update_buttons()
            return
        function_id, data = self._target
        data = list(data)
        data[0] = self._modifier_mask()
        self._target = (function_id, data)
        described = keymap.describe(function_id, data)
        self._chosen.configure(text=i18n.t(
            "keys_chosen", name=described[0 if i18n.LANG == "en" else 1]
            if described else "?"))
        self._update_buttons()

    # --- the target list -----------------------------------------------------

    def _targets(self):
        """(label, function_id, data) for the selected source, sorted for reading."""
        if self._source == SOURCE_KEY:
            index = 0 if i18n.LANG == "en" else 1
            mask = self._modifier_mask()
            return sorted(((names[index], 6, [mask, usage, 0, 0, 0])
                           for usage, names in keymap.HID_KEYS.items()),
                          key=lambda row: row[0].lower())
        if self._source == SOURCE_MEDIA:
            index = 0 if i18n.LANG == "en" else 1
            return sorted(((names[index], 8, [usage >> 8, usage & 0xFF, 0, 0, 0])
                           for usage, names in keymap.CONSUMER_KEYS.items()),
                          key=lambda row: row[0].lower())

        # Copy: only what this keyboard reported, and only vetted functions.
        #
        # Deduplicated by the BYTES, and labelled by the key they came from.
        # Both halves matter: four keys cycle the brightness and they do not
        # carry the same data, so collapsing by name would silently drop three
        # real assignments — but listing them by name alone puts four
        # indistinguishable "Cycle brightness" rows in front of the user. The
        # source key is what tells them apart, and it is also how someone thinks
        # about this feature: "do what Fn+Up does".
        labels = {k.id: k.label for k in self.profile.keys}
        seen = {}
        for (key_id, layer), value in (self._key_map or {}).items():
            if value is None or not keymap.is_copyable(value["function_id"]):
                continue
            signature = (value["function_id"], tuple(value["data"]))
            if signature in seen:
                continue                    # first key wins, deterministically
            where = labels.get(key_id, str(key_id))
            if layer == protocol.LAYER_FN:
                where = f"Fn + {where}"
            seen[signature] = (f"{self._describe(value)}  ({where})",
                               value["function_id"], list(value["data"]))
        return sorted(seen.values(), key=lambda row: row[0].lower())

    def _fill_list(self):
        if self._list is not None:
            self._list.destroy()
        self._list = ScrollFrame(self._list_holder, background=theme.BG_PANEL,
                                  body_style="Panel.TFrame")
        self._list.pack(fill="both", expand=True)

        rows = self._targets()
        if not rows:
            ttk.Label(self._list.body, text=i18n.t("keys_no_targets"),
                      style="PanelMuted.TLabel", justify="left",
                      wraplength=280).pack(anchor="w")
            return
        for label, function_id, data in rows:
            row = tk.Label(self._list.body, text=label, bg=theme.BG_PANEL,
                           fg=theme.FG, font=theme.FONT, anchor="w",
                           padx=6, pady=2, cursor="hand2")
            row.pack(fill="x")
            row.bind("<Button-1>",
                     lambda _e, l=label, f=function_id, d=data:
                     self._choose(l, f, d))

    def _choose(self, label, function_id, data):
        self._target = (function_id, list(data))
        # `describe` rather than the row's own label: with a modifier ticked the
        # row says "C" and the assignment is "Left Ctrl + C". Showing the label
        # would understate what is about to be written.
        described = keymap.describe(function_id, data)
        self._chosen.configure(text=i18n.t(
            "keys_chosen",
            name=described[0 if i18n.LANG == "en" else 1] if described else label))
        self._update_buttons()

    # --- writing -------------------------------------------------------------

    def _backup_has_keys(self):
        try:
            return state.load_keys(state.DEFAULT_PATH) is not None
        except (OSError, ValueError, KeyError):
            return False

    def _update_buttons(self):
        """Decide what is allowed, and say why when it is not.

        The note is never blank while something is refused: a disabled button
        with no explanation is the thing this project's placeholder pages exist
        to avoid.
        """
        if not self._alive():
            return
        key = self._selected_key
        note = ""
        can_write = True

        if self._busy:
            can_write, note = False, i18n.t("keys_working")
        elif self._key_map is None:
            can_write, note = False, i18n.t("fn_needs_device")
        elif key is None:
            can_write, note = False, i18n.t("keys_click")
        elif key.id in self._locked:
            can_write, note = False, i18n.t("keys_locked")
        elif not self._backup_has_keys():
            can_write, note = False, i18n.t("keys_need_backup")
        elif not self._locked:
            # Nothing on this keyboard reported the Fn modifier or the factory
            # reset, so the hatch this page relies on was not found. Say it.
            note = i18n.t("keys_no_hatch")

        self._apply_button.configure(
            state="normal" if can_write and self._target else "disabled")
        self._revert_button.configure(
            state="normal" if can_write and self._saved_for(key) else "disabled")
        self._note.configure(text=note or i18n.t("keys_hatch"))

    def _saved_for(self, key):
        if key is None:
            return None
        try:
            saved = state.load_keys(state.DEFAULT_PATH)
        except (OSError, ValueError, KeyError):
            return None
        return (saved or {}).get((key.id, self._layer))

    def _on_apply(self):
        if self._target is None or self._selected_key is None:
            return
        self._write(*self._target)

    def _on_revert(self):
        saved = self._saved_for(self._selected_key)
        if saved is None:
            return
        self._write(saved["function_id"], saved["data"])

    def _write(self, function_id, data):
        if self._busy:
            # The disabled button is a signal, not a lock: a button activated
            # from the keyboard can fire again before Tk has processed the
            # `configure`, and two overlapping jobs would clear `_busy` when the
            # first finished, not the second.
            return
        key_id, layer = self._selected_key.id, self._layer
        if key_id in self._locked:              # belt and braces: the buttons
            return                              # are disabled, but this writes
        self._busy = True
        self._update_buttons()
        self.app.set_status(i18n.t("keys_writing"), kind="info")

        def work(session):
            return session.assign_key(key_id, layer, function_id, data)

        self.controller.submit(
            f"assign-{key_id}-{layer}", work,
            on_done=lambda stored: self._on_written(key_id, layer, stored),
            on_error=self._on_write_failed)

    def _on_written(self, key_id, layer, stored):
        """`stored` is what the keyboard reports now, not what was requested."""
        self._busy = False
        if not self._alive():
            return
        if stored is None:
            self.app.set_status(i18n.t("keys_refused"), kind="error")
            self._update_buttons()
            return
        self._key_map[(key_id, layer)] = stored
        # The Home page's Fn guide reads the app-level cache; leaving it would
        # keep describing an assignment that is no longer on the keyboard.
        self.app.key_map = dict(self._key_map)
        self._locked = keymap.locked_keys(self._key_map)
        if self._selected_key is not None:
            self._show_summary()
        self.app.set_status(
            i18n.t("keys_written", name=self._describe(stored)), kind="ok")
        self._update_buttons()

    def _on_write_failed(self, error):
        self._busy = False
        if not self._alive():
            return
        self._update_buttons()
        self.app.report_error(error)

    def destroy(self):
        self._view.stop()
        super().destroy()


def keys_page(master, app):
    return KeysPage(master, app)
