# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Mateus Andrade
"""Decoding what a key does — in particular, what it does with Fn held.

The vendor's device profile records every key's default assignment as a
function id plus five data bytes (`default-fn-function-Id` /
`default-fn-function-data`). The function ids are `FUNCTION_INDEX` from
`docs/vendor-reference/device.js`; the data bytes are, for the two ids that
matter here, a standard USB HID usage:

    CombineKey (6)  -> data = [modifier bitmask, Keyboard-page usage, ...]
    MediaKeys  (8)  -> data = [usage high byte, usage low byte, ...]
                       i.e. usage = (data[0] << 8) | data[1], Consumer page

Everything here is pure lookup — no I/O, no packets. It exists because this
keyboard's Fn layer is not printed on the case and is not in any manual the
owner could find; the keyboard knows it, and so does this file.

Labels are (english, portuguese) pairs so the GUI can show either without a
second table to keep in sync.
"""

# --- FUNCTION_INDEX (device.js) — only the ids this keyboard's Fn layer uses --
FUNCTION_NAMES = {
    1: ("Mouse button", "Botão do mouse"),
    6: ("Key", "Tecla"),
    8: ("Media key", "Tecla de mídia"),
    10: ("Fn modifier", "Modificador Fn"),
    32: ("Mouse cursor", "Cursor do mouse"),
    39: ("Knob rotation", "Rotação do knob"),
    40: ("Knob press", "Clique do knob"),
    41: ("Bluetooth pairing", "Pareamento Bluetooth"),
    42: ("2.4G pairing", "Pareamento 2.4G"),
    44: ("Factory reset", "Reset de fábrica"),
    45: ("Windows / Mac layout", "Layout Windows / Mac"),
    46: ("Show battery level", "Mostrar nível da bateria"),
    48: ("Lighting speed", "Velocidade da iluminação"),
    49: ("Lighting direction", "Direção da iluminação"),
    53: ("Cycle lighting effect", "Trocar efeito de iluminação"),
    54: ("Cycle brightness", "Trocar brilho"),
    55: ("Cycle lighting colour", "Trocar cor da iluminação"),
}

# --- USB HID Keyboard page (0x07) -------------------------------------------
# Complete for what this hardware emits, not just for the Fn layer. The earlier
# version held 20 entries because it was written to describe Fn *shortcuts*,
# where a key that just types its own letter is noise worth dropping. Read the
# base layer with that table and 66 of 79 keys come back undescribed, so the
# filtering moved out of the table (see `describe` vs `fn_shortcuts`) and the
# table became complete.
#
# Values are the standard USB HID Usage Tables, Keyboard/Keypad page 0x07 —
# a public specification, not vendor material. A test asserts this covers every
# usage the device profile actually contains, so a gap fails rather than
# silently rendering a key as unknown.
HID_KEYS = {
    40: ("Enter", "Enter"), 41: ("Esc", "Esc"), 42: ("Backspace", "Backspace"),
    43: ("Tab", "Tab"), 44: ("Space", "Espaço"),
    45: ("-", "-"), 46: ("=", "="), 47: ("[", "["), 48: ("]", "]"),
    49: ("\\", "\\"), 50: ("#", "#"), 51: (";", ";"), 52: ("'", "'"),
    53: ("`", "`"), 54: (",", ","), 55: (".", "."), 56: ("/", "/"),
    57: ("Caps Lock", "Caps Lock"),
    70: ("Print Screen", "Print Screen"), 71: ("Scroll Lock", "Scroll Lock"),
    72: ("Pause / Break", "Pause / Break"), 73: ("Insert", "Insert"),
    74: ("Home", "Home"), 75: ("Page Up", "Page Up"), 76: ("Delete", "Delete"),
    77: ("End", "End"), 78: ("Page Down", "Page Down"),
    79: ("Right arrow", "Seta direita"), 80: ("Left arrow", "Seta esquerda"),
    81: ("Down arrow", "Seta baixo"), 82: ("Up arrow", "Seta cima"),
    83: ("Num Lock", "Num Lock"),
}

# Usages 4-29 are A-Z and 30-39 are 1-9 then 0, contiguously, by definition of
# the HID page. Generated rather than typed out: 36 hand-written lines is 36
# chances at a transposed digit, and the label is the same in both languages.
for _usage, _letter in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ", start=4):
    HID_KEYS[_usage] = (_letter, _letter)
for _usage, _digit in enumerate("1234567890", start=30):
    HID_KEYS[_usage] = (_digit, _digit)
for _n in range(1, 13):                            # 58-69 are F1-F12
    HID_KEYS[57 + _n] = (f"F{_n}", f"F{_n}")
del _usage, _letter, _digit, _n

# --- USB HID Consumer page (0x0C) — the media keys on the F-row --------------
CONSUMER_KEYS = {
    0xB5: ("Next track", "Próxima faixa"),
    0xB6: ("Previous track", "Faixa anterior"),
    0xB7: ("Stop", "Parar"),
    0xCD: ("Play / Pause", "Play / Pausar"),
    0xE2: ("Mute", "Mudo"),
    0xE9: ("Volume up", "Aumentar volume"),
    0xEA: ("Volume down", "Diminuir volume"),
    0x18A: ("Email", "E-mail"),
    0x192: ("Calculator", "Calculadora"),
    0x194: ("My computer", "Meu computador"),
    0x221: ("Search", "Buscar"),
    0x223: ("Browser home", "Página inicial"),
}

# Function ids whose meaning is fully carried by the id itself — the data bytes
# add nothing a user needs to see.
_SELF_DESCRIBING = set(FUNCTION_NAMES) - {1, 6, 8, 32}


def describe(function_id, data):
    """What one assignment does, as an (english, portuguese) pair, or None.

    Takes the raw pair so the live reply from `KEY_CMD_ASSIGN` and the profile's
    stored defaults go through the same decoder — the alternative is two copies
    of the rule that drift apart the first time one is corrected.

    None means "nothing to say": a bare modifier with no usage byte, or a code
    outside the tables here. It does NOT mean "does nothing" — the Fn-shortcut
    list adds its own filtering on top, and that filtering is deliberately not
    part of this function.
    """
    if data is None:                               # a key that did not answer
        return None
    data = list(data) + [0, 0, 0, 0, 0]

    if function_id == 6:                           # CombineKey: a keyboard usage
        usage = data[1]
        if usage == 0:                             # a bare modifier (Fn+Shift)
            return None
        return HID_KEYS.get(usage)

    if function_id == 8:                           # MediaKeys: a consumer usage
        return CONSUMER_KEYS.get((data[0] << 8) | data[1])

    return FUNCTION_NAMES.get(function_id)


def describe_fn(key):
    """What `Fn` + this key does according to the *device profile*, or None.

    Reads the JSON's stored defaults, which is all that is available with no
    keyboard connected. When one is connected, prefer the live reply — this
    keyboard was measured disagreeing with its own profile on 23 assignments.

    None means "nothing worth showing in a shortcut list": no Fn assignment, a
    bare modifier, or a plain letter that only repeats itself. That last filter
    is why this is not the same function as `describe`.
    """
    if key.fn_function_id is None:
        return None
    described = describe(key.fn_function_id, key.fn_function_data)
    if described is None:
        return None
    return described


def is_passthrough(key):
    """True when holding Fn changes nothing for this key.

    Most of this keyboard's Fn layer simply repeats the base layer — Fn+Tab is
    still Tab. Comparing the two assignments directly is exact, where comparing
    the *labels* would need a synonym table ("Up" vs "Up arrow") and would
    still get edge cases wrong.
    """
    return (key.fn_function_id == key.function_id
            and list(key.fn_function_data) == list(key.function_data))


def fn_shortcuts(profile):
    """Every Fn shortcut that actually does something, in the profile's key order.

    Returns [(key_label, (english, portuguese)), ...].
    """
    out = []
    for key in profile.keys:
        if is_passthrough(key):
            continue
        described = describe_fn(key)
        if described is not None:
            out.append((key.label, described))
    return out


def fn_shortcuts_from_map(profile, key_map):
    """The Fn shortcuts this keyboard *actually* has, from a live key map.

    `key_map` is what `lighting.Session.read_key_map` returns:
    {(key_id, layer): assignment or None}. `profile` supplies the key labels,
    which the wire does not carry — a reply says what a key does, never what is
    printed on it.

    Same shape and same filtering as `fn_shortcuts`, and for the same reason: a
    key whose Fn layer repeats its base layer is not a shortcut. The difference
    is the source, and on the unit this was written against the two disagree for
    23 assignments — which is the whole reason this function exists.
    """
    out = []
    for key in profile.keys:
        base = key_map.get((key.id, 0))
        fn = key_map.get((key.id, 1))
        if fn is None:
            continue
        if base is not None and base == fn:        # Fn repeats the base layer
            continue
        described = describe(fn["function_id"], fn["data"])
        if described is not None:
            out.append((key.label, described))
    return out
