# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Mateus Andrade
"""The user's own preferences — not device state.

Kept apart from `state.py` on purpose: that file is a snapshot of what the
*keyboard* holds and exists to undo a bad write. This one is about the app
(language, and whatever else accumulates), lives next to it in
~/.config/open-ek75/, and losing it costs nothing but a preference.

Reads never raise: a missing, unreadable or corrupt file yields the defaults,
because failing to start over a settings file would be worse than ignoring it.
"""
import json
import os

DEFAULT_PATH = os.path.expanduser("~/.config/open-ek75/settings.json")

DEFAULTS = {
    "language": "en",
}


def load(path=DEFAULT_PATH):
    """Stored settings merged over the defaults."""
    settings = dict(DEFAULTS)
    try:
        with open(path, encoding="utf-8") as f:
            stored = json.load(f)
    except (OSError, ValueError):
        return settings
    if isinstance(stored, dict):
        settings.update({k: v for k, v in stored.items() if k in DEFAULTS})
    return settings


def save(settings, path=DEFAULT_PATH):
    """Write the settings, keeping only known keys. Returns True on success."""
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({k: v for k, v in settings.items() if k in DEFAULTS},
                      f, indent=2)
    except OSError:
        return False
    return True


def update(path=DEFAULT_PATH, **changes):
    """Change some settings and persist the result."""
    settings = load(path)
    settings.update({k: v for k, v in changes.items() if k in DEFAULTS})
    save(settings, path)
    return settings
