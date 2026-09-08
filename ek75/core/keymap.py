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

# --- USB HID Keyboard page (0x07) — the usages this keyboard's Fn layer emits -
# Only the ones that differ from simply repeating the key's own letter; the
# pass-throughs are filtered out before display anyway.
HID_KEYS = {
    40: ("Enter", "Enter"), 41: ("Esc", "Esc"), 42: ("Backspace", "Backspace"),
    43: ("Tab", "Tab"), 44: ("Space", "Espaço"), 57: ("Caps Lock", "Caps Lock"),
    70: ("Print Screen", "Print Screen"), 71: ("Scroll Lock", "Scroll Lock"),
    72: ("Pause / Break", "Pause / Break"), 73: ("Insert", "Insert"),
    74: ("Home", "Home"), 75: ("Page Up", "Page Up"), 76: ("Delete", "Delete"),
    77: ("End", "End"), 78: ("Page Down", "Page Down"),
    79: ("Right arrow", "Seta direita"), 80: ("Left arrow", "Seta esquerda"),
    81: ("Down arrow", "Seta baixo"), 82: ("Up arrow", "Seta cima"),
    83: ("Num Lock", "Num Lock"),
}

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


def describe_fn(key):
    """What `Fn` + this key does, as an (english, portuguese) pair, or None.

    None means "nothing worth showing": either the key has no Fn assignment, or
    its Fn layer just repeats the key itself (Fn+E typing an `e`), which is the
    common case on this keyboard and would bury the useful rows in noise.
    """
    fid = key.fn_function_id
    if fid is None:
        return None
    data = list(key.fn_function_data) + [0, 0, 0, 0, 0]

    if fid == 6:                                   # CombineKey: a keyboard usage
        usage = data[1]
        if usage == 0:                             # a bare modifier (Fn+Shift)
            return None
        named = HID_KEYS.get(usage)
        if named is None:
            return None                            # a plain letter/digit: noise
        return named

    if fid == 8:                                   # MediaKeys: a consumer usage
        return CONSUMER_KEYS.get((data[0] << 8) | data[1])

    if fid in _SELF_DESCRIBING:
        return FUNCTION_NAMES[fid]

    return FUNCTION_NAMES.get(fid)


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
