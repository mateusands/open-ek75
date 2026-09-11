# Investigation: assigning a text string to a key

Status: **investigation, no code.** Nothing here has been sent to a keyboard,
and nothing in `ek75/` was touched to produce this document.

## 1. What it is

**INFERRED, from the shape of the evidence below, not from a single
confirmed source:** a "Text" key is meant to be a `CLASS_KEY` function like
any other — a `function_id` (`FUNCTION_INDEX.Text` = 210) plus the standard
5-byte `Data` that `KEY_CMD_ASSIGN` always carries — where the 5 bytes almost
certainly hold a *reference* (an id into some other storage) rather than the
literal characters, because 5 bytes cannot hold an arbitrary string. Nothing
found ties that reference to a concrete storage command with a confirmed wire
packet. It is **not** `CLASS_MACRO` by direct evidence (no code path connects
the two), though `CLASS_MACRO` is the only variable-length storage mechanism
this protocol has anywhere, which is why it is the leading guess for what a
"Text" key would ultimately reduce to if this family ever implements it.

## 2. Evidence

### `FUNCTION_INDEX.Text` = 210 exists in the shared vendor index — CONFIRMED

`docs/vendor-reference/device.js`:

```
FUNCTION_INDEX={...,Program:208,Website:209,Text:210,Focus:211,...}
```

It sits next to `Program` (run an executable) and `Website` (open a URL) —
the other two function types that would also need to carry a variable-length
string (a path, a URL) if they were ever wired up. None of the three has a
dedicated packet builder in `tgdevice.js`.

### It is used exactly once outside its own enum — as a *display label*, not a packet field — CONFIRMED

The only other appearance of `FUNCTION_INDEX.Text` in any of the ten mirrored
JS files is inside `device.js`'s `GetFunctionText(functionId, data, ...)`:

```js
case FUNCTION_INDEX.Program:n=e.RunProgram;break;
case FUNCTION_INDEX.Website:n=e.OpenWebsite;break;
case FUNCTION_INDEX.Text:n=e.Text;break;
case FUNCTION_INDEX.Focus:n=e.Focus;break;
```

`GetFunctionText` is a switch that turns a `function_id` into a human-readable
string for the UI (the same function that produces "Wave", "Double Click",
etc. for the ids this project already ported). It never builds a `Uint8Array`
or calls `CommandProcess`. Grepping all ten files for `FUNCTION_INDEX.Text`
finds nothing else — no `SetKeyAssign` call, no dedicated `SetText`/`GetText`
HID command anywhere in `tgdevice.js`.

### `CLASS_KEY_CMD_LIST` has no text-storage command — CONFIRMED

```
CLASS_KEY_CMD_LIST = {KEY_CMD_ID_LIST:0, KEY_CMD_ATTRIBUTE:1, KEY_CMD_DEBOUNCE:2,
  KEY_CMD_ASSIGN:3, KEY_CMD_ANALOG_ACTUATION_POINT:4, KEY_CMD_FN_LOCK:5,
  KEY_WIN_LOCK_MAC_STATUS:6, KEY_PERFORMACE:7, KEY_CMD_BULK_ASSIGN:8,
  KEY_CMD_SOCD_STATUS:9}
```

`KEY_CMD_ASSIGN`'s wire shape (already documented in `PROTOCOL.md`'s
`CLASS_KEY` section, and implemented read-only in this repo) is fixed: one
`function_id` byte and exactly 5 `Data` bytes, confirmed by
`tgdevice.js::SetKeyAssign(profile, keyId, functionId, layer, data[5])`. There
is no sub-command in this class capable of carrying an arbitrary-length blob.
`CLASS_MACRO` (`MCO_CMD_MEMORY`, `MCO_CMD_NAME`) is the **only** variable-length
storage this protocol exposes anywhere, per the earlier
`docs/investigations/macros.md` investigation and `PROTOCOL.md`'s `CLASS_MACRO`
section.

### `PageCharacterTg`/`PageCharacter` exist, but read as the *DKS key picker*, not a free-text page — CONFIRMED (identity), INFERRED (purpose)

The task named `PageStringKey` and `PageCharacterTg`. Searching every TypeDef
in `Central de Controle Husky.exe` for `StringKey` found **nothing** — that
exact type does not exist in this decompiled build. `PageCharacterTg` and its
sibling `PageCharacter` (for a different device family) do exist
(`OEMDriver.Pages.PageCharacterTg`, `OEMDriver.Pages.PageCharacter`), but their
`InitPage` IL (dumped in full) builds three palettes of pickable keys
(`wpBasicCharacter`, `wpExtendCharacter`, `wpSpecialCharacter`, all sourced
from `OEMDriver.CharacterKey` — a `KeyId`/`UsageId`/`KeyName` lookup, nothing
about arbitrary Unicode text) and a `DksKeysList`/`epdPersetsDks` section built
from a `TgKeyTravelParam`. `DKS` also turns up as embedded UI-string resource
keys inside `TK51G0101.dll` itself: `DksTip`, `DksTriggerPointTip`. This reads
as the **key picker for DKS (multi-actuation-point key assignment on analog
switches)** — a feature for Hall-effect keyboards — reusing a generic
"pick a keyboard character" widget, not a page for typing a string. `PROTOCOL.md`
already records that this exact model is **not** Hall-effect (`CLASS_MAGNETIC_AXIS`
is a shared protocol class, explicitly noted as possibly not applicable to
this unit). This does not prove `PageCharacterTg` is invisible on this model —
only that its own code is about DKS, not about the feature the task asked
about.

### The actual free-text serializer exists in `DeviceBase.dll` — and is provably unreached in this build — CONFIRMED

`DareuProducts.TextBase` (a distinct type from `CharacterKey`):

```
get_Index / set_Index      get_Name / set_Name        get_ID / set_ID
get_Text / set_Text        get_SendText / set_SendText
get_Binding / set_Binding  get_BindingKey / set_BindingKey
get_Length / set_Length    get_LengthKey / set_LengthKey
TextBaseToByte             ByteToTextBase
static FILE_EXT             static s_textVer = {1, 0, 0}
```

The presence of a **`FILE_EXT` static field** is the strongest single fact
here: this class serializes to a *file on disk*, the same pattern already
documented in `docs/investigations/macros.md` for `MacroPackage` (whose
`ByteToMacroPackage` checks for the ASCII magic `TGMacro` — the app's *export
file* format, not the device's wire format, and a trap that investigation
explicitly flagged).

`TextBaseToByte`'s IL (dumped in full) confirms the same shape:

```
bytes[0..5]   = "TGText"          (84 71 84 101 120 116, ASCII)
bytes[6..8]   = s_textVer         (static {1,0,0})
bytes[9]      = 0 (unused, left over from the zero-filled array)
bytes[10]     = ID                (single byte)
bytes[11]     = SendText != 0     (bool, as 0/1)
bytes[12]     = Name.length       (byte — Name capped at 255 UTF-16 code units)
bytes[13..]   = Name, Unicode (UTF-16) encoded
next 4 bytes  = Text.length, encoded big-endian
following     = Text, Unicode (UTF-16) encoded
```

`ByteToTextBase` is the exact mirror (checks the same 9-byte magic+version
header, then decodes the same fields back). **This is a save/load-to-disk
format for a named text preset, by the identical pattern already caught once
in this project (`macros.md`'s `TGMacro` trap) — not a HID packet layout.**

### Neither method is ever called, anywhere in this build — CONFIRMED, with a sanity check

Using `callsites.py` (which resolves every `call`/`callvirt` operand across
every method body, not a name search):

- Sanity check: `ToString` in `DeviceBase.dll` → **53 call sites** (matches
  the tool's own documented baseline of ~52). The tool finds real positives.
- `TextBaseToByte` in `DeviceBase.dll`: **0 call sites.**
- `TextBaseToByte` in `Central de Controle Husky.exe`: **0 call sites.**
- `ByteToTextBase` in both assemblies: **0 call sites.**
- `SetKeyString` (the `TextBase`-adjacent setter found in the same file) in
  both assemblies: **0 call sites.**
- `set_Text` / `set_SendText` on `TextBase`: **0 call sites** anywhere (only
  `TextBaseToByte` itself reads `get_Text`/`get_SendText` — nothing ever
  *writes* them, so nothing ever populates a `TextBase` to serialize in the
  first place).

For contrast — the same tool, the same technique, applied to the confirmed
*live* macro-write chain from `docs/investigations/macros.md`:

```
btnSaveToDevice_Click --> SaveMacros --> WriteMemorryMacro --> CreatMacro / WriteMacroData
```

lights up correctly (multiple call sites at every link). `TextBase` does not
light up anywhere. This is not "the tool found nothing" (the known failure
mode this project's tooling was built to avoid) — it is a genuine, isolated
node with confirmed call edges into it (`TextBaseToByte` reads `get_Text` /
`get_SendText`) and confirmed zero edges reaching it from any UI or device
class in either assembly.

### The live per-key assignment path for this device family does not special-case `Text` (or Macro) — CONFIRMED

`DareuProducts.TgKeyboard::SetKeyButtonFunction` — the method for the `Tg`
family this exact model belongs to (matching the `TgUsbHidDevice`/`PageXxxTg`
naming `PROTOCOL.md` already establishes for this PID) — was dumped in full.
It copies whatever `FunctionId`/`Data` the caller already built into the
profile's `ButtonsParam`/`FnButtonsParam`, then calls
`HidDevice.SetKeyAssign(profile, keyId, layer, FunctionId, Data, Data.Length)`
unconditionally — a straight passthrough, no branch on `FunctionId`.

This contrasts with the *other* device family found in the same assembly,
`DareuProducts.HyOHIDKeyboard::SetKeyButtonFunction`, which **does**
special-case `FunctionId` 12-15 (`MacroType1..4`): `if (12 <= FunctionId <= 15)
call SetKeyFunctionToMacro(usageId, Data[0])` — i.e., for *that* family, a
macro-type key's `Data[0]` is a macro id, and assigning one takes a different
path than the generic one. The `Tg` family's method has no equivalent branch
for `Text` (210) or for 12-15. Whatever turns a typed string into a
`KeyButtonParam` with `FunctionId=210` and 5 bytes of `Data` — if that code
exists for the `Tg` family at all — was not located; `SetKeyButtonFunction`
itself only proves that by the time a `Text` assignment reaches it (if one
ever does), it becomes an ordinary `KEY_CMD_ASSIGN` write like any other
function id.

## 3. The bytes

**No wire-packet reference exists for this.** Nothing found builds a
`CLASS_KEY`/`KEY_CMD_ASSIGN` packet with `function_id = FUNCTION_INDEX.Text`
(210), and nothing found builds any other command whose payload is the bytes
`TextBase.TextBaseToByte` produces.

What *does* exist, and what it is:

- The `KEY_CMD_ASSIGN` envelope itself (`HDR_SIZE=8`, `HDR_CLASS=CLASS_KEY`,
  `HDR_COMMAND=KEY_CMD_ASSIGN|SET_CMD`, `HDR_PROFILE`, then `keyId`, `layer`,
  `function_id`, and 5 `Data` bytes) is already confirmed and documented in
  `PROTOCOL.md`'s `CLASS_KEY` section (read direction; the write direction —
  `tgdevice.js::SetKeyAssign` — matches it byte for byte but has never been
  sent by this project). **If** a Text key is ever just an ordinary
  `KEY_CMD_ASSIGN` with `function_id=210`, this envelope is the reference —
  but nothing confirms that 210 is what actually gets sent, as opposed to the
  key ending up assigned some other `function_id` (e.g. a `MacroType`-style id)
  once the app has turned the string into a keystroke sequence.
- `TextBase.TextBaseToByte`'s 13-byte-header-plus-name-plus-text layout,
  quoted in full above, is a **file format** (it has a `FILE_EXT` field), by
  the same reasoning that caught `MacroPackage`'s `TGMacro` magic in
  `docs/investigations/macros.md`. It is recorded here because it is the only
  concrete byte layout connected to "Text" this investigation found anywhere
  — but treating it as the wire format would repeat the exact mistake that
  investigation already warned about.

## 4. Does PID 0101 (TK51G/EK75) support this?

**Not established either way — leaning toward "not confirmed."**

- The device profile shipped for this PID, `ek75/data/0101.json` (and the
  vendor's own `TK51G0101.dll` embedded `DefaultProfile.xml`, already quoted
  in `PROTOCOL.md`), assigns no key to `FUNCTION_INDEX.Text` (210) or to any
  `MacroType` id (12-15) — the full 172-entry default key map for this exact
  unit uses none of them. `ek75/core/keymap.py::FUNCTION_NAMES` (built from
  observing the live keyboard) likewise has never seen one.
- `TK51G0101.dll`'s own `DareuProducts.TK51G0101` product class (its
  `Initialize`, fully dumped) sets only `ProductImage`, `ImgLedOff`,
  `VirtualLedEffectFrameFunc`, and `IsSupportNotification=false` — no
  `HasText`/`HasMacro`/`SupportsDKS`-style capability flag was found set here
  one way or the other, and no such flag was found on the base type either
  (nothing named `IsSupportText`, `IsSupportDks`, etc. exists in
  `DeviceBase.dll` — searched by name, not exhaustively by every property).
- **Weak, circumstantial signal in the other direction:** the UI-string keys
  `DeleteTextConfirm`, `InputTextNameTip`, `DksTip`, `DksTriggerPointTip`
  appear (3 hits by `strings`) inside `TK51G0101.dll`'s own embedded resources,
  while the sibling product plugins `TK50S.dll` and `TK597.dll` (0 hits each)
  do not carry them at all. `TK51G0101.dll` is also noticeably larger
  (462 KB vs. ~375 KB) than its siblings. This is consistent with this
  product's bundle including a Text/DKS-aware resource set that the others
  don't — but it is equally consistent with `TK51G0101.dll` simply embedding a
  larger generic language catalog for unrelated reasons (three device
  variants — wired / wireless / dongle — are defined in this one DLL, versus
  one each for the others). **Not strong enough to call this CONFIRMED
  either way.**
- The web driver's per-device JSON (`docs/vendor-reference/0101.json`) has no
  `Keys`-section entry or device-level flag naming `Text` or `Macro` either.

## 5. Proposed plan

No code in this slice-list touches a keyboard before its own explicit,
separate approval — every slice below is read-only or investigation-only
until stated.

1. **Resolve the ambiguity with a live capture, not more static reading.**
   Run the actual Windows app ("Central de Controle Husky") against this PID
   over USB and see, empirically, whether a "Text"/"assign a string" UI
   surface is even offered for this model. This is the fastest way to turn
   "not established" into a fact, and it needs no packet sent to the
   keyboard — only observing the app's own screen. If the app doesn't offer
   it for this PID, everything past this point is moot and the answer to §4
   becomes CONFIRMED "no."
2. **If the app does offer it: find the `Tg`-family code that builds the
   `KeyButtonParam` for a Text assignment**, the piece this investigation did
   not locate. Concretely: whatever the "Text" page/dialog's save button
   calls, upstream of `TgKeyboard::SetKeyButtonFunction` (already read in
   full above) — search for what constructs a `KeyButtonParam` with
   `FunctionId = FUNCTION_INDEX.Text` for the `Tg` family specifically, the
   same way `docs/investigations/macros.md` traced `SaveMacros ->
   WriteMemorryMacro -> CreatMacro/WriteMacroData` for recorded macros. Read
   whether it goes through `CLASS_MACRO` (my leading guess, unconfirmed) or
   something else entirely.
3. **Only once a real call chain is found: read its actual `CommandProcess`
   call(s) for the true wire layout**, the same way `LED_CMD_FRAME` was
   recovered from `DeviceBase.dll` after the web driver came up empty. This
   is what turns "no reference" in §3 into a byte-match test.
4. **Byte-match tests before any write path is proposed for
   `core/protocol.py`**, per this project's golden rule 2 — and only once
   step 3 produces an actual confirmed packet, not the `TextBase` file format.
5. **Hardware confirmation and a way back**, per this project's hardware
   safety rules, before any `SET_CMD` variant of whatever is found is sent
   for real: the way back for a key reassignment is the existing
   `state.py` backup/restore (a key's function id and 5 data bytes are
   already covered by that mechanism, same as any other `CLASS_KEY` write).

Each step is a stop/go gate: step 1 can end the investigation outright (no
UI surface for this PID); step 2 can end it too (no call chain found, same
verdict as `CLASS_MACRO`'s undecoded record format in `macros.md`).

## 6. What could NOT be determined

- **Whether the live Windows app, run against this exact PID (0101), shows a
  "Text"/string-key assignment UI at all.** This requires running the app
  with the keyboard connected — outside what static decompilation can answer,
  and outside this investigation's scope (no code was run, no hardware was
  touched).
- **What code (if any) actually builds a `KeyButtonParam` with
  `FunctionId = FUNCTION_INDEX.Text` for the `Tg` family.** Every lead
  followed (`PageCharacterTg`, `TextBase`, `TgKeyboard::SetKeyButtonFunction`)
  either turned out to be about a different feature (DKS) or was confirmed
  unreached (`TextBase`'s (de)serializer) or was a generic passthrough that
  doesn't reveal what feeds it (`SetKeyButtonFunction`). The actual origin of
  a Text assignment, if the feature is live at all in this app build, is
  still unknown.
- **Whether "Text" ultimately becomes a `CLASS_MACRO` write (my leading
  guess) or something else.** No code path connects `FUNCTION_INDEX.Text` to
  `CLASS_MACRO`'s commands (`MCO_CMD_CREATE`, `MCO_CMD_MEMORY`, `MCO_CMD_NAME`)
  anywhere in the assemblies searched. The guess rests only on `CLASS_MACRO`
  being the sole variable-length storage the protocol has, not on any
  observed call.
- **Why `TK51G0101.dll` carries `DksTip`/`DksTriggerPointTip`/`InputTextNameTip`/
  `DeleteTextConfirm` strings while its sibling product DLLs don't.** Could
  be genuine per-product feature gating, or could be an artifact of this DLL
  bundling three device variants (wired/wireless/dongle) and a bigger default
  language catalog for unrelated reasons. Not resolved either way.
- **Whether this keyboard's firmware would even accept a `KEY_CMD_ASSIGN`
  with `function_id=210` if one were sent.** `HIDIOCSFEATURE` succeeding
  proves nothing about firmware acceptance (golden rule 2) — moot anyway,
  since no packet was sent and none is proposed to be sent by this document.
- **The exact byte offset/shape `TgApi.dll` (the native, non-.NET helper)
  might add on top of what `DeviceBase.dll` builds**, since `TgApi.dll` could
  not be decompiled with the `.NET`-only tooling (`dnfile`/`dncil`) used
  throughout this investigation.
