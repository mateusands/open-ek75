# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Mateus Andrade
"""Tk keysym name -> USB HID (page, usage) — for a live key-press test screen.

This is public X11/XKB input-stack data, not vendor material and not a packet
byte: it never reaches the keyboard, so CLAUDE.md's golden rule 2 ("never send
a byte you have not validated") does not apply to it — nothing here is ever
sent. See `docs/investigations/key-test.md` for the investigation this comes
from: the official app's own key-test screen works the same way, translating
a Win32 virtual-key code through the identical public HID tables this
project's `keymap.py` already carries for the opposite direction (describing a
`CLASS_KEY` assignment).

Scoped to exactly the keys `ek75/data/0101.json` lists for THIS keyboard, not
the full X11 keysym space — but "the keys this keyboard has" includes its Fn
layer, not only the base layer. An earlier version of this file mapped only
each physical key's unshifted identity and claimed Pause/Scroll_Lock/Home/End
had "no physical key for any of them" — false: this board's profile assigns
them to Fn+P/Fn+O/Fn+K/Fn+L (and Print Screen to Fn+I), exactly the same way
its arrow keys and F-keys double as Page Up/Page Down. `Insert`, `Num_Lock`
and a `Menu`/`Application` key are the ones genuinely absent from BOTH layers
(checked directly against every key's `default-function-*` AND
`default-fn-function-*` pair) and have no entry here on purpose.

`Fn` has no entry and never will: it is a controller-local modifier with no
USB HID usage of its own — the keyboard's microcontroller decides which
*other* usage to emit, and nothing ever puts "Fn" on the wire to be seen. See
PROTOCOL.md's `CLASS_KEY` section and `keymap.py`'s own docstring.
"""
from ..core import keymap

PAGE_KEYBOARD = 7           # USB HID Usage Tables, Keyboard/Keypad page
PAGE_CONSUMER = 12          # USB HID Usage Tables, Consumer page

KEYSYM_TO_USAGE = {}

# Letters: generated like `keymap.HID_KEYS` does for the same reason — 52
# hand-typed lines (upper and lower keysym spellings) is 52 chances at a
# transposed usage. Shift does not change the HID usage, only whether the OS
# reports the upper- or lower-case keysym for the same physical key, so both
# spellings map to the same (page, usage).
for _usage, _letter in enumerate("abcdefghijklmnopqrstuvwxyz", start=4):
    KEYSYM_TO_USAGE[_letter] = (PAGE_KEYBOARD, _usage)
    KEYSYM_TO_USAGE[_letter.upper()] = (PAGE_KEYBOARD, _usage)
del _usage, _letter

# Digits: the digit keysym for the unshifted press, and the shifted symbol
# the SAME physical key sends under `ek75/data/0101.json`'s own (plain
# US-ASCII) `KeyString` labels for this row — both are the same HID usage,
# only the modifier byte differs, and this table does not carry modifier
# state. An earlier version of this comment claimed "this model's factory
# legends are the US row", which the retail unit's own printed manual
# (`docs/investigations/manual-fn-shortcuts.md` §1) contradicts directly:
# its spec sheet says "Layout: ABNT2" and its keyboard diagram shows
# Brazilian legends (a Ç key, a ~^ dead key) — the vendor PROFILE data this
# project builds packets from is unaffected (it is plain US-ASCII either
# way, checked directly), but the physical keycap and, more importantly,
# the OS-side XKB layout a real owner runs are not.
#
# KNOWN GAP (found by /code-review, sharpened by the manual above): X11
# resolves a keysym from the ACTIVE XKB layout, not from the HID usage the
# firmware sent, so on a Brazilian ABNT2 layout — not a hypothetical other
# user, but this exact product's realistic buyer — Shift+6 reports a
# keysym other than "asciicircum" here, and this table wrongly answers
# "unrecognized" for a key that did send a valid usage. Not fixed here: the
# real fix is resolving by physical `keycode` instead of by keysym for this
# class of key, which is a different mechanism belonging to Slice 3's
# design, not a patch to this pure-keysym table — see
# docs/investigations/key-test.md §5's note on this.
_DIGIT_SHIFT_SYMBOL = {
    "1": "exclam", "2": "at", "3": "numbersign", "4": "dollar",
    "5": "percent", "6": "asciicircum", "7": "ampersand", "8": "asterisk",
    "9": "parenleft", "0": "parenright",
}
for _usage, _digit in enumerate("1234567890", start=30):
    KEYSYM_TO_USAGE[_digit] = (PAGE_KEYBOARD, _usage)
    KEYSYM_TO_USAGE[_DIGIT_SHIFT_SYMBOL[_digit]] = (PAGE_KEYBOARD, _usage)
del _usage, _digit, _DIGIT_SHIFT_SYMBOL

for _n in range(1, 13):                            # F1-F12, usages 58-69
    KEYSYM_TO_USAGE[f"F{_n}"] = (PAGE_KEYBOARD, 57 + _n)
del _n

KEYSYM_TO_USAGE.update({
    "Return": (PAGE_KEYBOARD, 40),
    "Escape": (PAGE_KEYBOARD, 41),
    "BackSpace": (PAGE_KEYBOARD, 42),
    "Tab": (PAGE_KEYBOARD, 43),
    "space": (PAGE_KEYBOARD, 44),
    "minus": (PAGE_KEYBOARD, 45), "underscore": (PAGE_KEYBOARD, 45),
    "equal": (PAGE_KEYBOARD, 46), "plus": (PAGE_KEYBOARD, 46),
    "bracketleft": (PAGE_KEYBOARD, 47), "braceleft": (PAGE_KEYBOARD, 47),
    "bracketright": (PAGE_KEYBOARD, 48), "braceright": (PAGE_KEYBOARD, 48),
    "backslash": (PAGE_KEYBOARD, 49), "bar": (PAGE_KEYBOARD, 49),
    "semicolon": (PAGE_KEYBOARD, 51), "colon": (PAGE_KEYBOARD, 51),
    "apostrophe": (PAGE_KEYBOARD, 52), "quotedbl": (PAGE_KEYBOARD, 52),
    "grave": (PAGE_KEYBOARD, 53), "asciitilde": (PAGE_KEYBOARD, 53),
    "comma": (PAGE_KEYBOARD, 54), "less": (PAGE_KEYBOARD, 54),
    "period": (PAGE_KEYBOARD, 55), "greater": (PAGE_KEYBOARD, 55),
    "slash": (PAGE_KEYBOARD, 56), "question": (PAGE_KEYBOARD, 56),
    "Caps_Lock": (PAGE_KEYBOARD, 57),
    "Delete": (PAGE_KEYBOARD, 76),

    # Confirmed as valid Tk keysym names on this system for the SAME two
    # physical keys (checked directly: both bind successfully) — different
    # XKB versions report one spelling or the other for Page Up/Page Down, so
    # both are mapped rather than betting on a single one.
    "Prior": (PAGE_KEYBOARD, 75), "Page_Up": (PAGE_KEYBOARD, 75),
    "Next": (PAGE_KEYBOARD, 78), "Page_Down": (PAGE_KEYBOARD, 78),

    "Left": (PAGE_KEYBOARD, 80), "Right": (PAGE_KEYBOARD, 79),
    "Up": (PAGE_KEYBOARD, 82), "Down": (PAGE_KEYBOARD, 81),

    # Fn-layer usages this board's profile actually assigns (Fn+I/O/P/K/L) —
    # found missing here by /code-review, which caught that this file's
    # earlier claim ("no physical key for Pause/Scroll_Lock/Home/End") was
    # simply wrong: those four ARE real Fn-shortcuts on this hardware, the
    # same way Fn+PageUp/PageDown already were. These four keysym names are
    # unambiguous, decades-old core X11 keysyms (keysymdef.h), not the kind of
    # spelling fork Prior/Page_Up turned out to be, so no live probe is
    # claimed for them the way there was for that pair.
    "Print": (PAGE_KEYBOARD, 70), "Scroll_Lock": (PAGE_KEYBOARD, 71),
    "Pause": (PAGE_KEYBOARD, 72), "Home": (PAGE_KEYBOARD, 74),
    "End": (PAGE_KEYBOARD, 77),

    # Modifiers: the HID usage a MACRO's recorded byte carries
    # (`keymap.HID_MODIFIER_USAGES`), not `CLASS_KEY`'s CombineKey bitmask
    # (`keymap.HID_MODIFIERS`) — the two are genuinely different encodings for
    # the same physical key; see `HID_MODIFIER_USAGES`'s own docstring. This
    # board has no R-Win key (confirmed by reading its live key map — no
    # assignment carries bit 7 of CombineKey's modifier byte), so `Super_R`
    # has no entry here either, on purpose.
    "Control_L": (PAGE_KEYBOARD, 0xE0), "Shift_L": (PAGE_KEYBOARD, 0xE1),
    "Alt_L": (PAGE_KEYBOARD, 0xE2), "Super_L": (PAGE_KEYBOARD, 0xE3),
    "Control_R": (PAGE_KEYBOARD, 0xE4), "Shift_R": (PAGE_KEYBOARD, 0xE5),
    "Alt_R": (PAGE_KEYBOARD, 0xE6),

    # The three dedicated media keys this keyboard has on its base layer.
    "XF86AudioMute": (PAGE_CONSUMER, 0x0E2),
    "XF86AudioRaiseVolume": (PAGE_CONSUMER, 0x0E9),
    "XF86AudioLowerVolume": (PAGE_CONSUMER, 0x0EA),

    # Eight more Consumer-page functions this board's Fn layer assigns to
    # F1-F8 (My Computer, Browser Home, Mail, Calculator, Stop, Previous,
    # Play/Pause, Next track) — also found missing by the same review pass
    # that caught the keyboard-page gap above. Names are the standard XF86
    # keysyms every Linux desktop's XKB rules already define for these HID
    # Consumer-page usages (X.Org's XF86keysym.h) — well-established, but
    # not verified with a live probe on this machine the way Prior/Page_Up
    # were, since a stock display here does not surface a way to bind them.
    "XF86MyComputer": (PAGE_CONSUMER, 0x194),
    "XF86HomePage": (PAGE_CONSUMER, 0x223),
    "XF86Mail": (PAGE_CONSUMER, 0x18A),
    "XF86Calculator": (PAGE_CONSUMER, 0x192),
    "XF86AudioStop": (PAGE_CONSUMER, 0xB7),
    "XF86AudioPrev": (PAGE_CONSUMER, 0xB6),
    "XF86AudioPlay": (PAGE_CONSUMER, 0xCD),
    "XF86AudioNext": (PAGE_CONSUMER, 0xB5),
})


def usage_for_keysym(keysym):
    """(page, usage) for a Tk keysym name, or None.

    None covers three different things, deliberately not distinguished here —
    a caller that needs to explain "why" to a user has to ask a different
    question than this function answers:
      - a keysym this keyboard has no physical key for, on either layer
        (`Insert`, `Num_Lock`, `Menu`, ...)
      - `Fn`, which has no HID usage at all, on any keyboard
      - a keysym this table simply has not been taught yet
    """
    return KEYSYM_TO_USAGE.get(keysym)
