# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Mateus Andrade
"""Placeholder pages for the parts of the official software this project does
not implement yet.

They exist so the UI is honest about scope: the feature is named, the exact
command class it needs is named, and the vendor-driver methods to port are
named — rather than a greyed-out button that looks like a bug.
"""
from tkinter import ttk

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
            self._selected = ttk.Label(self, text="", style="Value.TLabel")
            self._selected.pack(anchor="w", pady=(6, 0))

    def _on_key_click(self, key):
        self._selected.configure(
            text=f"KeyID {key.id}  ·  {key.label}  ·  "
                 f"default function {key.function_id} {key.function_data}  ·  "
                 f"Fn function {key.fn_function_id} {key.fn_function_data}")

    def refresh(self):
        pass

    def destroy(self):
        if self._view is not None:
            self._view.stop()
        super().destroy()


def keys_page(master, app):
    return TodoPage(master, app, i18n.t("nav_keys"), i18n.t("keys_todo"),
                    show_keyboard=True)


def macros_page(master, app):
    return TodoPage(master, app, i18n.t("nav_macros"), i18n.t("macros_todo"))
