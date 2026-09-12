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
| [`brightness-ladder.md`](brightness-ladder.md) | **Ladder confirmed, use unconfirmed.** `{0, 70, 120, 190, 255}` is real and shaped like a step ladder, with clamp and wrap helpers — and nothing in the app calls any of them. Closeable with `watch` and no write. |
| [`key-test.md`](key-test.md) | **No protocol needed.** The app uses Windows Raw Input, not a Dareu command; `CLASS_TEST` has no command list at all. Measured on a real KDE session: tkinter sees most keys with focus, and the desktop eats Print and the media keys. The valuable half is the list of keys that *cannot* be tested. |
| [`wireless-dongle.md`](wireless-dongle.md) | **Talks to the dongle, not the keyboard.** Pairing is not a command — it is `Fn`+`1/2/3` and `Fn`+`Q`, run by the firmware. One read, `DEV_CMD_WIRELESS_CONNECT_STATUS`, is agreed by both vendor sources. See the corrections at the top of that file. |
| [`string-keys.md`](string-keys.md) | **Not a gap — the feature does not exist.** It was listed from two page names that turned out to be a leftover string and a Hall-effect page this keyboard cannot show. |

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
