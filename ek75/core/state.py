# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Mateus Andrade
"""Local persistence: a snapshot of every region's lighting state, so a write
that goes wrong is one command away from being undone.

Deliberately dumb: it stores exactly what device.py + protocol.py produce and
reloads it as-is. No merging, no defaults guessed from thin air.
"""
import json
import os
import time

DEFAULT_PATH = os.path.expanduser("~/.config/open-ek75/backup.json")


def save(path, regions):
    """`regions` is {region_id (int): {"effect", "flag", "speed", "colors", "brightness"}}."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    payload = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "regions": {str(k): v for k, v in regions.items()},
    }
    with open(path, "w") as f:
        json.dump(payload, f, indent=2)


def load(path):
    with open(path) as f:
        payload = json.load(f)
    return {int(k): v for k, v in payload["regions"].items()}
