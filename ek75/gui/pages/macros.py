# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Mateus Andrade
"""What this keyboard says about its macros.

Read-only. Every macro write — creating, deleting, naming, storing the recorded
bytes — is unported, and the page says so rather than showing a control that
cannot work.

The recorded bytes are shown raw because they have not been decoded: the
vendor's web driver passes macro data straight through, and the code that builds
it lives in the site's UI layer, which is not among the files this project has.
Showing a guess at the keystrokes would be inventing a format.
"""
import tkinter as tk
from tkinter import ttk

from .. import i18n, theme
from ..widgets import Card, ScrollFrame


class MacrosPage(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master)
        self.app = app
        self.controller = app.controller
        self._loaded = False

        ttk.Label(self, text=i18n.t("nav_macros"), style="Title.TLabel").pack(anchor="w")
        ttk.Label(self, text=i18n.t("macros_blurb"), style="Muted.TLabel",
                  justify="left").pack(anchor="w", pady=(2, 12))

        card = Card(self, i18n.t("macros_stored"))
        card.pack(fill="both", expand=True)
        self._body = ScrollFrame(card.body, background=theme.BG_PANEL,
                                  body_style="Panel.TFrame")
        self._body.pack(fill="both", expand=True)
        self._status = ttk.Label(self._body.body, text=i18n.t("fn_reading"),
                                  style="PanelMuted.TLabel", justify="left")
        self._status.pack(anchor="w")

        ttk.Label(self, text=i18n.t("macros_writes"), style="Muted.TLabel",
                  justify="left").pack(anchor="w", pady=(12, 0))

    def _alive(self):
        try:
            return bool(self.winfo_exists())
        except tk.TclError:
            return False

    def refresh(self):
        if self._loaded:
            return                      # cached for the session, as elsewhere
        self._loaded = True
        self.controller.submit("read-macros", self._work,
                               on_done=self._show, on_error=self._failed)

    @staticmethod
    def _work(session):
        """One job, not one per macro: each is a multi-packet read, and
        splitting them would interleave with whatever else is queued."""
        found = session.read_macros()
        if not found["ids"]:
            return found["ids"], {}
        return found["ids"], {mid: session.read_macro_data(mid)
                              for mid in found["ids"]}

    def _failed(self, error):
        self._loaded = False            # let a reconnect try again
        if not self._alive():
            return
        self._status.configure(text=i18n.t("fn_needs_device"))
        self.app.report_error(error)

    def _show(self, payload):
        if not self._alive():
            return
        ids, data = payload
        for child in self._body.body.winfo_children():
            child.destroy()

        if ids is None:
            ttk.Label(self._body.body, text=i18n.t("macros_unsupported"),
                      style="PanelMuted.TLabel", justify="left",
                      wraplength=560).pack(anchor="w")
            return
        if not ids:
            ttk.Label(self._body.body, text=i18n.t("macros_none"),
                      style="PanelMuted.TLabel", justify="left",
                      wraplength=560).pack(anchor="w")
            return

        for macro_id in ids:
            row = ttk.Frame(self._body.body, style="Panel.TFrame")
            row.pack(fill="x", pady=(0, 10))
            recorded = data.get(macro_id)
            # The vendor names macros `Macro <id>` too — it reads the name
            # command and throws the answer away. Same string, honest reason.
            ttk.Label(row, text=i18n.t("macros_one", id=macro_id),
                      style="Panel.TLabel").pack(anchor="w")
            if recorded is None:
                ttk.Label(row, text=i18n.t("macros_no_data"),
                          style="PanelMuted.TLabel").pack(anchor="w")
                continue
            ttk.Label(row, text=i18n.t("macros_size", bytes=len(recorded)),
                      style="PanelMuted.TLabel").pack(anchor="w")
            tk.Label(row, text=recorded.hex(" "), bg=theme.BG_SUNKEN,
                     fg=theme.FG, font=theme.FONT_MONO, justify="left",
                     wraplength=540, padx=8, pady=6).pack(anchor="w", pady=(4, 0))


def macros_page(master, app):
    return MacrosPage(master, app)
