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
from ..widgets import Card, ScrollFrame, wrap_to_width

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
                           ("profiles", i18n.t("device_profiles")),
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
        # The string used to carry its own hand-placed \n breaks, tuned to
        # English's shorter phrasing; a ttk.Label with no wraplength does not
        # wrap on its own, so the Portuguese translation's longer words ran
        # past those fixed breaks and clipped mid-word at the card's edge. A
        # fixed wraplength alone is still a guess about the column's width —
        # wrap_to_width reads what pack() actually gave it instead.
        backup_note = ttk.Label(backup.body, text=i18n.t("backup_blurb"),
                                style="PanelMuted.TLabel", justify="left")
        backup_note.pack(anchor="w", fill="x", pady=(0, 10))
        wrap_to_width(backup_note)
        buttons = ttk.Frame(backup.body, style="Panel.TFrame")
        buttons.pack(anchor="w")
        self._backup_button = ttk.Button(buttons, text=i18n.t("backup"),
                                          command=self._on_backup)
        self._backup_button.pack(side="left", padx=(0, 8))
        self._restore_button = ttk.Button(buttons, text=i18n.t("restore"),
                                           command=self._on_restore)
        self._restore_button.pack(side="left")

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
        fn_hint = ttk.Label(card.body, text=i18n.t("fn_guide_hint"),
                           style="PanelMuted.TLabel", justify="left")
        fn_hint.pack(anchor="w", fill="x", pady=(0, 8))
        wrap_to_width(fn_hint)

        # The rows are filled by _show_fn_shortcuts once the keyboard answers.
        # Nothing is listed from the vendor profile: 23 of its assignments
        # disagree with this hardware, so a profile-derived list would name the
        # wrong function for 11 of these rows. Better empty than wrong.
        self._fn_grid_holder = ttk.Frame(card.body, style="Panel.TFrame")
        self._fn_grid_holder.pack(fill="both", expand=True)
        self._fn_status = ttk.Label(self._fn_grid_holder, text=i18n.t("fn_reading"),
                                     style="PanelMuted.TLabel", justify="left")
        self._fn_status.pack(anchor="w", fill="x")
        wrap_to_width(self._fn_status)
        self._fn_grid = None

    def _load_fn_shortcuts(self):
        self.app.request_key_map(self._on_key_map)

    def _on_key_map(self, key_map):
        if not self._alive():
            return
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
            # fill="x", matching how this label was originally packed: without
            # it, wrap_to_width's <Configure> binding stops receiving events
            # for the parent's real width (an unfilled label sizes to its own
            # content, not the cavity) and the wraplength freezes at whatever
            # it last was — silently reviving the exact clipping bug this
            # label was the original report for.
            self._fn_status.pack(anchor="w", fill="x")

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

    def _alive(self):
        """False once this page's widgets are gone.

        A device job can finish after `App._rebuild` has destroyed the page that
        asked for it — switching language during a read is enough, and a key-map
        restore takes ~17 s, which is a long time to hold a widget still. The
        callback then configures a dead widget and Tk raises. Every callback
        that touches a widget checks this first.
        """
        try:
            return bool(self.winfo_exists())
        except tk.TclError:                          # the interpreter is going away
            return False

    def _set_busy(self, busy):
        """Lock the backup/restore buttons while one of their jobs is running.

        `Controller` runs one job at a time in submission order, so a second
        click does not corrupt anything — it queues another full 17 s key-map
        write behind the first, with no sign on screen that anything is
        happening. Disabling is the honest signal.
        """
        if not self._alive():
            return
        mode = "disabled" if busy else "normal"
        for button in (self._backup_button, self._restore_button):
            button.configure(state=mode)

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

        self._rows["profiles"].configure(text=i18n.t("battery_reading"))
        self.controller.submit(
            "read-profiles", lambda session: session.read_profiles(),
            on_done=self._show_profiles, on_error=self.app.report_error)

        self.controller.submit(
            "read-regions", lambda session: session.region_ids(),
            on_done=lambda payload: self._alive() and self._rows[
                "regions"].configure(text=f"{payload[0]}  ({payload[1]})"),
            on_error=self.app.report_error)

    def _show_battery(self, info):
        """`info` is None when the device did not answer — say so rather than
        leaving the row reading "reading…" forever."""
        if not self._alive():
            return
        if info is None:
            self._rows["battery"].configure(text=i18n.t("battery_unknown"))
            return
        # `status` and `critical` are raw bytes with no documented meaning; the
        # percentage is the only part of this reply that can be shown honestly.
        percent = info["percent"]
        self._rows["battery"].configure(
            text=f"{percent}%" if percent is not None
            else f"{info['level']}/{info['max_level']}")

    def _show_profiles(self, info):
        """Which profiles the keyboard holds, and which one is live.

        The vendor's Windows app offers Profile 1/2/3 and this keyboard reports
        one. Saying "1 of 1" and leaving it there would read like a bug in this
        software, so the row says the other slots have to be created — which is
        a write this project does not send.
        """
        if not self._alive():
            return
        ids, active = info["ids"], info["active"]
        if ids is None and active is None:
            self._rows["profiles"].configure(text=i18n.t("battery_unknown"))
            return
        listed = "?" if ids is None else ", ".join(str(i) for i in ids) or "—"
        shown = i18n.t("profiles_active", listed=listed,
                       active="?" if active is None else active)
        if ids is not None and len(ids) == 1:
            shown += "  " + i18n.t("profiles_only_one")
        self._rows["profiles"].configure(text=shown)

    def _show_sleep(self, info):
        if not self._alive():
            return
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
        self._set_busy(True)
        self.app.backup_to(path, on_settled=lambda: self._set_busy(False))

    def _on_restore(self):
        path = filedialog.askopenfilename(
            parent=self, title=i18n.t("restore"),
            initialdir=os.path.dirname(state.DEFAULT_PATH) or ".",
            filetypes=[("JSON", "*.json"), ("All files", "*")])
        if not path:
            return
        # `App.apply_saved` owns reading the file, the worker job, the
        # 17-second warning and the per-half failure report — the Profiles page
        # does the same thing to the same format and one copy of that reporting
        # is one place to fix it.
        self._set_busy(True)
        self.app.apply_saved(path, on_settled=lambda: self._set_busy(False))
