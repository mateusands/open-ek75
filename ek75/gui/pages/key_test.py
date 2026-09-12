# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Mateus Andrade
"""Slice 3 of docs/investigations/key-test.md: press a physical key, watch it
light up on the drawn keyboard — reading ordinary OS keyboard events, the
same way the official app's own key-test screen does (Win32 Raw Input there,
Tk `<KeyPress>` here). Never a Dareu protocol command: nothing this page does
sends a byte to the keyboard, so CLAUDE.md's golden rule 2 does not apply to
it any more than it applies to `gui/key_input.py`.

This is the first page in this app that needs real keyboard focus — every
other page is mouse-only by design. That is a deliberate, owner-approved
exception (the investigation's own Slice 3 note said this needed explicit
sign-off before being built, separately from the technical design), not a
silent departure from the rest of the app's convention.

Reuses `KeyboardView` unchanged: its existing `select(key_id)` lights a key
up, `set_hover_text()` shows what a key does on mouseover (already shipped on
the Keys page) — nothing new added to that module, only bound to from here.
On `<KeyPress>`, the flow is keysym (Tk) -> HID `(page, usage)`
(`gui.key_input`, Slice 2) -> physical `KeyId`, resolved against the LIVE key
map (`keymap.find_key_for_keyboard_usage` / `find_key_for_consumer_usage`),
not the static profile — this keyboard's profile disagrees with the keyboard
on 23 assignments (`PROTOCOL.md`).

What this page can prove and what it cannot are different claims, and the
difference is permanent, visible UI text (the investigation's §3), not a
comment: `Fn` itself, the four Fn-lighting shortcuts, `Fn`+`Esc`, and
anything a desktop environment claims globally (Print, media keys, WM
shortcuts) are named as unconfirmable here rather than silently absent or
wrongly implied to work.
"""
import tkinter as tk
from tkinter import ttk

from ...core import keymap, protocol
from .. import i18n, key_input, theme
from ..keyboard_view import KeyboardView
from ..widgets import Card, ScrollFrame, wrap_to_width


class KeyTestPage(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master)
        self.app = app
        self.controller = app.controller
        self.profile = app.profile

        self._key_map = None
        self._locked = set()
        self._key_by_id = {k.id: k for k in self.profile.keys}

        ttk.Label(self, text=i18n.t("nav_keytest"), style="Title.TLabel").pack(anchor="w")
        blurb = ttk.Label(self, text=i18n.t("keytest_blurb"), style="Muted.TLabel",
                         justify="left")
        blurb.pack(anchor="w", fill="x", pady=(2, 10))
        wrap_to_width(blurb)

        columns = ttk.Frame(self)
        columns.pack(fill="both", expand=True)
        left = ttk.Frame(columns)
        left.pack(side="left", fill="both", expand=True)
        right = ttk.Frame(columns, width=330)
        right.pack(side="left", fill="y", padx=(14, 0))
        right.pack_propagate(False)

        # The focus hint sits ABOVE the keyboard, not just implied by it — the
        # investigation's own Slice 3 note is explicit that this page must say
        # so rather than silently expecting focus, since it is the one page in
        # this app that needs it. It also switches text on <FocusIn>/<FocusOut>
        # (below) — before that addition, the only sign a click actually
        # grabbed focus was the summary line changing after a keypress, which
        # left a click that missed the canvas looking identical to one that
        # landed, right up until someone tried typing and got nothing.
        self._focus_hint = ttk.Label(left, text=i18n.t("keytest_focus_hint"),
                                     style="Value.TLabel")
        self._focus_hint.pack(anchor="w", pady=(0, 6))

        self._view = KeyboardView(left, self.profile)
        self._view.pack(fill="both", expand=True)
        # Hover shows what a key does right now (same tooltip shape as the
        # Keys page) — a bonus, not the point of this page, but it is Slice 0
        # ("ship what already exists") for free once a key lights up.
        self._view.set_hover_text(self._hover_text)
        # A flat, unlit look: this page is about key events, not about light.
        self._view.set_preview(1, [(60, 66, 74)], brightness=255)
        self._view.set_preview(1, [(48, 52, 58)], brightness=255, side=True)
        # A canvas does not take keyboard focus on its own; a click grabs it.
        # No `on_key_click` is passed to KeyboardView itself — this page has
        # nothing to do with a mouse click beyond taking focus.
        self._view.bind("<Button-1>", lambda _e: self._view.focus_set(), add="+")
        self._view.bind("<KeyPress>", self._on_key_press, add="+")
        self._view.bind("<FocusIn>", self._on_focus_in, add="+")
        self._view.bind("<FocusOut>", self._on_focus_out, add="+")

        self._summary = ttk.Label(left, text=i18n.t("keytest_idle"),
                                   style="Value.TLabel", justify="left")
        self._summary.pack(anchor="w", fill="x", pady=(8, 0))
        wrap_to_width(self._summary)

        self._build_limits(right)

    def _build_limits(self, parent):
        """The permanent "what this can't confirm" panel — always visible,
        never a tooltip or a collapsed section. See this module's own
        docstring for why it must not be silently absent.
        """
        card = Card(parent, i18n.t("keytest_limits_title"))
        card.pack(fill="both", expand=True)
        body = ScrollFrame(card.body, background=theme.BG_PANEL,
                           body_style="Panel.TFrame")
        body.pack(fill="both", expand=True)
        ttk.Label(body.body, text=i18n.t("keytest_limits"),
                  style="PanelMuted.TLabel", justify="left",
                  wraplength=290).pack(anchor="w")

    # --- data ------------------------------------------------------------------

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
            self._summary.configure(text=i18n.t("keytest_needs_device"))
            return
        self._locked = keymap.locked_keys(key_map)

    # --- focus --------------------------------------------------------------

    def _on_focus_in(self, _event):
        # `foreground=` overrides just the colour on top of "Value.TLabel"'s
        # font/background — no new ttk style needed for one state, and
        # `theme.OK` is already this app's "working as intended" colour
        # (`app.py`'s own status-bar kinds use the same constant).
        self._focus_hint.configure(text=i18n.t("keytest_listening"),
                                   foreground=theme.OK)

    def _on_focus_out(self, _event):
        self._focus_hint.configure(text=i18n.t("keytest_focus_hint"),
                                   foreground=theme.FG)

    # --- key events --------------------------------------------------------

    def _on_key_press(self, event):
        """Tk keysym -> HID usage -> physical KeyId, against the live map.

        Every branch below is a DIFFERENT kind of "cannot show this",
        distinguished in the text rather than collapsed into one generic
        failure — matching this project's convention (`keymap.describe`'s own
        docstring: None does not mean one thing).
        """
        keysym = event.keysym
        resolved = key_input.usage_for_keysym(keysym)
        if resolved is None:
            self._summary.configure(
                text=i18n.t("keytest_unknown_keysym", keysym=keysym))
            return
        page, usage = resolved
        if self._key_map is None:
            self._summary.configure(text=i18n.t("keytest_needs_device"))
            return
        if page == key_input.PAGE_KEYBOARD:
            found = keymap.find_key_for_keyboard_usage(self._key_map, usage)
        else:
            found = keymap.find_key_for_consumer_usage(self._key_map, usage)
        if found is None:
            self._summary.configure(
                text=i18n.t("keytest_no_match", keysym=keysym, usage=usage))
            return
        key_id, layer = found

        self._view.select(key_id)
        key = self._key_by_id.get(key_id)
        label = key.label if key is not None else str(key_id)
        # A 🔒 rather than a plain hit — this is the same locked-key set the
        # Keys page refuses to write to, and Fn+Esc is deliberately never
        # invited here (this module's own docstring), so seeing it lit is
        # exactly where that note belongs, not a silent "matched" like any
        # other key.
        lock = "  🔒" if key_id in self._locked else ""
        pressed = i18n.t("keytest_pressed", keysym=keysym, label=label,
                         id=key_id, lock=lock)
        # Which LAYER matched is worth saying, not just discarding — found
        # missing by `/code-review`: the lookup already searches both layers
        # (a base-layer keysym can resolve to an Fn-layer assignment on some
        # OTHER key), so silently dropping which one answered hid exactly the
        # ambiguity this whole page exists to make visible. Reuses the same
        # `describe_assignment` the hover tooltip calls, so the two cannot
        # disagree about what one live assignment means.
        layer_name = i18n.t("keys_base" if layer == protocol.LAYER_BASE
                           else "keys_fn")
        name = keymap.describe_assignment(self._key_map.get((key_id, layer)),
                                          i18n.LANG)
        currently = i18n.t("keytest_currently", layer=layer_name, name=name)
        self._summary.configure(text=f"{pressed}\n{currently}")

    def _hover_text(self, key):
        """Same shape as the Keys page's tooltip: what this key does right
        now, from the live map — not the static profile, wrong 23 times.
        """
        if self._key_map is None:
            return f"{key.label}  ·  {i18n.t('fn_reading')}"
        locked = "  ·  🔒" if key.id in self._locked else ""
        base = keymap.describe_assignment(
            self._key_map.get((key.id, protocol.LAYER_BASE)), i18n.LANG)
        fn = keymap.describe_assignment(
            self._key_map.get((key.id, protocol.LAYER_FN)), i18n.LANG)
        return (f"{key.label}   (KeyID {key.id}){locked}\n"
                f"{i18n.t('keys_base')}: {base}\n{i18n.t('keys_fn')}: {fn}")

    def destroy(self):
        self._view.stop()
        super().destroy()


def key_test_page(master, app):
    return KeyTestPage(master, app)
