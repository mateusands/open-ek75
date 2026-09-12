# Investigation: the official retail manual's Fn-shortcut table

Status: **new first-party source, cross-checked against this project's existing
decompiled findings — some confirm, one genuinely conflicts, one is brand new
ground.** Nothing here has been sent to a keyboard because of this document;
the one concrete new live test it suggests is proposed at the end, not yet
run.

## 0. The source

`Manual - Teclado Gamer Husky Nomadic.pdf` — the printed user manual for the
**HTG800 / "Nomadic"**, the exact retail unit this project targets (per
`README.md`). Supplied by the owner from their own download; not committed to
this repository (it is Husky/KaBuM!'s own copyrighted document, same
treatment as the vendor binaries in `docs/vendor-binaries/` — kept locally,
never in git). What follows is a distillation of the facts in it, the same
way `PROTOCOL.md` distills facts out of the decompiled Windows app rather than
committing that app's own files.

This is a **stronger** source than everything else this project has used so
far for Fn-shortcut behaviour: the decompiled app and `tgdevice.js` describe
what the *configuration software* does; this manual describes what
Husky/Dareu's own documentation says the *keyboard's firmware* does,
independent of whether any host software is even running. Where the two
disagree, that is worth taking seriously rather than picking the one already
on record.

## 1. Spec table (§4) — confirms/updates project assumptions

    Layout:                     ABNT2
    Quantidade de teclas:       81 teclas (75%)
    Tipo de conexão:            Com fio / 2.4G e Bluetooth
    Iluminação:                 RGB
    Modos de iluminação:        6 Modos
    Modelo do Switch:           Gateron G Pro 3.0
    Rollover completo de teclas: Sobreposição de teclas (full N-key rollover)
    Macro:                      Suportado
    Bateria:                    4000mAh

**"Layout: ABNT2" is a correction, not a confirmation.** `ek75/gui/key_input.py`
(this session, before this manual surfaced) carried a comment claiming "this
model's factory legends are the US '~!@#$%^&*()_+' row" — checked against the
keyboard's photo on the manual's cover and this spec row, that is wrong for
the actual retail unit: it ships with **Brazilian ABNT2** keycap legends (a
`Ç` key, a `~^` dead-key next to Enter, visible in the manual's own keyboard
diagram). This does not change `ek75/data/0101.json` — that profile's own
`KeyString` values for the same physical positions are plain US-ASCII
(`[`, `]`, `\`, `;`, `'`, `~`; checked directly), so the underlying vendor
profile data and USB HID usages this project builds packets from are
unaffected. What it does confirm is that `/code-review`'s finding about
`key_input.py`'s digit-row-shift-symbol table (a Brazilian ABNT2 XKB layout
resolves `Shift+6` to something other than `asciicircum`) is **not a
hypothetical edge case for some other user** — it is the realistic case for
this exact product's actual buyers. See §4 below for the fix applied.

## 2. Fn-shortcut table (§5-6) — mostly confirms, one conflict

Transcribed from the manual's own diagrams (not vendor software):

| Shortcut | Manual says | This project's prior finding |
|---|---|---|
| Physical volume knob | Volume +/-, press = pause/play media | Matches `keymap.FUNCTION_NAMES[39]`/`[40]` ("Knob rotation"/"Knob press") — previously undecoded uses, now labelled with real behaviour |
| `Fn`+`-` / `Fn`+`=` | Brilho +/- (brightness) | **New** — neither key was previously suspected of being the brightness shortcut (this session guessed `Fn`+arrows, then `Fn`+Space, both wrong; see §3) |
| `Fn`+`↑`/`↓` | Brilho +/- "(ambos os lados)" — a SECOND brightness shortcut | Consistent with `docs/investigations/brightness-ladder.md`'s original plan, which also guessed arrows |
| `Fn`+`]` | "Mudança modos RGB" (RGB mode change) | Matches `keymap.FUNCTION_NAMES[55]`, `"Cycle lighting colour"` — previously decompiled but **never confirmed bound to any key**; the profile shows it IS (see §5) |
| `Fn`+`F1` | Abrir explorador de Arquivos | Matches `CONSUMER_KEYS[0x194]`, `"My computer"` |
| `Fn`+`F2` | Abrir navegador da internet | Matches `CONSUMER_KEYS[0x223]`, `"Browser home"` |
| `Fn`+`F3` | Abrir e-mail | Matches `CONSUMER_KEYS[0x18A]`, `"Email"` |
| `Fn`+`F4` | Abrir calculadora | Matches `CONSUMER_KEYS[0x192]`, `"Calculator"` |
| `Fn`+`F5` | Somente pausa a mídia (stop) | Matches `CONSUMER_KEYS[0xB7]`, `"Stop"` |
| `Fn`+`F6` | Voltar ao início da mídia (previous) | Matches `CONSUMER_KEYS[0xB6]`, `"Previous track"` |
| `Fn`+`F7` | Reproduzir/Pausar (play/pause) | Matches `CONSUMER_KEYS[0xCD]`, `"Play / Pause"` |
| `Fn`+`F8` | Avançar para próxima mídia (next) | Matches `CONSUMER_KEYS[0xB5]`, `"Next track"` |
| `Fn`+`F9` | **Aumentar** volume do sistema | Profile's HID usage for `F9` is `0xEA`, **"Volume Decrement"** per the USB HID Consumer-page spec — the opposite direction. See §3. |
| `Fn`+`F10` | **Diminuir** volume do sistema | Profile's HID usage for `F10` is `0xE9`, **"Volume Increment"** — also the opposite direction. See §3. |
| `Fn`+`F11` | Silenciar (mute) | Matches `CONSUMER_KEYS[0xE2]`, `"Mute"` |
| `Fn`+`1`/`2`/`3` | Connect Bluetooth device slot 1/2/3 | Matches `docs/investigations/wireless-dongle.md`'s finding, independently, from a different source |
| `Fn`+`Q`, held 3-4s | **Bluetooth** reconnect ("Pressione Fn+Q e mantenha pressionado por 3-4 segundos... indicador de luz irá começar a piscar") | `wireless-dongle.md` had this labelled as **2.4G** pairing (following `keymap.FUNCTION_NAMES[42]`, `"2.4G pairing"`, itself a decompiled name). See §3. |

## 3. Two things that conflict with what was already on record

**F9/F10's volume direction is backwards from the raw HID usage codes.**
USB's HID Usage Tables (Consumer page) fix `0xE9` = Volume Increment, `0xEA`
= Volume Decrement — this is not something this project inferred, it is the
published standard (and matches, independently, the Linux kernel's own
`hid-input.c` mapping `HID_CP_VOLUMEUP` to `0xE9`). This keyboard's profile
assigns `F9` -> usage `0xEA` (decrement) and `F10` -> usage `0xE9`
(increment) — checked directly against `ek75/data/0101.json`, not assumed.
The manual says the opposite: `F9` raises system volume, `F10` lowers it.

One of three things is true, and this project cannot settle which from a
decompile or a document alone: the manual's authors swapped the two labels
when writing it (plausible — the F1-F8/F11 rows all check out, so this
would be an isolated slip); the vendor's own profile data has the two usage
bytes swapped (equally plausible — nothing about `0xE9`/`0xEA` looks
transposed in the surrounding hex, so this would be a firmware/profile
authoring bug, not a decode error here); or the physical keycap silkscreen
for F9/F10 does not match either source. **This is a one-line, five-second
test the owner can run without touching this project at all**: press
`Fn`+`F9`, watch whether the OS's own volume indicator goes up or down, then
the same for `Fn`+`F10`. No `watch`, no terminal, no code — this shortcut's
effect is on the *host OS's* volume, not on anything `CLASS_LIGHTING` or any
other class here reads back.

**`Fn`+`Q`'s wireless mode is labelled differently by two sources.**
`keymap.FUNCTION_NAMES[42]` says `"2.4G pairing"` (from decompiling
`tgdevice.js`'s function-id names); this manual's own "Conexão Bluetooth"
section describes `Fn`+`Q` as the **Bluetooth** reconnect combo. Both may be
correct at once: the keyboard has a 3-position physical switch (`A` / `BT` /
`2.4G`, per the manual's installation diagrams), and the same physical `Fn`+
`Q` combo plausibly does "re-pair whichever radio mode is currently
selected" rather than being hardwired to one mode — in which case
`FUNCTION_NAMES[42]`'s name is simply too narrow, not wrong. Left as an open
question rather than corrected outright, since neither source states the
switch-position behaviour explicitly.

## 4. Fix applied on the strength of this manual alone

`ek75/gui/key_input.py`'s `_DIGIT_SHIFT_SYMBOL` comment claiming a US legend
row is corrected (§1) — this did not need a live test, the manual's own spec
table and keyboard diagram are enough on their own to know the claim was
wrong for the actual retail unit.

## 5. New ground: `Fn`+`[`/`Fn`+`]` (cycle lighting effect / colour) — untested

Checked directly against the profile (not assumed): the `[` key's Fn-layer
`function_id` is **53** (`"Cycle lighting effect"`), and `]`'s is **55**
(`"Cycle lighting colour"`) — both already named in `keymap.FUNCTION_NAMES`
from an earlier decompile pass, but **neither had ever been confirmed bound
to a real key on this keyboard before this manual's own diagram pointed at
`]`.** `[` (53) is not mentioned in the manual at all (only `]` is shown,
labelled "Mudança modos RGB") — plausibly the manual just illustrates one of
a natural next/previous pair and treats both under one icon.

Unlike `brightness-ladder.md`'s brightness shortcuts, **this one is cheaply
and unambiguously testable with `watch`**: cycling the active lighting
*effect* or *colour* is exactly what `read_region`'s `effect`/`colors` fields
already report on every poll, so a real change here would show up as an
ordinary `<- changed: effect` or `<- changed: colors` line — no subtle byte,
no firmware-local state invisible to the protocol, unlike brightness.

**Proposed test, read-only, same shape as every other `watch` experiment in
this project:**

```
python3 main.py watch 1
```

Press `Fn`+`]` a few times, pausing between each; then, separately,
`Fn`+`[`. Record whether `effect` (or `colors`, or both) changes, and in
which direction each key moves it. This would be the first confirmation
that any `LED_CMD_*` shortcut is actually bound to a key on this hardware —
every other candidate this project has tried (`LightingDirection`,
`LightingSpeed`'s Fn binding) came back unbound. Not run yet; this document
only proposes it.
