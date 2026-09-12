# Investigation: does `_brightnessLevel` = `{0, 70, 120, 190, 255}` back the `Fn`+`↑`/`↓` brightness step?

Scope: read-only static analysis of the decompiled Windows app
(`docs/vendor-binaries/extracted/app/`, proprietary, never committed) plus
`PROTOCOL.md`/`ek75/core/*` in this repo. **No bytes were sent to the
keyboard.** No test was run. No production file was touched.

Tooling: `dnfile`/`dncil` via the session's scratchpad scripts —
`callsites.py <dll> <name>...` (who calls a method, resolving
`call`/`callvirt`/`newobj`/`ldftn` operands against MethodDef/MemberRef/
MethodSpec — not a string search) and a short ad-hoc script built on the same
`dnfile` API to read `FieldRva` table rows directly and cross-check field
owners/names. `callsites.py` was validated against a known positive
(`ToString`, which returns dozens of hits in `DeviceBase.dll` and the main
`.exe`) before any negative result below was trusted.

## 1. Does the inference hold?

**Partially — CONFIRMED at the data/API-shape level, INFERRED at the
"this is what `Fn`+`↑`/`↓` drives" level.**

**CONFIRMED** (read directly from `Products/TK51G0101.dll`, independent of
the user's own extraction): the `FieldRva` table has exactly two rows for
this assembly. One of them backs a field named `_brightnessLevel` on type
`DareuProducts.TK51G0101`:

```
DareuProducts.TK51G0101::.ctor:
    ldc.i4.5
    newarr    System.Byte        ; new byte[5]
    dup
    ldtoken   field 0x04000373   ; the FieldRva-backed static blob
    call      RuntimeHelpers.InitializeArray
    stfld     _brightnessLevel
```

and the raw bytes at that RVA are `00 46 78 BE FF` = **0, 70, 120, 190, 255**
— exactly the five values reported. `TK51G0101::get_BrightnessLevel` is a
one-line getter, `ldarg.0; ldfld _brightnessLevel; ret` — it does no
computation, no clamping, no percent conversion. It just exposes the array.

**CONFIRMED**: `DeviceBase.dll` declares a static helper type
`DareuProducts.LedInterface` (a sealed, abstract-flagged utility class, not a
C# `interface`) with four methods that consume exactly this shape — "given a
`byte[]` ladder and a current value, find the next/previous rung":

- `GetNextBrightnessLevel(current)` — scans the array for the first entry
  `> current`; if found, returns it; if `current` is already `>=` every rung,
  **clamps** to the last element (255).
- `GetNextBrightnessLevelLoop(current)` — identical scan, but **wraps** to
  the first element (0) instead of clamping when there is no higher rung.
- `GetPreviousBrightnessLevel(current)` — scans backward for the first entry
  `<= current`, i.e. the rung at or below; clamps to the first element (0) at
  the bottom.
- `GetPreviousBrightnessLevelLoop(current)` — same, but wraps to the last
  element (255) at the bottom instead of clamping.

This is unambiguous "cycle through a step table, with a clamp variant and a
wrap variant" logic — there is no other plausible reading of that IL. So the
five-value array is **designed** as a stepping ladder, by the vendor's own
code, for exactly the operation `Fn`+`↑`/`↓` is described as doing
(`BrightnessAdjust`, "cycles the brightness" — `PROTOCOL.md` line ~703, ~1206).
That much does not need hardware confirmation; it is what the bytes and the
IL say.

**INFERRED, not confirmed — and this is the part the task asked to test
hardest**: whether these four helper methods, or this array, are actually
*reached* when the physical `Fn`+`↑`/`↓` combo fires on a TK51G0101. Static
analysis found **no call site for any of the four methods, anywhere**:

```
$ callsites.py <dll> GetNextBrightnessLevel GetNextBrightnessLevelLoop \
               GetPreviousBrightnessLevel GetPreviousBrightnessLevelLoop
```
run against every managed module shipped with the app —
`Products/TK51G0101.dll`, `Products/TK50S.dll`, `Products/TK597.dll`,
`UiLib.dll`, `DataControl.dll`, `ToolLib.dll`, `DeviceBase.dll` itself, and
`Central de Controle Husky.exe` — returned zero hits in all eight. The same
run for `get_BrightnessLevel`/`set_BrightnessLevel` also found nothing
outside the getter's own one-line body. `TgApi.dll` is a native (non-.NET)
PE — `file` and its `MZ`-but-no-CLR-header confirm it is not a managed
assembly at all, so it is a real "does not apply" and not a tool failure;
`dnfile` cannot and should not parse it, consistent with this repo's own
`docs/vendor-binaries/README.md` ("`TgApi.dll` is native... was not needed").

A raw byte search (ASCII and UTF-16LE) for the literal strings
`GetNextBrightnessLevel`, `GetPreviousBrightnessLevel`, `BrightnessLevel` and
`_brightnessLevel` across the `.exe` and every `.dll` found these names
**only inside `TK51G0101.dll`'s own metadata** (where the type/field/method
definitions themselves live) — zero occurrences anywhere else, including the
`.exe`'s embedded resources (which is where the compiled XAML/BAML for the UI
lives, per this repo's own `vendor-binaries/README.md`). That rules out the
two easiest ways this tool's negative could be wrong — a XAML
`Click="GetNextBrightnessLevel"`-style binding, or a
`System.Reflection.MethodInfo.Invoke("GetNextBrightnessLevel")` call — being
invisible to a call/callvirt/newobj/ldftn walk (both would still need the
literal name as a UTF-8/UTF-16 string somewhere in the binary, since neither
XAML markup nor `Type.GetMethod` compiles a token reference).

So: in **this build** of the Windows app (v1.0.0.4, 2025-08-15, see
`docs/vendor-binaries/README.md`), the stepping helpers exist, are shaped
exactly like the answer to "what does `Fn`+`↑`/`↓` do", and are provably
**not invoked by the shipped Windows app** through any path this analysis can
see. Two readings are both consistent with that:

1. The firmware handles `Fn`+`↑`/`↓` entirely on its own — the keyboard just
   *reports* `BrightnessAdjust` (`54`) to the host for informational/keymap
   purposes (exactly as `PROTOCOL.md`'s existing "The data bytes of the
   lighting functions, as observed" table already shows: `Fn`+`↑` reports
   `[4, 0, 0, 0, 0]`, `Fn`+`↓` reports `[4, 0, 1, 0, 0]`) while the actual
   brightness byte changes inside the keyboard's own firmware memory, never
   touching this Windows-side helper at all. The Windows app's copy of the
   ladder would then be vestigial — carried over into this product's plugin
   DLL for a reason lost to this build (maybe planned UI, maybe firmware
   parity data), but dead in the app itself.
2. Some other, still-unfound code path calls it — e.g. through a delegate
   built by a mechanism this walk's opcode set does not cover, or logic that
   is genuinely absent from this decompile because it lives in a resource
   this project doesn't have (a different installer version, a firmware
   blob, `TgApi.dll`'s native code, which was out of scope here per this
   project's own README).

Static analysis cannot distinguish these two, and the task's own instruction
not to write to the keyboard means this document cannot either. Section 3
gives the one experiment that can.

One more data point, run for context and not conclusive on its own: the
family's other two product plugins, `TK50S.dll` and `TK597.dll`, have **no**
`BrightnessLevel` field, property or method at all — their single `FieldRva`
blob is a differently-shaped table unrelated to brightness. So this ladder
is not a copy-pasted vendor-wide convention showing up idly in every product;
it was written specifically for `TK51G0101` (this device's own plugin),
which is mildly *for* the "it's meant for something" reading, even though it
doesn't resolve whether that something ships.

## 2. What the app uses these values for

Everything found says: **stepping only, never a slider bound and never a
value clamp on a write path.**

- `get_BrightnessLevel` is a plain field accessor — TK51G0101 does not use it
  to compute a percentage, does not reference it from a `Min`/`Max` binding,
  and (per §1) nothing in the shipped app calls the getter at all outside its
  own body.
- The percent brightness **slider** the user actually sees in the app is a
  *different* mechanism entirely, already documented in `PROTOCOL.md`
  ("Brightness: a 0-255 byte, shown as 1-100") and in this project's own
  `docs/vendor-binaries/README.md`: the compiled XAML for
  `pages/pagemodule/pageledregiontg.baml` declares the brightness slider as
  `Minimum="1" Maximum="100"`, and `sliderBrightness.Value =
  (int)((float)Brightness / 255f * sliderBrightness.Maximum)` converts the
  raw 0-255 byte to that 1-100 scale. That slider has **nothing to do** with
  the five-value array — it is a linear percent mapping over the full
  0-255 range, matching this repo's own `brightness_to_percent`/
  `brightness_from_percent` (`ek75/core/protocol.py`), not a 5-step
  quantization.
- So the two brightness representations in the vendor app are:
  1. **Continuous 0-255, shown as 1-100** — the slider, read/write via
     `LED_CMD_BRIGHTNESS`, already implemented and confirmed on hardware in
     this repo.
  2. **A discrete 5-rung ladder `{0, 70, 120, 190, 255}`** — consumed only by
     `GetNext/PreviousBrightnessLevel(Loop)`, which return "the next/previous
     rung given a current value", the textbook shape of a step-button or
     keyboard-shortcut handler, not a display concern (nothing reads the
     array to draw tick marks or labels — a slider using it would show 5
     positions, and the XAML says 100, not 5).

There is no third use found — no packet builder anywhere reads the array to
clamp an outgoing write, and no report-parsing code reads it to decode an
incoming HID report.

## 3. Exact procedure to confirm on hardware — no write required

This mirrors the experiment `PROTOCOL.md` already ran for the `Speed`
1-3 range (`### \`Speed\` is 1-3, not 0-255 — confirmed by the firmware
itself`), which is the project's own precedent for "settle a stepped range by
watching, without writing a byte."

**Command** (run from the repo root, needs the hidraw permission already set
up per the `local-environment` skill):

```
python3 main.py watch 1
```

(`1` = `REGION_KEYS`, the per-key matrix — the same region the `Speed`
experiment used, and the region `Fn`+`↑`/`↓`'s `BrightnessAdjust` report
already correlates with in `PROTOCOL.md`'s function-id table.)

**Keys to press, one at a time, pausing a beat between each so `watch`'s
polling loop (default interval 0.4s) has time to print a line:**

1. `Fn`+`↓` several times in a row (5-6 presses) — walk toward the bottom.
2. `Fn`+`↑` several times in a row (6-7 presses) — walk past the top.
3. A couple more `Fn`+`↓` / `Fn`+`↑` presses to see the behaviour right at
   the ends.

**What to watch for:** the tool prints a line only when `brightness` (or any
other field) changes, with `<- changed: brightness` on the diff. Record the
full sequence of `brightness=` values it prints.

**What each outcome would prove:**

- **The sequence of values is exactly `0, 70, 120, 190, 255` (in some
  order/subset, moving up with `Fn`+`↑` and down with `Fn`+`↓`)** — closes
  the loop: CONFIRMS the array is the live ladder, resolves which pair of
  helpers is used (does it clamp at the ends — stops changing after reaching
  255 or 0 — or wrap — jumps from 255 back to 0, or 0 back to 255?),
  distinguishing `GetNextBrightnessLevel` from `...Loop`. Update
  `PROTOCOL.md`'s "`_brightnessLevel`: the Fn brightness ladder, probably"
  section (drop the "probably"), and this would be the moment to transcribe
  the ladder into `ek75/core/vendor_tables.py` alongside the other
  transcribed tables, with a docstring citing this exact observation as the
  reference (per this project's own evidence-tier convention: "replayed and
  visually confirmed" vs. "read back" vs. a live capture).
- **`brightness` never changes at all, no matter how many times `Fn`+`↑`/`↓`
  are pressed** — this would mean either the shortcut is not bound on this
  unit/profile (as happened with `LightingSpeed` before the profile-hiding
  discovery documented in `PROTOCOL.md`'s "the profile simply does not show
  it"), or `Fn`+`↑`/`↓` does something entirely unrelated to region 1's
  brightness field on this firmware revision. Worth also trying `watch 4` (the
  side light region) in case the shortcut targets that region instead, or the
  currently-active region rather than a fixed one.
- **`brightness` changes, but to values outside `{0, 70, 120, 190, 255}`**
  — would falsify the inference outright: the array would be confirmed dead
  data (matches reading #1 in §1), and whatever stepping the firmware
  actually does is unrelated to this DLL's ladder. That would be worth its
  own line in `PROTOCOL.md` next to the existing "Inferred, not confirmed"
  note, same honesty rule as everywhere else in this project.
- **`brightness` changes smoothly by some other fixed step (not matching the
  ladder) across the full 0-255 range** — would suggest the firmware cycles
  brightness by a constant delta unrelated to the Windows app's ladder
  entirely (i.e. the array is coincidentally-shaped leftover data, not a
  step table the firmware also implements).

No `set`, `restore`, `off`, or `brightness` CLI command is needed or should
be run for this — `watch` only issues the read-only `LED_CMD_BRIGHTNESS`
GET request in a loop; the state change being observed is produced by the
owner pressing the keyboard's own physical shortcut, which is the same
"replayed and visually confirmed" tier of evidence `PROTOCOL.md` already uses
for `Speed`.

## 3.1. Live attempt on real hardware — INCONCLUSIVE, not closed

Run on the owner's actual TK51G/EK75, `watch 1` and `watch 4` both open,
2026-09-11:

- **`Fn`+`↑`/`Fn`+`↓` (arrow keys): zero change** to `brightness` on either
  region, across two separate rounds. Checked the profile's own
  `default-fn-function-Id` for the arrow keys directly (not assumed): both
  arrows carry `function_id 6` (CombineKey) on their Fn layer with the SAME
  keyboard-page usage as their base layer (82/81) — i.e. this profile
  assigns arrows **no Fn function at all**. The read-only round-trip itself
  is confirmed working correctly (it re-issues `LIT_CMD_GET_BRIGHTNESS`
  every poll, not a cached value), so a flat `brightness=153`/`255` the
  whole time is a real "nothing changed", not a client bug.
- **Visually, `Fn`+`↓` made the Caps Lock/battery/wifi status indicators
  blink white** — not backlight color, not brightness. This lines up with
  `keymap.FUNCTION_NAMES[46]`, `"Show battery level"`, already in this
  codebase from the decompile — but the profile assigns function 46 to
  `Fn`+`` ` `` (grave), not to an arrow key, so which physical key the
  owner actually triggered this with is not settled. Worth a cleaner retest
  (press ONLY `Fn`+`` ` ``, isolated) before concluding anything about
  which key does this.
- **`Fn`+`Space` (the profile's `function_id 54`, `"Cycle brightness"`),
  held/repeated: `region 1`'s `speed` field oscillated rapidly (1↔2↔3)
  over several seconds** — brightness itself still never moved. A
  single, quick tap of `Fn`+`Space` immediately after produced **no change
  at all**, and the space character reached the terminal as ordinary text
  — meaning `Fn` most likely was not held long enough to register as a
  combo for that one tap (this keyboard's `Fn` behaves as a hold-then-press
  modifier, not a tap-together one), so the earlier "speed oscillates" data
  point is now suspect: it may not have been `Fn`+`Space` at all, since the
  terminal filling with literal spaces in that round too suggests the same
  timing failure happened repeatedly, not just once.

**Net result:** brightness reading over the protocol is solid (unchanged
conclusion from §3); whether `Fn`+`Space` actually is this unit's live
brightness shortcut, and what (if anything) `Fn`+arrows or `Fn`+`` ` ``
really do, is **not settled** — the attempts so far are more consistent
with imprecise remote key-combo timing than with a clean negative. Not
worth further rounds of text-relayed live testing right now (diminishing
returns, each round adds a new ambiguity rather than resolving the last
one); revisit if the owner wants to try again with the physical keyboard
in hand and more deliberate timing (hold `Fn` down first, then tap the
other key, release both together), or if `usbmon`/a similar capture ever
becomes available to settle it without relying on narrated key presses.

## 3.2. The real shortcut, per the official retail manual

`docs/investigations/manual-fn-shortcuts.md` distills the HTG800/Nomadic's
own printed manual — a first-party source, not a decompile — and it settles
which physical key this shortcut actually is: **`Fn`+`-` and `Fn`+`=`**, not
`Space` (§3.1's guess, from this project's own reading of
`keymap.FUNCTION_NAMES[54]`) and not the arrow keys (the manual also lists
`Fn`+`↑`/`↓` as a *second* brightness shortcut, "ambos os lados" — both
sides/zones at once).

This also explains §3.1's negative results rather than leaving them
unexplained: checked directly against the profile, the `-` and `=` keys
carry **no Fn-layer function at all** (`fn_function_id == 6`, the same
plain `CombineKey` usage as their base layer) — exactly the same shape the
arrow keys and `Space` already showed. Brightness (and `Fn`+`]`'s lighting
shortcuts, `manual-fn-shortcuts.md` §5) are apparently wired straight into
the firmware's own input handling, bypassing the reconfigurable per-key
table this project reads (`CLASS_KEY`) entirely — consistent with, not
contradicting, this section's `_brightnessLevel`/`GetNextBrightnessLevel`
finding: the ladder is real, local to the keyboard's own firmware memory,
and invisible to any host read, on purpose or otherwise.

**Still not run:** a clean test of `Fn`+`-`/`Fn`+`=` specifically (this
project has now tried arrows and Space, both apparently the wrong keys).
Given the pattern above, the likely outcome is the same as §3.1 — brightness
never appears in `watch`'s output no matter which physical key drives it —
but confirming that against the *correct* shortcut, rather than the wrong
ones already tried, would close this properly instead of leaving it open on
a technicality.

## 4. Other constants worth extracting from the product DLLs' `FieldRva` data

`Products/TK51G0101.dll` has exactly two `FieldRva` rows — no more static
array data to mine in this specific plugin. The other one, beyond the
brightness ladder, is **already in this codebase and matches byte-for-byte**:

- `TK51G0101::_matrixIds` — an `int32[90]` array (`newarr System.Int32`, 90
  elements, one per key-matrix cell — not the `byte[5]` element type the
  brightness ladder uses). Read directly from the DLL and reshaped as 6 rows
  of 15, it is **identical**, value for value, to `ek75/core/vendor_tables.py`'s
  existing `KEY_MATRIX` (6×15, including the same zero-holes at the same
  positions for the knob and other LED-less cells). This is a nice
  independent sanity check that the existing transcription is exact, not a
  new find — nothing to add here, just a confirmation.

`Products/TK50S.dll` and `Products/TK597.dll` (siblings in the family, not
this device, kept here only because they ship in the same installer) each
have exactly **one** `FieldRva` row, and it is a differently-shaped table
(pairs of small 16-bit-ish values, not a 5-byte ladder and not a 90-entry
matrix) — plausibly each product's own key-matrix table in a different
encoding, but this was not decoded further since it belongs to hardware this
project does not target; flagging it only in case a future PID in this
family reuses `TK50S`/`TK597`'s plugin shape rather than `TK51G0101`'s.

No other `FieldRva` rows exist in any product DLL. Everything else this
session found of interest during the walk was already known to
`PROTOCOL.md` (the software-effect id range 128-147 and their names, the
`Speed` 1-3 slider bound in XAML) and is not a `FieldRva` constant — it is
enum/string metadata, a different kind of asset from what this task asked
about.

## 5. What could not be determined

- **Whether `Fn`+`↑`/`↓` actually walks this ladder on real firmware** — this
  is exactly the gap that needs the hardware experiment in §3; nothing short
  of that closes it honestly.
- **Which of the two helper *pairs* (clamp vs. loop) the keyboard's own
  firmware behaviour matches**, even if the ladder is confirmed — clamp
  (`GetNextBrightnessLevel`/`GetPreviousBrightnessLevel`) stops at 0/255,
  loop wraps around. Static analysis shows both exist in the app but neither
  is called from anywhere reachable; only watching the actual wraparound
  behaviour at the endpoints answers this.
- **Why the helpers exist with zero call sites in this build.** Three
  explanations were considered (vestigial software-side stepping UI never
  shipped, firmware-only behavior with the Windows-side copy kept for parity/
  future use, or a call path this specific analysis genuinely cannot see —
  reflection was checked and ruled out via raw string search, but this
  project's own decompiled surface is not exhaustive: no C# source recovery
  was attempted, and `TgApi.dll`'s native code was out of scope per this
  project's own `vendor-binaries/README.md`). No further static evidence
  distinguishes them.
- **What `TK50S.dll`/`TK597.dll`'s single `FieldRva` blob encodes.** Left
  unread since it belongs to a sibling product, not this device; noted in
  §4 only as a pointer for later.
- **Whether the ladder, if confirmed, is used identically for the side-light
  region (4) or only the key matrix (1).** The existing factory-read values
  (153 for region 1, 200 for region 4 — both off-ladder, both consistent with
  having been set by software rather than by the Fn shortcut) don't settle
  this either way; §3's procedure only exercises region 1 by default, with a
  suggestion to also try region 4.
