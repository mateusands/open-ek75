# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Mateus Andrade
"""Named configurations, kept on this machine.

This is the vendor's "Profile 1 / 2 / 3", and it is on the PC because that is
where the vendor keeps it too. Both of Dareu's own implementations were checked:
the web driver defines `PFL_CMD_CREATE`, `PFL_CMD_DELETE` and `PFL_CMD_RESET`
and calls none of them, and the Windows app's `CreateProfile` for this model
builds an in-memory object from an embedded template without touching the wire.
See PROTOCOL.md, "Creating profiles 2 and 3".

A profile holds exactly what the vendor's `GetProfileConfig` says one holds —
for a keyboard, the key map and the lighting — so the file format is `state`'s,
unchanged. A backup can be dropped in as a profile and a profile can be restored
as a backup.

What this does NOT give: switching with a key on the keyboard. That needs a real
device profile, and `PFL_CMD_CREATE` stays unsent.
"""
import os

from . import state

DEFAULT_DIR = os.path.join(os.path.dirname(state.DEFAULT_PATH), "profiles")
MAX_NAME = 64


def clean_name(name):
    """Return the name, or raise ValueError.

    **Surrounding whitespace is trimmed. Nothing else is ever repaired.** The
    line between those is whether the repair changes *which file you get*:
    turning `../../.bashrc` into `.bashrc` writes something the user did not
    ask for and says nothing about it, so it raises. Trimming `" Game "` to
    `"Game"` gives the file the user meant, and the alternative is an error
    about characters they cannot see. An earlier version of this docstring
    claimed nothing was repaired, which the `.strip()` below already
    contradicted.

    The rules, and the reason each exists:

    - the first character must be alphanumeric. A leading `-` is read by
      argparse as an option, so `profiles apply -game` would fail with an
      unrecognised-argument error that never mentions profiles; a leading space
      is invisible in every list that shows the name.
    - after that, alphanumerics, space, `-` and `_`. This rejects every path
      separator, `.`, control characters and NUL without listing them.
    - `str.isalnum()` is deliberate rather than an ASCII range: "Perfil Jogo"
      and "Ação" are names people here will use.
    """
    cleaned = str(name).strip()
    if not cleaned:
        raise ValueError("a profile name cannot be empty")
    if len(cleaned) > MAX_NAME:
        raise ValueError(f"a profile name cannot be longer than {MAX_NAME}")
    if not cleaned[0].isalnum():
        raise ValueError("a profile name must start with a letter or a digit")
    for char in cleaned[1:]:
        if not (char.isalnum() or char in " -_"):
            raise ValueError(f"a profile name cannot contain {char!r}")
    return cleaned


def path_for(name, directory=None):
    return os.path.join(directory or DEFAULT_DIR, clean_name(name) + ".json")


def list_profiles(directory=None):
    """Every readable profile name, sorted. A directory that is not there yet
    is not an error — it means none have been saved."""
    directory = directory or DEFAULT_DIR
    try:
        entries = os.listdir(directory)
    except OSError:
        return []
    names = []
    for entry in entries:
        if not entry.endswith(".json"):
            continue
        try:
            names.append(clean_name(entry[:-len(".json")]))
        except ValueError:
            continue                    # something else put a file here
    return sorted(names)


def save(name, regions, keys, directory=None):
    """Write one profile. `regions` or `keys` may be None — see state.save,
    which carries the other half forward rather than dropping it."""
    path = path_for(name, directory)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    state.save(path, regions, keys=keys)
    return path


def delete(name, directory=None):
    """Remove one profile. Missing is FileNotFoundError, not a quiet success:
    a caller that mistyped a name must not be told the delete worked."""
    os.remove(path_for(name, directory))
