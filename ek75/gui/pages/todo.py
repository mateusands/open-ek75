# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Mateus Andrade
"""Placeholder pages for the parts of the official software this project does
not implement yet.

They exist so the UI is honest about scope: the feature is named, the exact
command class it needs is named, and the vendor-driver methods to port are
named — rather than a greyed-out button that looks like a bug.
"""
from tkinter import ttk

from ...core import keymap, protocol
from .. import i18n, theme
from ..keyboard_view import KeyboardView


class TodoPage(ttk.Frame):
    def __init__(self, master, app, title, body, show_keyboard=False):
        super().__init__(master)
        self.app = app
        self._view = None

        ttk.Label(self, text=title, style="Title.TLabel").pack(anchor="w")
        ttk.Label(self, text=i18n.t("not_implemented"),
                  style="Heading.TLabel").pack(anchor="w", pady=(2, 10))
        ttk.Label(self, text=body, style="Muted.TLabel",
                  justify="left").pack(anchor="w")

        if show_keyboard:
            ttk.Label(self, text=i18n.t("layout_note"),
                      style="Muted.TLabel").pack(anchor="w", pady=(16, 4))
            self._view = KeyboardView(self, app.profile,
                                      on_key_click=self._on_key_click)
            self._view.pack(fill="both", expand=True)
            # A neutral, unlit look: this page previews the layout, not an effect.
            self._view.set_preview(1, [(60, 66, 74)], brightness=255)
            self._view.set_preview(1, [(48, 52, 58)], brightness=255, side=True)
            self._selected = ttk.Label(self, text=i18n.t("keys_click"),
                                        style="Value.TLabel")
            self._selected.pack(anchor="w", pady=(6, 0))
            self._key_map = None

    def _on_key_click(self, key):
        """Show what the KEYBOARD says this key does, not what the profile says.

        The two disagree on this hardware for 23 assignments, and the profile is
        the vendor's description of the PID rather than of the unit in front of
        you — which is the entire question this page exists to answer.
        """
        if self._key_map is None:
            self._selected.configure(text=i18n.t("fn_reading"))
            return
        parts = [f"KeyID {key.id}  ·  {key.label}"]
        for layer, name in ((protocol.LAYER_BASE, i18n.t("keys_base")),
                            (protocol.LAYER_FN, i18n.t("keys_fn"))):
            got = self._key_map.get((key.id, layer))
            if got is None:
                continue
            described = keymap.describe(got["function_id"], got["data"])
            text = (described[0 if i18n.LANG == "en" else 1] if described
                    else f"fid={got['function_id']} {got['data']}")
            parts.append(f"{name}: {text}")
        parts.append(f"({i18n.t('keys_live')})")
        self._selected.configure(text="   ·   ".join(parts))

    def refresh(self):
        if self._view is None or self._key_map is not None:
            return                      # the window caches it for the session
        self.app.request_key_map(self._store_key_map)

    def _store_key_map(self, key_map):
        self._key_map = key_map

    def destroy(self):
        if self._view is not None:
            self._view.stop()
        super().destroy()


def keys_page(master, app):
    return TodoPage(master, app, i18n.t("nav_keys"), i18n.t("keys_todo"),
                    show_keyboard=True)


def macros_page(master, app):
    return TodoPage(master, app, i18n.t("nav_macros"), i18n.t("macros_todo"))
