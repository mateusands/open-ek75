# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Mateus Andrade
"""The main window: a sidebar, one page per feature area, and a status line.

Safety (CLAUDE.md, "Hardware safety"): the lighting state lives in the
keyboard's persistent memory, so the first thing this window does after
connecting is take a backup if none exists. Every write the UI can perform is
undoable from the Device page.
"""
import os
import tkinter as tk
from tkinter import messagebox, ttk

from ..core import layout, state
from . import i18n, theme
from .controller import Controller
from .pages.home import HomePage
from .pages.lighting import LightingPage
from .pages.keys import keys_page
from .pages.key_test import key_test_page
from .pages.macros import macros_page
from .pages.profiles import profiles_page

NAV = [
    ("home", "⌂", "nav_home"),
    ("keys", "⌨", "nav_keys"),
    ("keytest", "⌖", "nav_keytest"),
    ("lighting", "✺", "nav_lighting"),
    ("macros", "Ⓜ", "nav_macros"),
    ("profiles", "▤", "nav_profiles"),
]


class App(tk.Tk):
    def __init__(self, pid=layout.DEFAULT_PID):
        super().__init__()
        self.title(i18n.t("app_title"))
        self.geometry("1120x680")
        self.minsize(940, 600)
        theme.apply(self)

        self.profile = layout.load(pid)
        self.controller = Controller(self)
        self.controller.start()

        self._pages = {}
        self._nav_buttons = {}
        self._current = None
        self._auto_backup_done = False
        self._permission_warned = False
        # The key map is 166 reads (~1.6 s). It belongs to the window, not to a
        # page: two pages want it, the worker queue is serial, and a per-page
        # read would sweep the keyboard twice for the same answer.
        self.key_map = None
        self._key_map_waiters = []

        self._build()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(100, self._first_connect)

    # --- layout --------------------------------------------------------------

    def _build(self, initial="home"):
        header = tk.Frame(self, bg=theme.ACCENT, height=44)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="open-ek75", bg=theme.ACCENT, fg="#ffffff",
                 font=("Sans", 13, "bold")).pack(side="left", padx=18)
        self._header_note = tk.Label(header, text="", bg=theme.ACCENT,
                                     fg="#ffe2d5", font=theme.FONT_SMALL)
        self._header_note.pack(side="right", padx=18)
        self._build_language_switch(header)

        body = ttk.Frame(self)
        body.pack(fill="both", expand=True)

        sidebar = tk.Frame(body, bg=theme.BG_PANEL, width=64)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        self._content = ttk.Frame(body, padding=16)
        self._content.pack(side="left", fill="both", expand=True)

        for name, glyph, label_key in NAV:
            button = tk.Label(sidebar, text=glyph, bg=theme.BG_PANEL,
                              fg=theme.FG_MUTED, font=("Sans", 18),
                              pady=14, cursor="hand2")
            button.pack(fill="x")
            button.bind("<Button-1>", lambda _e, n=name: self.show(n))
            self._add_tooltip(button, i18n.t(label_key))
            self._nav_buttons[name] = button

        status = tk.Frame(self, bg=theme.BG_PANEL, height=28)
        status.pack(fill="x", side="bottom")
        status.pack_propagate(False)
        self._status = tk.Label(status, text=i18n.t("searching"),
                                bg=theme.BG_PANEL, fg=theme.FG_MUTED,
                                font=theme.FONT_SMALL, anchor="w")
        self._status.pack(side="left", padx=14)

        self._pages["home"] = HomePage(self._content, self)
        self._pages["lighting"] = LightingPage(self._content, self)
        self._pages["keys"] = keys_page(self._content, self)
        self._pages["keytest"] = key_test_page(self._content, self)
        self._pages["macros"] = macros_page(self._content, self)
        self._pages["profiles"] = profiles_page(self._content, self)
        # Always the device page on launch: it is the one that says what is
        # connected and lists the Fn shortcuts, which is what someone opening
        # the app cold most likely wants.
        self.show(initial)

    def _build_language_switch(self, header):
        """EN / PT-BR, in the header, remembered across restarts."""
        box = tk.Frame(header, bg=theme.ACCENT)
        box.pack(side="right", padx=(0, 6))
        for code, label in i18n.available():
            selected = code == i18n.LANG
            button = tk.Label(
                box, text=label, font=theme.FONT_SMALL, padx=8, pady=2,
                cursor="hand2",
                bg="#ffffff" if selected else theme.ACCENT,
                fg=theme.ACCENT if selected else "#ffe2d5")
            button.pack(side="left", padx=1)
            button.bind("<Button-1>", lambda _e, c=code: self._set_language(c))

    def _set_language(self, code):
        if not i18n.set_language(code):
            return
        self._rebuild()

    def _rebuild(self):
        """Re-create every widget in the new language.

        Each string is read once, when its widget is built, so switching
        language means building again. The controller and its open device
        handle deliberately survive: only the UI is language-dependent.
        """
        current = self._current or "home"
        for page in self._pages.values():
            page.destroy()
        self._pages.clear()
        self._nav_buttons.clear()
        self._current = None
        for child in self.winfo_children():
            child.destroy()
        self._build(initial=current)
        if self.controller.device_path:
            self._header_note.configure(text=self.controller.device_path)

    def _add_tooltip(self, widget, text):
        """A one-label tooltip; ttk has none and the sidebar is icon-only."""
        tip = {"window": None}

        def show(_event):
            if tip["window"] is not None:
                return
            window = tk.Toplevel(self)
            window.wm_overrideredirect(True)
            tk.Label(window, text=text, bg=theme.BG_RAISED, fg=theme.FG,
                     font=theme.FONT_SMALL, padx=8, pady=3).pack()
            x = widget.winfo_rootx() + widget.winfo_width() + 6
            y = widget.winfo_rooty() + 8
            window.wm_geometry(f"+{x}+{y}")
            tip["window"] = window

        def hide(_event):
            if tip["window"] is not None:
                tip["window"].destroy()
                tip["window"] = None

        widget.bind("<Enter>", show, add="+")
        widget.bind("<Leave>", hide, add="+")

    def show(self, name):
        if self._current is not None:
            self._pages[self._current].pack_forget()
        self._current = name
        self._pages[name].pack(fill="both", expand=True)
        for key, button in self._nav_buttons.items():
            selected = key == name
            button.configure(fg=theme.ACCENT if selected else theme.FG_MUTED,
                             bg=theme.BG if selected else theme.BG_PANEL)
        self._pages[name].refresh()

    # --- connection ----------------------------------------------------------

    def _first_connect(self):
        self.controller.submit(
            "connect", lambda session: True,
            on_done=lambda _ok: self._on_connected(),
            on_error=self.report_error)

    def _on_connected(self):
        path = self.controller.device_path or "?"
        self._header_note.configure(text=path)
        self.set_status(i18n.t("connected", path=path), kind="ok")
        # refresh first: `Controller` runs one job at a time in submission
        # order, so queueing the automatic backup ahead of it would leave the
        # device card reading "reading…" behind a 166-key sweep.
        self._pages[self._current].refresh()
        self._auto_backup()

    def request_key_map(self, callback):
        """Call `callback(key_map)` once the map is available, reading it at most
        once per session. Callers that arrive while a read is in flight are
        queued rather than starting a second one."""
        if self.key_map is not None:
            callback(self.key_map)
            return
        self._key_map_waiters.append(callback)
        if len(self._key_map_waiters) > 1:
            return                                   # a read is already in flight
        self.controller.submit(
            "read-key-map",
            lambda session: session.read_key_map(
                [k.id for k in self.profile.keys]),
            on_done=self._key_map_ready,
            on_error=self._key_map_failed)

    def _key_map_ready(self, key_map):
        self.key_map = key_map
        waiters, self._key_map_waiters = self._key_map_waiters, []
        for callback in waiters:
            callback(key_map)

    def _key_map_failed(self, error):
        waiters, self._key_map_waiters = self._key_map_waiters, []
        for callback in waiters:
            callback(None)
        self.report_error(error)

    def _auto_backup(self):
        """Take one backup the first time this machine connects, never overwrite.

        "Never overwrite" used to mean "do nothing at all if the file exists",
        which silently skipped every install that already had one: those files
        predate key backups, so the key map would never be captured on exactly
        the machines that had been using this longest. The file existing is
        still enough to skip the *lighting* half — overwriting a saved setting
        with the current one is the loss this guard exists to prevent — but a
        file with no key map in it still gets one. `state.save` carries the
        lighting forward untouched.
        """
        if self._auto_backup_done:
            return
        self._auto_backup_done = True

        if not os.path.exists(state.DEFAULT_PATH):
            self.backup_to(state.DEFAULT_PATH, automatic=True)
            return
        try:
            if state.load_keys(state.DEFAULT_PATH) is not None:
                return                               # already has both halves
        except (OSError, ValueError, KeyError):
            return                                   # unreadable: leave it alone
        self.backup_to(state.DEFAULT_PATH, automatic=True, keys_only=True)

    # --- shared actions used by pages ---------------------------------------

    def backup_to(self, path, automatic=False, keys_only=False, on_settled=None):
        """Save the lighting and the key map, the same two halves the CLI saves.

        `keys_only` passes None for the lighting, which `state.save` reads as
        "nothing to say about it" and carries forward rather than replacing.
        """
        key_ids = [k.id for k in self.profile.keys]

        def work(session):
            # Both reads happen before the file is touched, so a keyboard
            # unplugged half way through leaves the old backup intact instead of
            # a file with half a key map in it.
            regions = None if keys_only else session.snapshot()
            keys = session.read_key_map(key_ids)
            state.save(path, regions, keys=keys)
            return path

        def done(saved):
            if on_settled is not None:
                on_settled()
            self.set_status(
                i18n.t("auto_backup" if automatic else "backup_saved", path=saved),
                kind="ok")

        def failed(error):
            # `on_settled` runs on both paths or the caller's button stays
            # disabled for the rest of the session after one unplugged cable.
            if on_settled is not None:
                on_settled()
            self.report_error(error)

        self.controller.submit("backup", work, on_done=done, on_error=failed)

    def apply_saved(self, path, on_settled=None, label=None):
        """Put a saved file back — a backup or a profile, which are one format.

        Lives here rather than on a page because two pages do it and the half
        that is easy to get wrong is the *reporting*: a lighting restore that
        worked and a key restore that partly failed must not be summarised as
        one word. Two copies of that would be two places to fix it.

        Returns False when the file could not be read, having already said so.
        """
        try:
            keys = state.load_keys(path)             # None for an older backup
            regions = state.load(path)
        except (OSError, ValueError, KeyError) as error:
            # Not `report_error`: that one reads `error.kind` and speaks about
            # the device. A file the user picked that is not a backup needs a
            # different message and would otherwise crash the reporter itself.
            self.set_status(
                i18n.t("backup_unreadable", name=os.path.basename(path),
                       detail=type(error).__name__), kind="error")
            if on_settled is not None:
                on_settled()
            return False

        # Said before the job starts: writing 166 assignments takes about 17
        # seconds, and a live but silent window that long reads as a hang.
        self.set_status(
            label or i18n.t("restoring_keys" if keys else "restoring"),
            kind="info")

        def work(session):
            return session.restore(regions), (session.restore_key_map(keys)
                                               if keys else [])

        def done(results):
            if on_settled is not None:
                on_settled()
            self.on_restored(path)
            lighting_results, key_results = results
            bad_regions = [r for r, ok in lighting_results if not ok]
            bad_keys = [k for k, ok in key_results if not ok]
            if bad_regions or bad_keys:
                self.set_status(
                    i18n.t("restore_partial", regions=len(bad_regions),
                           keys=len(bad_keys)), kind="warn")

        def failed(error):
            if on_settled is not None:
                on_settled()
            self.report_error(error)

        self.controller.submit("restore", work, on_done=done, on_error=failed)
        return True

    def on_restored(self, path):
        self.set_status(i18n.t("restored", path=path), kind="ok")
        # The cached map was read before the restore wrote a different one over
        # it. Dropping it makes the next reader ask the keyboard again; keeping
        # it would leave the Fn guide describing shortcuts that are no longer
        # there, which is the failure this project treats as the worst kind.
        self.key_map = None
        self._pages[self._current].refresh()

    def set_status(self, text, kind="info"):
        colour = {"ok": theme.OK, "warn": theme.WARN,
                  "error": theme.ERROR}.get(kind, theme.FG_MUTED)
        self._status.configure(text=text, fg=colour)

    def report_error(self, error):
        if error.kind == "missing":
            self.set_status(i18n.t("disconnected"), kind="error")
            self._header_note.configure(text="")
        elif error.kind == "permission":
            self.set_status(i18n.t("permission_short"), kind="error")
            # The fix is one command the user has to run themselves, so it goes
            # in a dialog they cannot miss — but only once per session.
            if not self._permission_warned:
                self._permission_warned = True
                messagebox.showwarning(i18n.t("permission_title"),
                                       i18n.t("permission_hint"), parent=self)
        else:
            self.set_status(str(error).strip().splitlines()[-1], kind="error")

    # --- shutdown ------------------------------------------------------------

    def _on_close(self):
        for page in self._pages.values():
            page.destroy()
        self.controller.stop()
        self.destroy()


def run(argv=None):
    """Entry point for `open-ek75 gui` / `python3 main.py gui`."""
    app = App()
    app.mainloop()
    return 0
