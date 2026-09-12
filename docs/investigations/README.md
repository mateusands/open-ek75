# Investigations

Each file answers one question about a feature the official Windows app has and
this project does not. **None of them contains code, and nothing in them has
been sent to a keyboard.** They exist so that the decision to build something —
or not to — is made against evidence rather than against a feature list.

They came out of asking "what is left before this reaches parity with the
vendor's app?". Two of the five answers were that the question was wrong.

| File | Verdict |
|---|---|
| [`macros.md`](macros.md) | **Partly closed.** The record format was decoded from the Windows app; the encoder and `SetMacroData` are now confirmed on hardware, full validation ladder. What remains is `MacroCreate`/`SetMacroName` — the two vendor sources genuinely disagree on how creation packages a name with the data. |
| [`brightness-ladder.md`](brightness-ladder.md) | **CONFIRMED ON HARDWARE.** `{0, 70, 120, 190, 255}` is real and the firmware does walk it — on `Fn`+`-`/`Fn`+`=`, not the arrows or `Space` this investigation guessed at first (both checked directly against the profile and found to carry no Fn function, before the retail manual pointed at the real shortcut). Clamps at the floor; wrap at the ceiling wasn't exercised in the run that confirmed it. |
| [`key-test.md`](key-test.md) | **Built.** No protocol needed — the app uses Windows Raw Input, not a Dareu command. Slices 0-2 (what already existed, a throwaway probe, the keysym→HID table) shipped first; Slice 3 (`gui/pages/key_test.py`, the live page — the first in this app needing real keyboard focus) shipped after the owner's sign-off, design-reviewed and hardware-verified. Slice 4 (rollover tracking) stays unbuilt on purpose. |
| [`wireless-dongle.md`](wireless-dongle.md) | **CONFIRMED ON HARDWARE.** Talks to the dongle, not the keyboard — pairing itself is still `Fn`+`1/2/3`/`Fn`+`Q`, firmware behaviour, not a command. `packaging/60-ek75.rules` now covers the dongle's PID (owner's call), and `DEV_CMD_WIRELESS_CONNECT_STATUS` was actually sent: with the keyboard paired over 2.4G, the reply correctly reported one connected slot carrying the keyboard's own PID. See PROTOCOL.md's `CLASS_DEVICE` section. |
| [`string-keys.md`](string-keys.md) | **Not a gap — the feature does not exist.** It was listed from two page names that turned out to be a leftover string and a Hall-effect page this keyboard cannot show. |
| [`manual-fn-shortcuts.md`](manual-fn-shortcuts.md) | **New first-party source.** The retail unit's own printed manual, cross-checked against every decompiled Fn-shortcut finding above: mostly confirms them, corrects `key_input.py`'s wrong "US legends" claim outright (spec sheet says ABNT2), and turned up the actual brightness shortcut (§3.2, closed in `brightness-ladder.md`). `F9`/`F10`'s volume direction is settled — tested live, the manual's own labels were swapped — and `Fn`+`Q`'s 2.4G-vs-Bluetooth label is left open by the owner's own call. §5: cycle lighting colour (`]`) confirmed live; cycle lighting effect (function 53) confirmed real and bound, but to which physical key is still open — a live test assumed `[`, which this project's own earlier live sweep of the actual keyboard says is unbound, putting 53 on `\`/`R-Alt` instead. |

## Two habits these earned

**A control has to be a name that is actually called in the assembly you are
testing.** `ToString` is a fine control in `DeviceBase.dll` — 53 call sites —
and useless in a 68-method product DLL, where its absence means nothing. One
investigation marked a whole DLL's findings inconclusive on that mistake.

**Check the declaring type before reading the body.** Three separate methods in
this codebase share a name across layers where only one reaches the wire
(`SaveCustomLed`), or look like a device decoder and parse an export file
instead (`ByteToMacroPackage` → `TGMacro`, `TextBaseToByte` → `TGText`). The
second of those cost nothing, because the first was written down.
