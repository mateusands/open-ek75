# Investigation: the official retail manual's Fn-shortcut table

Status: **new first-party source, cross-checked against this project's existing
decompiled findings — most confirm, one (F9/F10's volume direction) was
tested live and found to be the MANUAL's own error, one (`Fn`+`Q`'s wireless
mode) stays open by the owner's own call (not worth a live test), and one
(`Fn`+`[`/`Fn`+`]`, cycle lighting effect/colour) was tested live and fully
confirmed — see §5.** Nothing has been sent to a keyboard because of this
document; every state change described here was produced by the owner's own
keypresses, read back with `watch`, no write.

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
| `Fn`+`F9` | "Aumentar" volume do sistema — **tested live, wrong**: it lowers | Matches the profile's HID usage `0xEA`, "Volume Decrement". See §3. |
| `Fn`+`F10` | "Diminuir" volume do sistema — **tested live, wrong**: it raises | Matches the profile's HID usage `0xE9`, "Volume Increment". See §3. |
| `Fn`+`F11` | Silenciar (mute) | Matches `CONSUMER_KEYS[0xE2]`, `"Mute"` |
| `Fn`+`F12` | "Alternar entre modo Windows e Mac (as luzes indicadoras piscarão para confirmar a mudança)" | Matches `keymap.FUNCTION_NAMES[45]`, `"Windows / Mac layout"` — checked directly against the profile: `F12`'s `fn_function_id` is `45`. Previously decompiled, never before tied to a specific key or a manual description |
| `Fn`+`1`/`2`/`3` | Connect Bluetooth device slot 1/2/3 | Matches `docs/investigations/wireless-dongle.md`'s finding, independently, from a different source |
| `Fn`+`Q`, held 3-4s | **Bluetooth** reconnect ("Pressione Fn+Q e mantenha pressionado por 3-4 segundos... indicador de luz irá começar a piscar") | `wireless-dongle.md` had this labelled as **2.4G** pairing (following `keymap.FUNCTION_NAMES[42]`, `"2.4G pairing"`, itself a decompiled name). See §3 — accepted as the manual's own claim, not live-tested (owner's call: these are firmware-local behaviours with no packet this project ever sends either way, so a printed manual is sufficient documentation without a hardware round-trip). |

## 3. Two things that conflict with what was already on record

**F9/F10's volume direction — SETTLED, the manual is wrong, this project's
decode was right.** Tested directly on the owner's OS volume indicator (no
`watch`, no terminal — this shortcut is a plain Consumer-page media key, it
never touches `CLASS_LIGHTING` or anything else this project reads back):
`Fn`+`F9` **lowers** the volume, `Fn`+`F10` **raises** it. That matches the
profile's own HID usage bytes exactly (`F9` -> `0xEA`, Volume Decrement;
`F10` -> `0xE9`, Volume Increment — the published USB HID Consumer-page
standard, and `keymap.CONSUMER_KEYS`'s existing labels) and contradicts the
manual, which states the opposite pairing. Of the three possibilities §3
originally listed, it was the manual's own printed labels that were
transposed — an isolated slip, not a pattern (its F1-F8/F11 rows all
checked out against this project's independent decode). No code or doc
correction needed here beyond this note: `keymap.py`'s labels were already
right.

**`Fn`+`Q`'s wireless mode is labelled differently by two sources.**
`keymap.FUNCTION_NAMES[42]` says `"2.4G pairing"` (from decompiling
`tgdevice.js`'s function-id names); this manual's own "Conexão Bluetooth"
section describes `Fn`+`Q` as the **Bluetooth** reconnect combo. Both may be
correct at once: the keyboard has a 3-position physical switch (`A` / `BT` /
`2.4G`, per the manual's installation diagrams), and the same physical `Fn`+
`Q` combo plausibly does "re-pair whichever radio mode is currently
selected" rather than being hardwired to one mode — in which case
`FUNCTION_NAMES[42]`'s name is simply too narrow, not wrong. **Owner's
call: not worth a live test** — unlike F9/F10 (a one-second listen to the
system volume), settling this would need actually pairing a second
Bluetooth device, for a question that changes nothing this project sends
or reads. Left open in `FUNCTION_NAMES[42]`'s label rather than corrected,
with the manual's own, more specific claim (Bluetooth reconnect) recorded
here as the accepted description of what `Fn`+`Q` does in practice.

## 4. Fix applied on the strength of this manual alone

`ek75/gui/key_input.py`'s `_DIGIT_SHIFT_SYMBOL` comment claiming a US legend
row is corrected (§1) — this did not need a live test, the manual's own spec
table and keyboard diagram are enough on their own to know the claim was
wrong for the actual retail unit.

## 5. `Fn`+`?`/`Fn`+`]` (cycle lighting effect / colour) — colour confirmed, effect key UNCERTAIN

**Correction — this section originally said `[` (not `]`) carries function 53
("Cycle lighting effect"), sourced from `ek75/data/0101.json`'s STATIC
profile.** That source is exactly the one `PROTOCOL.md`'s own "The device
profile disagrees with the keyboard — 23 times" section warns against: a
live sweep of THIS keyboard, done in an earlier session, found `[` is an
ordinary bracket key on the real hardware with no Fn function at all, and
that the real, measured binding for function 53 is `Fn`+`\` and `Fn`+`R-Alt`
— not `Fn`+`[`. `]` -> 55 ("Cycle lighting colour") is the one row that
happens to match between both sources.

So which physical key actually drove the effect-cycling test below is not
yet settled — asked, not yet answered. `]`'s role (cycle colour) stands
either way, confirmed independently by the profile, the earlier live sweep,
and this test all agreeing.

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
`LightingSpeed`'s Fn binding) came back unbound.

**Run, `watch 1`, no write:**

    [22:08:24] Wave    flag=0 speed=0 brightness=120 colors=[]
    [22:08:26] Wave    ...    colors=[(255, 0, 0)]        <- changed: colors
    [22:08:27] Reactive ...   colors=[]                   <- changed: effect, colors
    [22:08:28] Starlit
    [22:08:29] Rotate
    [22:08:30] RainbowW
    [22:08:30] SteadyStream
    [22:08:30] AreaReactive
    [22:08:31] LineReactive
    [22:08:31] Scanning
    [22:08:32] Heartbeat
    [22:08:32] Breathing
    [22:08:33] Static
    [22:08:34] Neon
    [22:08:35] RunningLight
    [22:08:35] Wave                                       <- back to the start

Two distinct, real functions are visible here, told apart by which fields
moved: the first change touched `colors` only, `effect` staying `Wave`
(function 55, "cycle lighting colour" — on `Wave`, cycling colour turns on
a fixed red rather than the effect's own automatic rainbow, without leaving
the effect); every change after that touched `effect` only, cycling forward
through 14 real firmware effects and wrapping back to `Wave` exactly where
it started (function 53, "cycle lighting effect" — `colors` resets to empty
on each step, since most of these effects carry no fixed colour of their
own). `brightness` stayed at `120` throughout — both shortcuts are isolated
from brightness and from each other.

**`]` -> 55 is confirmed as the key for the colour change** (agrees with the
profile, the earlier live sweep, and this test). **Which key drove the
effect change (53) is not confirmed** — this test proves function 53 is
real and bound to *something*, but not, on its own, to `[` specifically;
see the correction at the top of this section. Along with `_brightnessLevel`
in `brightness-ladder.md`, this is nonetheless the second confirmed case of
a genuine `CLASS_LIGHTING` state change happening entirely through a
firmware-local Fn shortcut, readable after the fact through the same
`LED_CMD_ATTRIBUTE` poll this project already uses for everything else.

**A second attempt at isolating the key (asking for `Fn`+`[` and `Fn`+`\`
one at a time) did not settle it either.** `brightness` started changing
mid-run without having been asked for, and stray characters (`/`, `.`, `;`,
`ç`) reached the terminal as literal text — the same failure shape as
`brightness-ladder.md`'s own Fn-timing attempts (a combo not held long
enough registers as the bare key instead), compounded here by a real
possibility this project has flagged before and never resolved: the
physical key this document called "`\`, the key next to Enter" assumes a
US/ANSI position, and the owner's actual keyboard is ABNT2
(`manual-fn-shortcuts.md` §1) — the key in that position, or its label, may
simply not match what a US layout would call it.

**Left open, low priority, not worth another round of remote testing.**
Both functions (53, 55) are confirmed real and working (§5's first test);
only the exact physical key for 53 is unsettled, and two attempts at
narrowing it by relayed keypresses have both failed the same way for
reasons unrelated to the function itself. Closing this needs either the
owner testing alone with the keyboard in hand (one key, isolated, held
deliberately), or is simply not worth closing — nothing in this project
depends on knowing which physical key it is, only on the function being
real, which is settled.
