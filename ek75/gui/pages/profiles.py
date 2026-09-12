# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Mateus Andrade
"""Named configurations kept on this machine.

The vendor's "Profile 1 / 2 / 3", and on the PC because that is where the vendor
keeps it too — see `core/profiles.py` for the evidence. Applying one is the same
act as restoring a backup, on the same format, so it goes through
`App.apply_saved` rather than growing a second copy of that reporting.
"""
import tkinter as tk
from tkinter import simpledialog, ttk

from ...core import profiles
from .. import i18n, theme
from ..widgets import Card, ScrollFrame, wrap_to_width


class ProfilesPage(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master)
        self.app = app
        self.controller = app.controller
        self._selected = None
        self._busy = False

        ttk.Label(self, text=i18n.t("nav_profiles"),
                  style="Title.TLabel").pack(anchor="w")
        blurb = ttk.Label(self, text=i18n.t("profiles_blurb"), style="Muted.TLabel",
                         justify="left")
        blurb.pack(anchor="w", fill="x", pady=(2, 12))
        wrap_to_width(blurb)

        card = Card(self, i18n.t("profiles_saved"))
        card.pack(fill="both", expand=True)
        self._list_holder = ttk.Frame(card.body, style="Panel.TFrame")
        self._list_holder.pack(fill="both", expand=True)
        self._list = None

        buttons = ttk.Frame(card.body, style="Panel.TFrame")
        buttons.pack(anchor="w", pady=(10, 0))
        self._apply_button = ttk.Button(buttons, text=i18n.t("profiles_apply"),
                                         command=self._on_apply, state="disabled")
        self._apply_button.pack(side="left", padx=(0, 8))
        self._save_button = ttk.Button(buttons, text=i18n.t("profiles_save"),
                                        command=self._on_save)
        self._save_button.pack(side="left", padx=(0, 8))
        self._delete_button = ttk.Button(buttons, text=i18n.t("profiles_delete"),
                                          command=self._on_delete, state="disabled")
        self._delete_button.pack(side="left")

        note = ttk.Label(self, text=i18n.t("profiles_note"), style="Muted.TLabel",
                        justify="left")
        note.pack(anchor="w", fill="x", pady=(12, 0))
        wrap_to_width(note)

    # --- data ----------------------------------------------------------------

    def _alive(self):
        try:
            return bool(self.winfo_exists())
        except tk.TclError:
            return False

    def refresh(self):
        """Re-read the directory every time. Unlike the key map this is a
        local listing, it costs nothing, and the user may have changed it with
        the CLI while the window was open."""
        if not self._alive():
            return
        names = profiles.list_profiles()
        if self._selected not in names:
            self._selected = None
        if self._list is not None:
            self._list.destroy()
        self._list = ScrollFrame(self._list_holder, background=theme.BG_PANEL,
                                  body_style="Panel.TFrame")
        self._list.pack(fill="both", expand=True)
        if not names:
            ttk.Label(self._list.body, text=i18n.t("profiles_none"),
                      style="PanelMuted.TLabel", justify="left",
                      wraplength=520).pack(anchor="w")
        for name in names:
            row = tk.Label(self._list.body, text=name, anchor="w", padx=8, pady=3,
                           cursor="hand2", font=theme.FONT,
                           bg=theme.ACCENT if name == self._selected else theme.BG_PANEL,
                           fg="#ffffff" if name == self._selected else theme.FG)
            row.pack(fill="x", pady=1)
            row.bind("<Button-1>", lambda _e, n=name: self._select(n))
        self._update_buttons()

    def _select(self, name):
        self._selected = name
        self.refresh()

    def _set_busy(self, busy):
        self._busy = busy
        self._update_buttons()

    def _update_buttons(self):
        if not self._alive():
            return
        ready = bool(self._selected) and not self._busy
        self._apply_button.configure(state="normal" if ready else "disabled")
        self._delete_button.configure(state="normal" if ready else "disabled")
        self._save_button.configure(state="disabled" if self._busy else "normal")

    # --- actions -------------------------------------------------------------

    def _on_apply(self):
        if self._selected is None or self._busy:
            return                      # the buttons are a signal, not a lock
        self._set_busy(True)
        self.app.apply_saved(profiles.path_for(self._selected),
                             on_settled=lambda: self._set_busy(False))

    def _on_save(self):
        if self._busy:
            return
        raw = simpledialog.askstring(i18n.t("profiles_save"),
                                      i18n.t("profiles_name_prompt"),
                                      parent=self)
        if raw is None:
            return
        try:
            # Validated in `core`, so the CLI cannot bypass what this enforces
            # and this cannot invent a rule the CLI does not share.
            name = profiles.clean_name(raw)
        except ValueError as error:
            self.app.set_status(str(error), kind="error")
            return

        key_ids = [k.id for k in self.app.profile.keys]
        self._set_busy(True)
        self.app.set_status(i18n.t("profiles_saving", name=name), kind="info")

        def work(session):
            regions = session.snapshot()
            keys = session.read_key_map(key_ids)
            return profiles.save(name, regions, keys)

        def done(_path):
            self._set_busy(False)
            if not self._alive():
                return
            self._selected = name
            self.refresh()
            self.app.set_status(i18n.t("profiles_saved_ok", name=name), kind="ok")

        def failed(error):
            self._set_busy(False)
            if self._alive():
                self.app.report_error(error)

        self.controller.submit("save-profile", work, on_done=done, on_error=failed)

    def _on_delete(self):
        if self._selected is None or self._busy:
            return
        name = self._selected
        try:
            profiles.delete(name)
        except OSError as error:
            self.app.set_status(str(error), kind="error")
            return
        self._selected = None
        self.refresh()
        self.app.set_status(i18n.t("profiles_deleted", name=name), kind="ok")


def profiles_page(master, app):
    return ProfilesPage(master, app)
