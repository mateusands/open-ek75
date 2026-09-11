# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Mateus Andrade
"""Device page: what this keyboard is, and the backup/restore safety net.

The official software's home screen also has a wired-connection toggle, a
profile selector and a sleep timer. Those are CLASS_POWER and CLASS_PROFILE,
neither of which is ported — they are listed as missing rather than drawn as
dead controls.
"""
import os
import tkinter as tk
from tkinter import filedialog, ttk

from ...core import device, keymap, layout, state
from .. import i18n, theme
from ..widgets import Card, ScrollFrame

MISSING_FEATURES = [
    ("todo_connection", "CLASS_POWER"),
    ("todo_profiles", "CLASS_PROFILE"),
    # Reading the sleep timer landed; SetTimeToSleep did not, because its effect
    # cannot be seen on the cable (the keyboard does not sleep while on USB), and
    # this project does not ship a write it cannot validate — see PROTOCOL.md.
    ("todo_sleep", "CLASS_POWER — SetTimeToSleep"),
]


class HomePage(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master)
        self.app = app
        self.controller = app.controller
        self.profile = app.profile
        self._rows = {}
        self._build()

    def _build(self):
        ttk.Label(self, text=f"{self.profile.product_name} · {self.profile.model}",
                  style="Title.TLabel").pack(anchor="w")
        ttk.Label(self, text=i18n.t("device_subtitle"),
                  style="Muted.TLabel").pack(anchor="w", pady=(0, 16))

        columns = ttk.Frame(self)
        columns.pack(fill="both", expand=True)

        info = Card(columns, i18n.t("nav_home"))
        info.pack(side="left", fill="both", expand=True, padx=(0, 10))
        for key, label in (("model", i18n.t("device_model")),
                           ("pid", i18n.t("device_pid")),
                           ("node", i18n.t("device_node")),
                           ("firmware", i18n.t("device_firmware")),
                           ("battery", i18n.t("device_battery")),
                           ("sleep", i18n.t("device_sleep")),
                           ("regions", i18n.t("device_regions"))):
            row = ttk.Frame(info.body, style="Panel.TFrame")
            row.pack(fill="x", pady=2)
            ttk.Label(row, text=label, style="PanelMuted.TLabel",
                      width=32, anchor="w").pack(side="left")
            value = ttk.Label(row, text="—", style="Panel.TLabel",
                              font=theme.FONT_MONO)
            value.pack(side="left")
            self._rows[key] = value

        right = ttk.Frame(columns)
        right.pack(side="left", fill="both", expand=True)

        backup = Card(right, f"{i18n.t('backup')} / {i18n.t('restore')}")
        backup.pack(fill="x")
        ttk.Label(backup.body, text=i18n.t("backup_blurb"),
                  style="PanelMuted.TLabel", justify="left").pack(anchor="w",
                                                                  pady=(0, 10))
        buttons = ttk.Frame(backup.body, style="Panel.TFrame")
        buttons.pack(anchor="w")
        ttk.Button(buttons, text=i18n.t("backup"),
                   command=self._on_backup).pack(side="left", padx=(0, 8))
        ttk.Button(buttons, text=i18n.t("restore"),
                   command=self._on_restore).pack(side="left")

        todo = Card(right, i18n.t("not_implemented"))
        todo.pack(fill="both", expand=True, pady=(12, 0))
        for name_key, where in MISSING_FEATURES:
            row = ttk.Frame(todo.body, style="Panel.TFrame")
            row.pack(fill="x", pady=1)
            ttk.Label(row, text=f"· {i18n.t(name_key)}", style="Panel.TLabel",
                      width=34, anchor="w").pack(side="left")
            ttk.Label(row, text=where, style="PanelMuted.TLabel",
                      font=theme.FONT_MONO).pack(side="left")

        self._build_fn_guide()

    def _build_fn_guide(self):
        """The Fn layer, spelled out.

        This keyboard has 38 working Fn shortcuts and prints none of them on the
        case; the owner of the unit this was built against had to search the web
        to learn them. They are all sitting in the vendor's device profile as
        function ids and HID usages, so the app can simply say what they are —
        see core/keymap.py for the decoding.
        """
        card = Card(self, i18n.t("fn_guide"))
        card.pack(fill="both", expand=True, pady=(14, 0))
        ttk.Label(card.body, text=i18n.t("fn_guide_hint"),
                  style="PanelMuted.TLabel", justify="left").pack(anchor="w",
                                                                   pady=(0, 8))

        # The rows are filled by _show_fn_shortcuts once the keyboard answers.
        # Nothing is listed from the vendor profile: 23 of its assignments
        # disagree with this hardware, so a profile-derived list would name the
        # wrong function for 11 of these rows. Better empty than wrong.
        self._fn_grid_holder = ttk.Frame(card.body, style="Panel.TFrame")
        self._fn_grid_holder.pack(fill="both", expand=True)
        self._fn_status = ttk.Label(self._fn_grid_holder, text=i18n.t("fn_reading"),
                                     style="PanelMuted.TLabel", justify="left")
        self._fn_status.pack(anchor="w")
        self._fn_grid = None

    def _load_fn_shortcuts(self):
        self.app.request_key_map(self._on_key_map)

    def _on_key_map(self, key_map):
        if key_map is None:
            self._show_status(i18n.t("fn_needs_device"))
            return
        self._show_fn_shortcuts(keymap.fn_shortcuts_from_map(self.profile, key_map))

    def _show_status(self, text):
        """Replace the list with a message — the exact inverse of showing it.

        Setting the label's text is not enough on a *second* pass: the first
        successful read calls `pack_forget` on it and leaves a populated grid
        behind, so a later failure used to change the text of an invisible
        label and leave the old shortcuts on screen. That is this project's
        worst failure mode in UI form — stale data presented as current, for a
        keyboard that is no longer plugged in.
        """
        if self._fn_grid is not None:
            self._fn_grid.destroy()
            self._fn_grid = None
        self._fn_status.configure(text=text)
        # `winfo_manager()` and not `winfo_ismapped()`: the question is whether
        # pack still manages this label, and ismapped answers a different one —
        # it is False for every widget under a withdrawn or not-yet-drawn
        # toplevel, packed or not.
        if not self._fn_status.winfo_manager():
            self._fn_status.pack(anchor="w")

    def _show_fn_shortcuts(self, shortcuts):
        """Render the live list. Called on the Tk thread by the controller."""
        if self._fn_grid is not None:
            self._fn_grid.destroy()
        self._fn_status.pack_forget()
        columns = 3
        # 38 rows over three columns is more than fits at any sane window
        # height, so the list scrolls rather than being silently truncated.
        scroller = ScrollFrame(self._fn_grid_holder, background=theme.BG_PANEL,
                                body_style="Panel.TFrame")
        scroller.pack(fill="both", expand=True)
        self._fn_grid = scroller
        grid = scroller.body
        for column in range(columns):
            grid.grid_columnconfigure(column, weight=1, uniform="fn")

        per_column = -(-len(shortcuts) // columns)      # ceiling division
        for index, (key_label, labels) in enumerate(shortcuts):
            row = ttk.Frame(grid, style="Panel.TFrame")
            row.grid(row=index % per_column, column=index // per_column,
                     sticky="ew", padx=(0, 18), pady=1)
            combo = tk.Label(row, text=f"Fn + {key_label}", bg=theme.BG_RAISED,
                             fg=theme.FG, font=theme.FONT_MONO,
                             padx=6, pady=1)
            combo.pack(side="left")
            ttk.Label(row, text=labels[0 if i18n.LANG == "en" else 1],
                      style="Panel.TLabel").pack(side="left", padx=(8, 0))

    # --- data ----------------------------------------------------------------

    def refresh(self):
        self._rows["model"].configure(
            text=f"{self.profile.model} / {self.profile.product_name}")
        self._rows["pid"].configure(
            text=f"{device.VID:04x}:{device.PID:04x}")
        self._rows["firmware"].configure(text=self.profile.firmware_version or "—")
        self._rows["node"].configure(text=device.find_device() or "—")

        if self.profile.has_battery:
            self._rows["battery"].configure(text=i18n.t("battery_reading"))
            self.controller.submit(
                "read-battery", lambda session: session.read_battery(),
                on_done=self._show_battery, on_error=self.app.report_error)
        else:
            self._rows["battery"].configure(text=i18n.t("no"))

        self._rows["sleep"].configure(text=i18n.t("battery_reading"))
        self.controller.submit(
            "read-sleep", lambda session: session.read_sleep(),
            on_done=self._show_sleep, on_error=self.app.report_error)

        self._load_fn_shortcuts()

        self.controller.submit(
            "read-regions", lambda session: session.region_ids(),
            on_done=lambda payload: self._rows["regions"].configure(
                text=f"{payload[0]}  ({payload[1]})"),
            on_error=self.app.report_error)

    def _show_battery(self, info):
        """`info` is None when the device did not answer — say so rather than
        leaving the row reading "reading…" forever."""
        if info is None:
            self._rows["battery"].configure(text=i18n.t("battery_unknown"))
            return
        # `status` and `critical` are raw bytes with no documented meaning; the
        # percentage is the only part of this reply that can be shown honestly.
        percent = info["percent"]
        self._rows["battery"].configure(
            text=f"{percent}%" if percent is not None
            else f"{info['level']}/{info['max_level']}")

    def _show_sleep(self, info):
        if info is None:
            self._rows["sleep"].configure(text=i18n.t("battery_unknown"))
        elif not info["enabled"]:
            self._rows["sleep"].configure(text=i18n.t("sleep_disabled"))
        else:
            self._rows["sleep"].configure(
                text=i18n.t("sleep_minutes", minutes=info["minutes"]))

    # --- actions -------------------------------------------------------------

    def _on_backup(self):
        path = filedialog.asksaveasfilename(
            parent=self, title=i18n.t("backup"),
            initialfile=os.path.basename(state.DEFAULT_PATH),
            initialdir=os.path.dirname(state.DEFAULT_PATH) or ".",
            defaultextension=".json")
        if not path:
            return
        self.app.backup_to(path)

    def _on_restore(self):
        path = filedialog.askopenfilename(
            parent=self, title=i18n.t("restore"),
            initialdir=os.path.dirname(state.DEFAULT_PATH) or ".",
            filetypes=[("JSON", "*.json"), ("All files", "*")])
        if not path:
            return

        def work(session):
            return session.restore(state.load(path))

        self.controller.submit(
            "restore", work,
            on_done=lambda _r: self.app.on_restored(path),
            on_error=self.app.report_error)
