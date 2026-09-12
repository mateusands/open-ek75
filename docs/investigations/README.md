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
| [`brightness-ladder.md`](brightness-ladder.md) | **Ladder confirmed, use unconfirmed.** `{0, 70, 120, 190, 255}` is real and shaped like a step ladder — nothing in the app calls it, and it is apparently wired straight into the firmware, invisible to any host read. Two live attempts on real hardware (§3.1) tried the wrong keys (arrows, then `Space`); the official retail manual (§3.2, `manual-fn-shortcuts.md`) says the real shortcut is `Fn`+`-`/`Fn`+`=`, still untested. |
| [`key-test.md`](key-test.md) | **No protocol needed.** The app uses Windows Raw Input, not a Dareu command; `CLASS_TEST` has no command list at all. Measured on a real KDE session: tkinter sees most keys with focus, and the desktop eats Print and the media keys. The valuable half is the list of keys that *cannot* be tested. |
| [`wireless-dongle.md`](wireless-dongle.md) | **Talks to the dongle, not the keyboard.** Pairing is not a command — it is `Fn`+`1/2/3` and `Fn`+`Q`, run by the firmware. `DEV_CMD_WIRELESS_CONNECT_STATUS` is built and tested (`protocol.py`) and `find_dongle()` locates the dongle's interface, but nothing has been sent: its hidraw node is root-only, and this project's udev rule does not cover the dongle's PID. See PROTOCOL.md's `CLASS_DEVICE` section. |
| [`string-keys.md`](string-keys.md) | **Not a gap — the feature does not exist.** It was listed from two page names that turned out to be a leftover string and a Hall-effect page this keyboard cannot show. |
| [`manual-fn-shortcuts.md`](manual-fn-shortcuts.md) | **New first-party source.** The retail unit's own printed manual, cross-checked against every decompiled Fn-shortcut finding above: mostly confirms them, corrects `key_input.py`'s wrong "US legends" claim outright (spec sheet says ABNT2), and turns up two genuine conflicts (`F9`/`F10`'s volume direction; `Fn`+`Q`'s 2.4G-vs-Bluetooth label) plus one untested lead (`Fn`+`[`/`Fn`+`]`, cycle lighting effect/colour — the first `LED_CMD_*` shortcut candidate that looks cleanly testable with `watch`). |

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
