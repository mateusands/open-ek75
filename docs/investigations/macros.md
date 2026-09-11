# Investigation: writing macros

Status: **investigation, no code.** Nothing here has been sent to a keyboard.

The reading half is already shipped (`CLASS_MACRO`, see PROTOCOL.md). This is
about the other half — recording and editing — which needs the data format that
`MCO_CMD_MEMORY` carries, and that format is in neither vendor source this
project had been using.

## What this keyboard actually holds — DECODED

One macro, id 1, 27 bytes:

```
04 e0 0a 80  05 e0 0b 09 5e  04 e0 0a 6d  05 e0 0b 07 9d  04 e0 0a 5f  05 e0 0b 04 71
```

**This section previously guessed the records were length-prefixed** — 27
splits as 4+5+4+5+4+5 and each group's first byte happened to equal its own
length. That was arithmetic, not a decode, and it was wrong: it is a
coincidence that the KEYDOWN opcode is 4 and the first record it starts
happens to run 4 bytes before a delay opcode follows.

**CONFIRMED**, from `OEMDriver.Pages.PageMacroTg::ParseKeyboardData` in the
Windows app — the recording page, walked instruction by instruction. It is a
TLV opcode stream:

| Opcode | Meaning | Payload |
|---|---|---|
| `0x04` | key down | 1 byte: HID usage |
| `0x05` | key up | 1 byte: HID usage |
| `0x0A` | delay | 1 byte: ms (0-255) |
| `0x0B` | delay | 2 bytes big-endian: ms (0-65535) |
| `0x0C` | delay | 3 bytes big-endian: ms (0-16777215) |
| `0x0D` | random delay | 4 bytes big-endian: min-ms, max-ms (2 each) |

The "keycode" byte is a real USB HID Keyboard-page usage, not a Windows
VKey — confirmed independently: `RawInputDataArrived` converts every key event
through `VirtualKeyCorrection` then `ASCallToUsageId` *before* handing it to
`ParseKeyboardData`. Same public usage table `keymap.HID_KEYS` already carries.

**Modifiers use HID usages `0xE0`-`0xE7` here, not the `CLASS_KEY` bitmask.**
`CombineKey` (function id 6) packs modifiers into `data[0]` as a bitmask; a
macro instead spells out "Left Ctrl" as its own usage byte, `0xE0`, exactly
like any other key. Two different encodings for the same physical key,
confirmed in two different corners of this protocol.

Decoding this keyboard's 27 bytes with that table, byte by byte, consumes
**all 27 with nothing left over**:

```
KEYDOWN 0xE0 (Left Ctrl)   DELAY 128 ms   KEYUP 0xE0   DELAY 2398 ms
KEYDOWN 0xE0               DELAY 109 ms   KEYUP 0xE0   DELAY 1949 ms
KEYDOWN 0xE0               DELAY  95 ms   KEYUP 0xE0   DELAY 1137 ms
```

Three taps of Left Ctrl, a couple of seconds apart — the shape of an anti-idle
or keep-awake macro. A parse that lands on exactly zero remaining bytes, using
an opcode table read independently of this data, is about as strong as
evidence gets without a live USB capture.

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

1. **A pure decoder, `parse_macro_steps(data)`, in `core/protocol.py`.** No
   hardware risk at all — it decodes bytes this project already reads through
   `MCO_CMD_MEMORY`. The byte-match test is this keyboard's own 27 bytes,
   decoded against the table above, asserting the exact three-tap sequence —
   the strongest kind of test this project can write, because the expected
   value is independent hardware data, not the encoder's own output.
2. **Show it.** CLI `probe` and the GUI's Macros page currently print raw hex.
   Once decoded, they can say "KEYDOWN Left Ctrl, wait 128ms, KEYUP ..." —
   real, immediate value from a read this project already performs.
3. **`GetMacroStorageInfo` and `GetMacroMiniDelay`** — two more reads with a
   reference in the Windows app and none in the web driver, so they cost
   nothing to be wrong about.
4. **`ReadMacroData` vs what we already read**, to confirm `MCO_CMD_MEMORY`
   is the whole story and not a header-then-body split.
5. **Only then, writing**: an encoder (`build_macro_steps`, the inverse of
   step 1) plus `CreatMacro`, `WriteMacroData`, `SetMacroName`, `DeleteMacro`.
   Persistent writes. The way back is `Fn`+`Esc` plus the existing key-map
   backup — a macro is bound to a key through `CLASS_KEY`, already backed up
   and restored.

## Not determined

- Whether this keyboard's single stored macro is a factory default or
  something the owner recorded with the Windows app.
- How a macro is bound to a key — presumably a `function_id` in `CLASS_KEY`
  whose data carries the macro id, but no id in `FUNCTION_NAMES` has been
  matched to it and the live key map shows no key using one.
- Mouse events (`ParseMouseData`) inside a macro — out of scope; this project
  has no mouse to bind one to, and the opcode table above only covers what
  `ParseKeyboardData` emits.
