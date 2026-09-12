# Investigation: a "press a key, see it light up" test screen

Status: **built.** Slice 0 already existed; Slices 1 (throwaway probe) and 2
(`ek75/gui/key_input.py`, the keysym→HID table) shipped first; Slice 3 (the
live page, `ek75/gui/pages/key_test.py`) shipped after the owner's explicit
sign-off on breaking the mouse-only convention, design-reviewed and verified
against real hardware. Slice 4 (rollover tracking) remains deliberately
unbuilt — optional, lower priority, higher ambiguity, per §4 below.

What follows is the investigation and plan as originally written, kept
intact rather than rewritten after the fact — the sections below describe
what was true before any of this was built, and the plan they propose is
exactly what shipped.

## 0. The question

The official Windows app has `PageKeyTest` / `PageKeyTestTg` — a diagnostic
screen where the user presses physical keys and the matching key lights up
on an on-screen keyboard. This document asks:

1. Does that screen work by reading the keyboard over the **vendor HID
   protocol** (some `CLASS_*` command), or by listening to **ordinary OS
   keyboard events**?
2. If (2), how does that translate to Linux, in pure stdlib?
3. Where does a `tkinter` window's `bind()` succeed, and where does it fall
   short, on this project's actual target platform (Linux desktop, X11 or
   Wayland)?
4. Which keys on this keyboard could **never** be verified this way, and why
   — stated plainly, because a test screen that quietly can't see some keys
   and doesn't say so is worse than no test screen.

## 1. How the vendor app does it — CONFIRMED, decompiled

**Verdict: ordinary OS keyboard input (Windows' Raw Input API), not a
Dareu vendor `CLASS_*` command.** `PageKeyTest`/`PageKeyTestTg` never touch
the keyboard's vendor HID interface to find out what was pressed; they watch
the same `WM_INPUT` messages any Windows app can register for.

### The evidence chain

All of this comes from decompiling `Central de Controle Husky.exe` and
`DeviceBase.dll` with `dnfile`/`dncil` (the same tool this project's
`PROTOCOL.md` already used for the lighting protocol). Every claim below was
checked by dumping the actual IL, not by trusting a name in the metadata —
per this project's own evidence rule, a name is not a call site.

**`PageKeyTest` and `PageKeyTestTg` exist and have an identical shape**
(confirmed: `TypeDef` scan of the exe finds both, each with exactly:
`.ctor`, `PageKeyTest_Loaded`, `PageKeyTest_Unloaded`, `InitPage`,
`KeyboardDataArrived`, `ParseKeyboardData`, `OpacityChanged_Completed`, plus
the XAML-generated `InitializeComponent`/`IComponentConnector.Connect`).
Both extend `System.Windows.Controls.Page` directly — no shared custom base
class, no interface beyond the XAML one.

**`ParseKeyboardData(byte sentinel, ushort usageId, byte flags)`** (confirmed
via IL dump): bails out if `sentinel == 255` or `sentinel == 0`, otherwise
calls `GetKeyByUsageId(usageId)`, and if that returns a live key object,
either inserts a "recently seen" row (on `flags & 1` clear) or plays an
opacity-flash animation on the matching on-screen key widget (`flags & 1`
set — i.e. it distinguishes key-down from key-up and animates the *release*).
This is a **usage-id-driven UI flash**, exactly matching "press a key, see it
light up."

**`GetKeyByUsageId`** (`OEMDriver.CharacterKey`, confirmed via IL dump):
linearly scans a static `_basicCharacterKey[]` array of on-screen key
objects for one whose `.UsageId` matches, and returns it (or an
empty/unmatched key). This confirms the app's model is "the key that owns
this **standard USB HID usage id**", not "the key the vendor profile's
`CLASS_KEY` table currently has a function assigned to."

**`KeyboardDataArrived` is wired to a static delegate field, not an
override** (confirmed via IL dump of `PageKeyTest_Loaded`/`_Unloaded`):

```
ldsfld  KbdDataArrived            ; MainWindow.KbdDataArrived (static, multicast)
ldarg.0
ldftn   KeyboardDataArrived
newobj  <delegate ctor>
call    Combine                   ; classic C# `+=` compiled without add/remove
stsfld  KbdDataArrived
```

`Unloaded` does the mirror `Delegate.Remove`. This field, `KbdDataArrived`,
belongs to `OEMDriver.MainWindow` (confirmed by resolving the field's owning
`TypeDef`) — the app's main window, not the page.

**`MainWindow.WndProc` invokes it, straight out of `WM_INPUT`** (confirmed
via IL dump of `WndProc`):

```
ldarg.2
ldc.i4  255                       ; msg == 0x00FF == WM_INPUT
bne.un  <skip>
ldarg.s 4
ldloca.s local(2)
call    ProcessMessage
brfalse <skip>
...
call    ParseRawInputHidData      ; decodes RAWINPUT out of lParam
...
; dwType == 2 (RIM_TYPEHID) branch -> TgNotificationProc/JmNotificationProc/
;   QfNotificationProc — device attach/detach notifications for OTHER
;   product families' vendor HID interfaces. Unrelated to key-test.
...
ldsfld  KbdDataArrived
ldloc.3 ldfld kbData ldfld VirutalKey
brfalse <skip>
ldsfld  KbdDataArrived
ldloc.3 ldfld kbData ldfld VirutalKey
ldloc.3 ldfld kbData ldfld ScanCode
ldloc.3 ldfld kbData ldfld Flags
callvirt Invoke                   ; KbdDataArrived(VirtualKey, ScanCode, Flags)
```

`msg == 255` is `WM_INPUT`; the branch reached after `ParseRawInputHidData`
gates on `header.dwType == 1`, which is `RIM_TYPEKEYBOARD` in the Win32
`RAWINPUT` struct (the sibling `dwType == 2` branch, `RIM_TYPEHID`, is what
carries the vendor's own HID feature-report traffic for other device
families' notifications — a completely different code path, not used by
`PageKeyTest`). `kbData.VirutalKey`/`ScanCode`/`Flags` are exactly the three
fields of Win32's `RAWKEYBOARD`.

**The P/Invokes confirm the mechanism is the real Win32 Raw Input API**
(confirmed via each managed DLL's `ImplMap` table):

| Assembly | Imports | From |
|---|---|---|
| `ToolLib.dll` | `RegisterRawInputDevices`, `GetRawInputData`, `GetRawInputDeviceInfo` | `User32.dll` |
| `DataControl.dll` | same three | `User32.dll` |
| `DeviceBase.dll` | `RegisterRawInputHook`, `UnRegisterRawInputHook`, `ParseRawInputData`, `ParseRawInputHidData` | a native `DataSource.dll` helper (not among the extracted files; presumably a thin wrapper around the same three Win32 calls) |

`RegisterRawInputDevices`/`GetRawInputData` are the two calls that define
the Win32 Raw Input API. There is no P/Invoke anywhere in this app to
`HidD_SetFeature`/`HidD_GetFeature` (the vendor protocol's transport) in
connection with key-test — `HidD_GetInputReport` only turns up in
`DeviceBase.dll` for the unrelated lighting/profile read paths this project
already ported.

**`ASCallToUsageId`** (`DareuProducts.KeysOperator` in `DeviceBase.dll`,
confirmed via IL dump): a big `switch` on the Win32 virtual-key code that
writes a **standard USB HID Usage Table** id into an out-parameter and
returns the usage *page* (`7` for Keyboard/Keypad, `12` for Consumer — the
same two pages `ek75/core/keymap.py`'s `HID_KEYS`/`CONSUMER_KEYS` already
transcribe from the public spec, independently). This is the exact same
public HID table this project already uses to *describe* what a key's
`CLASS_KEY` assignment means — the vendor app reuses it here to translate a
*live keypress* instead.

**`CLASS_TEST` (10) is not the mechanism — checked and ruled out.**
`PROTOCOL.md` lists `CLASS_TEST` among the unimplemented classes from the
shared vendor framework. Grepping `tgdevice.js` (the web driver this whole
protocol was reverse-engineered from) for `Test` finds **zero** matches — a
negative worth trusting only after checking the grep can find a known
positive, so it was checked against `Lighting`/`Effect` (found, non-zero)
first, confirming grep isn't the problem. The single `Test` hit in the
sibling `device.js` is `FUNCTION_INDEX.RFTest` (217) — a wireless self-test
function id, unrelated to key-test. `CLASS_TEST` is a declared-but-unused
enum value in the shared cross-product framework; it plays no role here.

### What this means for the "protocol vs OS event" question

**CONFIRMED:** the vendor's key-test screen answers "did the OS receive a
key event with this HID usage id", not "what is this key currently
programmed to do" (that second question is what `CLASS_KEY`/`GetKeyAssign`
answers, and this project already implements it — see `PageKeySetting`'s
equivalent, `keymap.py`, and the GUI's Keys page). The two are genuinely
different questions, and the vendor app has two different screens for them.

## 2. How to do the equivalent on Linux, in pure stdlib

`tkinter` is stdlib (Python ships `_tkinter` against the system Tcl/Tk), so
this whole approach satisfies golden rule 4 with no new dependency.

### What was actually tested, on this machine

A throwaway script (`tk_probe.py`, kept only in the scratchpad, never in
`ek75/`) opened a plain `tk.Tk()` window, called `bind_all("<KeyPress>", ...)`
and `bind_all("<KeyRelease>", ...)`, and logged `keysym`, `keysym_num`,
`keycode`, `state`, `char` for every event received. `xdotool` (XTEST, i.e.
synthetic hardware-level key events, not synthetic X client messages) drove
the window after `windowactivate`/`windowfocus`, on this session's actual
desktop: **KDE Plasma, session type Wayland, Tk running as an XWayland
client** (`DISPLAY=:0`, `XDG_SESSION_TYPE=wayland`).

**Delivered to the focused Tk window, no elevated permission, no `input`
group, no `/dev/input` access — CONFIRMED by direct capture:**

```
a          -> keysym 'a'          keycode 38   (ordinary letter)
F5         -> keysym 'F5'         keycode 71
Up         -> keysym 'Up'         keycode 111  (arrow)
Menu       -> keysym 'Menu'       keycode 135
KP_1       -> keysym 'KP_1'/'KP_End' keycode 87 (see caveat below)
Super_L    -> keysym 'Super_L'    keycode 133  (the Windows/Meta key)
Caps_Lock  -> keysym 'Caps_Lock'  keycode 66
Scroll_Lock-> keysym 'Scroll_Lock'keycode 78
Pause      -> keysym 'Pause'      keycode 127
```

**NOT delivered at all, despite the window holding focus — CONFIRMED, same
run, same method, `xdotool` reported success (`rc=0`) sending them:**

```
Print                 (PrintScreen)
XF86AudioMute
XF86AudioLowerVolume
XF86AudioRaiseVolume
XF86MonBrightnessUp
```

Zero `KeyPress`/`KeyRelease` events reached the Tk window for any of these
five, in two separate isolated runs. This is not a Tk limitation as such —
it is KDE Plasma's compositor (kwin) claiming these as global shortcuts
(screenshot tool, volume OSD, brightness OSD) before the key event is ever
routed to a client window, focused or not. See §3 for what this means for
this keyboard's actual keys.

**A press/release keysym mismatch was also observed and is worth designing
around:** sending `KP_1` produced `KeyPress keysym=KP_1` but
`KeyRelease keysym=KP_End` at the *same* `keycode` (87) — because `xdotool`
toggled `Num_Lock` state around the key to guarantee the digit, and the
X server re-resolves a release's keysym against the *current* modifier
state, which had changed since the press. A matching scheme built on keysym
alone can misfire around Num Lock/Caps Lock transitions; matching on the
physical `keycode` (or better, resolving to the HID usage once, at press
time, and tracking that) is safer than re-deriving a usage from each event
independently.

### What this requires that does not exist in this repo yet

`ek75/core/keymap.py` already has, in both directions where it matters,
public HID-table data: `HID_KEYS` (Keyboard page 0x07, usage -> label),
`CONSUMER_KEYS` (Consumer page 0x0C), `HID_MODIFIERS` (the boot-report
modifier byte). None of that is vendor material — same status as the
vendor app's own use of the identical public tables (§1). What is missing,
and would be new: a **Tk keysym -> HID usage (page, id)** table. This is
also public X11/XKB data (not vendor material, not a device protocol byte —
CLAUDE.md's golden rule 2, "byte-match test before any hardware write",
does not apply to it, because it never produces a byte sent to the
keyboard), but authoring it and testing it for coverage against the
existing `HID_KEYS`/`CONSUMER_KEYS`/`HID_MODIFIERS` tables is new work with
no prior art here to port.

Matching an incoming event to a physical on-screen `KeyId` then means:
`keysym -> HID (page, usage)` (new table) `-> which KeyId's live
CLASS_KEY assignment currently carries that (page, usage)` (existing:
`core/lighting.py`'s key-map read, already used by the Keys page and the
Fn-shortcut listing). This reuses, rather than re-derives, the project's
existing "the keyboard is the authority, not the static profile" principle
(`PROTOCOL.md`, "The device profile disagrees with the keyboard — 23
times") — the same live read that already powers the Keys page should back
this screen too, not `ek75/data/0101.json` directly.

### Where a `bind()`-only approach is fundamentally insufficient

None of this needs `/dev/input/event*` for the *in-focus, ordinary-key*
case — that was the main thing worth settling, and it settles in `tkinter`'s
favour with no permission story to solve. Reading `/dev/input/event*`
directly (the `input` group, or a udev rule, the same story
`local-environment`'s hidraw setup already tells for the vendor interface)
would only be needed for something this feature does not need: capturing
keys **without** window focus, or independent of what the desktop
environment chooses to forward at all — and the second half of that (global
shortcuts eating a key before any client sees it) is exactly what §1's
Print/media-key result demonstrates, and reading raw evdev would not fix it
either, because the compositor consumes the event at the kernel-evdev layer
before dispatching to Wayland clients in the first place — the same
interception, one layer lower.

## 3. What is IMPOSSIBLE to test this way, and why

Every item here is either directly confirmed by this project's own
`PROTOCOL.md` measurements, or by this investigation's own experiment (§2).
None is a guess.

1. **The `Fn` key itself.** CONFIRMED, two ways: (a) it is a universal
   design fact of USB HID keyboards that `Fn` is a controller-local
   modifier with no usage id of its own — the keyboard's own microcontroller
   decides which *other* usage to emit, and never reports "Fn" as a
   discrete keypress; (b) this project's own data agrees — `CLASS_KEY`
   assigns function id `10` ("Fn modifier") to the physical Fn key, and
   `keymap.describe()` has no HID usage for it at all (function id 10 has no
   `data` interpretation the way ids 6/8 do). A key-test screen — vendor's or
   this one — structurally cannot show "Fn was pressed" as its own event,
   because nothing ever puts that on the wire to be seen.

2. **The four Fn-lighting shortcuts** — `Fn`+`↑`/`↓`/`-`/`=` (brightness),
   `Fn`+`←`/`→` (speed), `Fn`+`\`/`R-Alt` (effect), `Fn`+`]` (colour).
   CONFIRMED by `PROTOCOL.md`: pressing these makes the **firmware change
   its own stored lighting state**, observed only by re-reading
   `CLASS_LIGHTING` in a polling loop (`open-ek75 watch 1`) — never by
   capturing a distinguishing keyboard event. Whether the OS *also* receives
   a normal usage for the base key (arrow/minus/equals/backslash/bracket)
   while Fn is held was never captured either way (see §5) — but even in the
   best case, a key-test screen could only ever prove the **base physical
   key** works; it structurally cannot prove the **Fn-shortcut** fired,
   because that only ever shows up in the device's own lighting state, a
   job for `CLASS_LIGHTING` polling, not for a keyboard-event screen. A
   press-and-highlight test and a state-poll test are answering two
   different questions, and this keyboard's Fn-lighting layer only answers
   to the second one.

3. **`Fn`+`Esc` (factory reset, function id 44).** CONFIRMED never
   exercised by this project — `PROTOCOL.md`: "It has not been pressed.
   Testing the escape hatch means performing the destructive act it exists
   to undo." `keymap.locked_keys()` already exists to keep a remapping UI
   away from this key and the Fn key; any key-test screen must inherit the
   same exclusion rather than inviting a press.

4. **PrintScreen and the Consumer-page media/brightness keys.** CONFIRMED
   by this session's experiment (§2): on this KDE Plasma/Wayland session,
   `Print`, `XF86AudioMute`, `XF86AudioLowerVolume`, `XF86AudioRaiseVolume`
   and `XF86MonBrightnessUp` never reached a focused Tk window at all — the
   desktop shell claims them first for its own screenshot tool and
   volume/brightness OSDs. The physical key genuinely does send a standard
   Consumer-page usage (already in `keymap.CONSUMER_KEYS`) — it is the
   desktop environment, not the keyboard or this project's code, that
   consumes it. This is DE/compositor policy, not a Linux universal, and it
   was only checked on one desktop (see §5) — but it is real, reproducible,
   and it is the general shape of the risk: **any** key whose usage a
   desktop environment has bound to a global shortcut is unverifiable from
   inside a focused application window, on any DE, without root-level
   input capture that this feature does not otherwise need.

5. **Modifier chords the window manager owns for itself** — `Alt`+`Tab`,
   `Super`+anything, etc. Not directly tested here (out of scope: this
   keyboard has no such factory binding), but the same interception
   mechanism as (4) applies to any chord a window manager grabs globally,
   on any Linux desktop.

6. **True N-key-rollover / anti-ghosting, as a pass/fail claim.** Not
   impossible outright — the app can track currently-down keycodes across
   press/release pairs and notice a *missing* pairing — but a missing event
   is ambiguous between "the keyboard's own matrix dropped this
   combination" (the thing rollover testing wants to catch) and "the
   compositor/DE ate it" (item 4/5's mechanism) — the GUI has no way to
   tell those apart from inside a focused window. A rollover count from this
   screen would need the same "unconfirmed" honesty label the project
   already uses for Direction, not a bare pass/fail.

## 4. Proposed plan — slices only, no product code

**Slice 0 — ship what already exists, as the "what this key does" half.**
`CLASS_KEY`'s `GetKeyAssign` is already implemented and confirmed
(`PROTOCOL.md`), and `keymap.describe()`/`fn_shortcuts_from_map()` already
turn a live read into a human label; the Keys page already reads it on
mouse click. This answers "what is this key currently assigned to", which
is the other half of what a diagnostic screen is usually asked for, and it
needs **zero** new mechanism, zero device-I/O risk beyond what is already
shipped, and zero keyboard-focus tension with the GUI's mouse-only design.
Worth calling out on its own merits, independent of whether Slice 3 below
is ever built.

**Slice 1 — a throwaway probe on the real target desktop(s), before
committing to a design.** This investigation's `tk_probe.py` only ran on
one machine/DE (KDE Plasma/Wayland). Before designing the live-press
screen for real, rerun the same probe (or a small variant covering this
keyboard's actual factory key set from `ek75/data/0101.json`) on whichever
desktop(s) the project cares about supporting, and treat GNOME/Sway/etc. as
untested until it has been. Cheap, no hardware risk, no product code.

**Slice 2 — the new, genuinely missing piece: a Tk-keysym -> HID
(page, usage) table.** Pure data, pure stdlib, public X11/XKB information —
not vendor material, not a packet byte. Belongs in `gui/` (this is
UI-input decoding, not a packet builder — keep it out of
`core/protocol.py`), with its own test asserting coverage against the
existing `keymap.HID_KEYS`/`CONSUMER_KEYS`/`HID_MODIFIERS` tables (mirroring
how `keymap.py`'s own docstring describes a test asserting full HID-usage
coverage today). No hardware needed to write or test this slice.

**Slice 3 — the live test page.** Reuses `KeyboardView` and its existing
`select(key_id)`/`set_hover_text()`. On `<KeyPress>`, resolve keysym -> HID
usage (Slice 2) -> physical `KeyId` against the **live** key map (not the
static profile — same principle `PROTOCOL.md` already established for the
Keys page), then `select()` it. Two things this slice must get right from
day one, matching the project's existing honesty convention (the
"unconfirmed on hardware" label already in `gui/i18n.py`, used for
Direction):

- It is the **first** GUI page that needs real keyboard focus — flag this
  explicitly to the user when the page opens (e.g. "click here, then start
  typing"), rather than silently expecting focus the rest of the app never
  asked for. This is a product decision (breaking the mouse-only
  convention for one page), not a technical one — worth the owner's
  explicit sign-off before implementation, separately from the technical
  design.
- §3's impossible list must be visible, not silently absent: `Fn` and its
  four lighting shortcuts need a permanent, visible note that they cannot
  be verified this way (same treatment as the Direction control today),
  `Fn`+`Esc` must stay excluded the same way `locked_keys()` already
  excludes it elsewhere, and any key this project has not verified
  reaches a focused window on the user's actual desktop (media/Print keys,
  going by this investigation) needs the same "can't confirm from here"
  framing rather than an assumed pass or an assumed fail.

**Slice 4 (optional, lower priority, higher ambiguity) — rollover
tracking**, with the ambiguity in §3.6 stated in the UI, not hidden behind
a clean pass/fail.

**Risk, by slice:** 0 and 2 touch no hardware and need no byte-match test
(no packet is built). 1 touches no hardware either — it is a throwaway
diagnostic script, not shipped. 3 needs no *new* device I/O beyond the
already-implemented, already-tested `CLASS_KEY` read (the worker-thread rule
in `CLAUDE.md` already covers that read; nothing new to add there) — its
risk is entirely about correctly representing what cannot be verified, not
about hardware safety. 4 is the only one whose output could plausibly be
misread as a hardware verdict it cannot actually support.

## 5. What this investigation could NOT determine

- **Whether the four Fn-lighting shortcuts also emit an ordinary keyboard
  usage on the wire while Fn is held**, alongside changing the firmware's
  own state. `PROTOCOL.md` settles the firmware-state half by polling
  `CLASS_LIGHTING`; nothing in this project has ever captured USB traffic
  from this keyboard to check the keyboard-usage half. Stated as unknown,
  not assumed either way.
- **Whether other Linux desktop environments intercept the same key set**
  (Print, `XF86Audio*`, `XF86MonBrightness*`) as KDE Plasma did in this
  session. Only one desktop was tested; GNOME, Sway, Hyprland, XFCE, etc.
  may differ, and some may forward more (or fewer) of these to a focused
  client. This needs testing on whichever desktop(s) the project decides
  to support (Slice 1).
- **Whether a future Wayland-native Tk build changes any of this.** Today's
  Tk on this system runs as an XWayland client; all of §2's findings are
  specific to that path. Stdlib Tk has no native Wayland backend at the
  time of this investigation, so this is a theoretical caveat rather than a
  live one, but it is worth naming as an assumption.
- **What the physical Fn key does, if anything, when combined with a key
  that carries no Fn assignment at all** — not tested against real
  hardware in this task (out of scope: investigation only, no hardware
  writes or reads performed for this document).
- **Slice 2's table assumes a US/ANSI keyboard layout for shifted digit-row
  symbols** (found by `/code-review` while reviewing Slice 2's diff): X11
  resolves a keysym from the *active XKB layout*, not from the physical HID
  usage the keyboard firmware actually sent, so `Shift+6` on a Brazilian
  ABNT2 layout (this project ships Portuguese i18n, so a real user) reports
  a different keysym than `asciicircum` — Slice 2's table then returns
  `None` for a key that really did send a valid, working usage. This is a
  property of matching on *keysym name* at all, not a bug fixable by adding
  more keysym spellings: it is the same class of fragility as the KP_1/
  Num_Lock press-vs-release mismatch above, and the vendor app's own design
  (§1) sidesteps it entirely by reading the raw HID usage id directly off
  `WM_INPUT`, never going through a layout-dependent symbol at all. On
  Linux, `event.keycode` (the X11 hardware keycode, layout-independent) is
  the closer analogue — Slice 3 should resolve **letters, digits and
  punctuation** by keycode against a fixed physical-position table, and
  reserve keysym names for the keys that do not vary by layout (arrows,
  F-keys, modifiers, Home/End/Print/Pause, media keys) rather than trusting
  every keysym Slice 2 currently maps. Left as a design note for Slice 3,
  not fixed in Slice 2 itself: a keycode-based table is a materially
  different mechanism, and deciding to build it belongs with the rest of
  Slice 3's design, not as a silent addition to the pure keysym table this
  investigation originally scoped.
- **The exact internal layout `ParseRawInputHidData`/`RegisterRawInputHook`
  use inside the native `DataSource.dll` helper.** That helper is native
  (non-.NET) and outside what `dnfile`/`dncil` can decompile; the .NET side
  of the call boundary (§1) was fully confirmed, the native implementation
  behind it was not inspected. It does not change any conclusion here —
  Win32 Raw Input's public contract (`RAWINPUT`/`RAWKEYBOARD`, `WM_INPUT`)
  is confirmed independently through the managed-side P/Invoke declarations
  and the struct field reads in `WndProc` — but it is an honest gap in how
  deep this investigation went.

## Sources

- `docs/vendor-binaries/extracted/app/Central de Controle Husky.exe` and
  `DeviceBase.dll`, decompiled with `dnfile`/`dncil` (proprietary; never
  committed, per `compliance`).
- `docs/vendor-reference/tgdevice.js`, `device.js` (already mirrored in this
  repo, per `PROTOCOL.md`'s own sourcing).
- `PROTOCOL.md`'s `CLASS_KEY` section and Fn-shortcut findings (already
  confirmed on real hardware by prior work in this project).
- `ek75/core/keymap.py`, `ek75/core/layout.py`, `ek75/gui/keyboard_view.py`,
  `ek75/gui/pages/keys.py` (existing code read for context, not modified).
- This session's own experiment: `tk_probe.py` (kept only in the session
  scratchpad, not part of this repo), run against a live `tkinter` window
  on this machine (KDE Plasma, Wayland session, Tk as an XWayland client),
  driven by `xdotool` XTEST key injection.
