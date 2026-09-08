# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Mateus Andrade
"""Device access for the GUI, off the UI thread.

Every command costs up to ~200ms (`command_process` polls the reply up to 20
times, 10ms apart) and a full read of every region costs several of those, so
doing this on tkinter's thread would freeze the window. One worker thread owns
the `core.lighting.Session` — and therefore the file descriptor — and results
come back through `root.after`, which is the documented thread-safe way into
tkinter.

This module builds no packets: it only decides *when* to call `Session`.
"""
import queue
import threading
import tkinter as tk
import traceback

from ..core import device, lighting


class Job:
    __slots__ = ("name", "work", "on_done", "on_error")

    def __init__(self, name, work, on_done=None, on_error=None):
        self.name = name
        self.work = work
        self.on_done = on_done
        self.on_error = on_error


class DeviceError(Exception):
    """A device operation failed in a way worth showing the user."""

    def __init__(self, message, kind="error"):
        super().__init__(message)
        self.kind = kind          # "missing" | "permission" | "error"


class Controller:
    """Serialises device work onto one thread and marshals replies back to Tk."""

    POLL_MS = 30

    def __init__(self, root):
        self.root = root
        self._queue = queue.Queue()
        self._results = queue.Queue()
        self._thread = None
        self._session = None
        self._stopping = threading.Event()
        self._poll_id = None
        self.device_path = None

    # --- lifecycle -----------------------------------------------------------

    def start(self):
        self._thread = threading.Thread(target=self._run, name="ek75-io",
                                        daemon=True)
        self._thread.start()
        self._pump()

    def stop(self):
        self._stopping.set()
        if self._poll_id is not None:
            try:
                self.root.after_cancel(self._poll_id)
            except Exception:      # noqa: BLE001 — the widget may already be gone
                pass
            self._poll_id = None
        self._queue.put(None)
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        self._drain()

    # --- Tk-thread side ------------------------------------------------------

    def _pump(self):
        """Deliver finished jobs' callbacks. Runs on the Tk thread only."""
        self._drain()
        if not self._stopping.is_set():
            self._poll_id = self.root.after(self.POLL_MS, self._pump)

    def _drain(self):
        while True:
            try:
                callback, value = self._results.get_nowait()
            except queue.Empty:
                return
            if callback is None:
                continue
            try:
                callback(value)
            except tk.TclError:
                # The widget the reply was for is gone — the language switch
                # rebuilds every page, and a read submitted just before that
                # lands just after. Nothing to report: the new page issues its
                # own reads.
                pass

    @property
    def connected(self):
        return self._session is not None

    # --- public API ----------------------------------------------------------

    def submit(self, name, work, on_done=None, on_error=None):
        """Run `work(session)` on the worker thread.

        `on_done(result)` and `on_error(DeviceError)` are called back on the Tk
        thread. Jobs run in submission order, so a read queued after a write
        sees the write's effect.
        """
        self._queue.put(Job(name, work, on_done, on_error))

    def drop_connection(self):
        """Close the session so the next job reconnects — used after an I/O error."""
        self._queue.put(Job("disconnect", None))

    # --- worker --------------------------------------------------------------

    def _run(self):
        while not self._stopping.is_set():
            job = self._queue.get()
            if job is None:
                break
            if job.work is None:                     # drop_connection sentinel
                self._close_session()
                continue
            try:
                session = self._ensure_session()
                result = job.work(session)
            except Exception as exc:                 # noqa: BLE001 — reported, not swallowed
                self._close_session()
                self._post_error(job, self._as_device_error(exc))
            else:
                if job.on_done is not None:
                    self._post(job.on_done, result)
        self._close_session()

    def _ensure_session(self):
        if self._session is None:
            path = device.find_device()
            self._session = lighting.Session.open()
            self.device_path = path
        return self._session

    def _close_session(self):
        if self._session is not None:
            try:
                self._session.close()
            except OSError:
                pass
            self._session = None
            self.device_path = None

    @staticmethod
    def _as_device_error(exc):
        if isinstance(exc, DeviceError):
            return exc
        if isinstance(exc, FileNotFoundError):
            return DeviceError(str(exc), kind="missing")
        if isinstance(exc, PermissionError):
            return DeviceError(str(exc), kind="permission")
        if isinstance(exc, OSError):
            return DeviceError(f"{exc.__class__.__name__}: {exc}", kind="error")
        # Anything else is a bug in this code, not the device — keep the
        # traceback rather than reducing it to a one-line message.
        return DeviceError(traceback.format_exc(), kind="error")

    def _post(self, callback, value):
        """Queue a callback for the Tk thread — never touch Tk from here."""
        self._results.put((callback, value))

    def _post_error(self, job, error):
        if job.on_error is not None:
            self._results.put((job.on_error, error))
