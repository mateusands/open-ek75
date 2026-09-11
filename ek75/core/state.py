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


def save(path, regions, keys=None):
    """`regions` is {region_id (int): {"effect", "flag", "speed", "colors", "brightness"}}.

    Either half may be None, meaning "this caller has nothing to say about it",
    in which case whatever the file already holds is carried forward. Both
    directions matter: `--lighting-only` must not discard a saved key map, and
    `--keys-only` must not discard saved lighting. One rule, one place.

    `keys`, when given, is what `lighting.Session.read_key_map` returns:
    {(key_id, layer): {"function_id", "data"} or None}. It is stored under
    "keys" as "<key_id>:<layer>" strings — JSON object keys must be strings and
    `json.dump` raises TypeError on a tuple, so this is not a stylistic choice.

    `keys=None` means "this caller has nothing to say about keys" — **not**
    "delete them". If the file already holds a key map, it is carried over
    untouched. The GUI's backup button and `--lighting-only` both save lighting
    alone to the same default path the CLI uses, and without this, either one
    silently discards a key map the CLI saved there. Destroying a backup is far
    worse than failing to write one, and it would happen with no error.

    An explicitly empty map (`keys={}`) is a different statement and is written
    as such: `load_keys` distinguishes "this file predates key backups" (None)
    from "a key map was recorded and was empty" ({}).
    """
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    if regions is None:
        regions = _carry_forward(load, path) or {}
    if keys is None:
        keys = _carry_forward(load_keys, path)
    payload = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "regions": {str(k): v for k, v in regions.items()},
    }
    if keys is not None:
        payload["keys"] = {f"{key_id}:{layer}": value
                            for (key_id, layer), value in keys.items()}
    with open(path, "w") as f:
        json.dump(payload, f, indent=2)


def _carry_forward(reader, path):
    """What the file already holds, or None when there is nothing to read.

    A backup that does not exist yet, is unreadable, or predates the section
    being asked for is not an error here — it just means there is nothing to
    preserve, and the caller's own data is all there is.
    """
    try:
        return reader(path)
    except (OSError, ValueError, KeyError):
        return None


def load(path):
    """The lighting regions. Signature and return value deliberately unchanged.

    Adding the key map must not alter what `cmd_restore` receives — see
    `load_keys` for the other half. A backup file written before keys existed
    loads here exactly as it always did.
    """
    with open(path) as f:
        payload = json.load(f)
    return {int(k): v for k, v in payload["regions"].items()}


def load_keys(path):
    """The key map, or None when this file does not carry one.

    None is the answer for every backup written before keys were recorded, and
    it has to stay distinguishable from `{}` — "this file predates key backups"
    and "this file recorded a key map that turned out to be empty" call for
    different behaviour from a caller about to write to hardware.
    """
    with open(path) as f:
        payload = json.load(f)
    stored = payload.get("keys")
    if stored is None:
        return None
    out = {}
    for composite, value in stored.items():
        key_id, _, layer = composite.partition(":")
        out[(int(key_id), int(layer))] = value
    return out
