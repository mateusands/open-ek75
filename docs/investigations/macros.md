# Investigation: writing macros

Status: **investigation, no code.** Nothing here has been sent to a keyboard.

The reading half is already shipped (`CLASS_MACRO`, see PROTOCOL.md). This is
about the other half — recording and editing — which needs the data format that
`MCO_CMD_MEMORY` carries, and that format is in neither vendor source this
project had been using.

## What this keyboard actually holds

One macro, id 1, 27 bytes:

```
04 e0 0a 80  05 e0 0b 09 5e  04 e0 0a 6d  05 e0 0b 07 9d  04 e0 0a 5f  05 e0 0b 04 71
```

**INFERRED — the records are length-prefixed.** 27 splits cleanly as
`4 + 5 + 4 + 5 + 4 + 5`, and each group's first byte is its own length:

    04 | e0 0a 80           four bytes, counting the 04
    05 | e0 0b 09 5e        five bytes, counting the 05

Six records, alternating. `0xE0` leads every one. `0x0A` and `0x0B` alternate
with it and are sequential, which invites reading them as a type or an index —
**no meaning is claimed for any of these bytes.** The split is arithmetic, not
evidence.

## The Tg macro API in the Windows app — CONFIRMED

Methods found by walking the assembly's metadata and grouping by declaring type:

| Type | Methods |
|---|---|
| `UsbHidDevice.TgUsbHidDevice` | `GetMacroStorageInfo`, `GetMacroIdList`, `GetMacroName` (×2), `SetMacroName` (×2), `CreatMacro` [sic], `WriteMacroData`, `DeleteMacro`, `ReadMacroData`, `GetMacroMiniDelay` |
| `DareuProducts.TgDeviceBase` | `ReadMemorryMacros` [sic], `WriteMemorryMacro`, `SetMacroName`, `SaveMacroParams`, `ThreadSaveMacro`, `SaveMacros` |
| `DareuProducts.MacroPackage` | `MacroPackageToByte` (×2), `ByteToMacroPackage` |

**`GetMacroStorageInfo` exists here.** PROTOCOL.md records that
`MCO_CMD_SOTRAGE_INFO` appears once in `tgdevice.js`, in the enum, and is never
sent — that is still true of the *web driver*, and it is now also true that the
*Windows app* implements it. There is a reference to port after all.

`GetMacroMiniDelay` likewise: `MCO_CMD_MINI_DELAY` is dead in the web driver and
implemented here.

## A trap, already stepped in once — CONFIRMED

`MacroPackage.ByteToMacroPackage` looks like the decoder and is not. Its first
act is to check bytes 0-6 against `84 71 77 97 99 114 111` — ASCII **`TGMacro`**.
That is the magic of the app's **export file**, not of the device's memory. A
whole afternoon could go into decoding a file format nobody asked for.

The same shape as `SaveCustomLed`, where two methods share a name across layers
and only one touches the wire. In this codebase the rule has earned itself:
**check the declaring type before reading the body.**

## `TgDeviceBase::WriteMemorryMacro`, partially read — CONFIRMED

The write orchestration, in order:

1. `HidDevice.DeleteMacro(macro.ID)` when the second argument is falsy — so a
   rewrite is delete-then-create, not an in-place update;
2. the name, as **Unicode**: `Name` is decoded, `Split`, and the first part's
   `Length * 2` is compared against **23**. A UTF-16 name capped near 11
   characters.
3. then the data, which is where the record format lives.

Step 3 was not read. `TgUsbHidDevice::WriteMacroData` and `ReadMacroData` are
the packets themselves and are the obvious next dumps.

## Plan

Read-only first, as everywhere else in this project.

1. **`GetMacroStorageInfo` and `GetMacroMiniDelay`** — two reads with a
   reference in the Windows app and none in the web driver. They say how much
   room the keyboard has and what its minimum delay is, and they cost nothing
   to be wrong about. Byte-match tests, then `probe`.
2. **`ReadMacroData` vs what we already read.** We get the 27 bytes through
   `MCO_CMD_MEMORY`; reading the app's own `ReadMacroData` confirms whether that
   is the whole story or whether it reads a header first.
3. **The record format**, from `WriteMacroData`'s encoder. Until this is read,
   the 27 bytes stay opaque and the GUI keeps showing raw hex, which is the
   honest state.
4. **Only then**, writing: `CreatMacro`, `WriteMacroData`, `SetMacroName`,
   `DeleteMacro`. Persistent writes. The way back is `Fn`+`Esc`, the firmware's
   own factory reset, plus the existing key-map backup — a macro is bound to a
   key through `CLASS_KEY`, which this project already backs up and restores.

## Not determined

- The record format. This is the whole blocker for step 4.
- Whether this keyboard's single stored macro is a factory default or something
  the owner recorded with the Windows app.
- How a macro is bound to a key — presumably a `function_id` in `CLASS_KEY`
  whose data carries the macro id, but no id in `FUNCTION_NAMES` has been
  matched to it and the live key map shows no key using one.
