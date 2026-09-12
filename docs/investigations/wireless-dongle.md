> ## Two corrections, added after review
>
> **1. The claim that `callsites.py` fails its sanity check on
> `Products/TK51G0101.dll` is wrong, and so is the "inconclusive" caveat built
> on it.** The tool reads all 68 method bodies there with zero failures and
> finds real call sites — `.ctor --callvirt--> Add`, several of them. What
> happened is that the control was badly chosen: `ToString` genuinely is never
> called in a 68-method product-descriptor DLL, so its absence says nothing
> about the tool.
>
> The rule this sharpens, and it is worth more than the finding: **a control has
> to be a name that is actually called in THAT assembly**, not a name that is
> usually called somewhere. `ToString` earns its keep as a control in
> `DeviceBase.dll` (53 hits) and is useless as one here.
>
> So negatives about `TK51G0101.dll` in this document are trustworthy after all.
>
> **2. The dongle is plugged into this machine.** The plan below ends with "stop
> here without a physical dongle"; that condition is already met:
>
> ```
> Bus 003 Device 002: ID 260d:0042  USB 2.4G Receiver
> Bus 003 Device 003: ID 260d:0101  EK75_Keyboard
> /dev/hidraw0,1,2  ->  HID_ID=0003:0000260D:00000042
> ```
>
> The keyboard is on the cable and the receiver is in a port at the same time,
> so `DEV_CMD_WIRELESS_CONNECT_STATUS` is reachable — a read, against a second
> device this project has never opened. That makes the last slice testable
> rather than blocked, which is a different plan from the one written below.

# Investigation: wireless connection and the 2.4G dongle

Status: **CONFIRMED ON HARDWARE.** `packaging/60-ek75.rules` was extended to
cover the dongle's PID (owner's explicit decision), and
`DEV_CMD_WIRELESS_CONNECT_STATUS` was sent for real: with the keyboard
switched to 2.4G and paired to this exact dongle, the reply decoded to one
connected slot carrying the keyboard's own PID (`0x0101`) — see PROTOCOL.md's
`CLASS_DEVICE` section for the exact bytes. Pairing itself is still `Fn`-key
firmware behaviour, not a command (unchanged from the rest of this document).

Status before that: **investigation, no code.** Nothing here has been sent to a keyboard,
and no hardware for this part exists on the bench (no dongle was tested — this
project's owner has only ever driven this keyboard over the USB cable).

## 1. What the app does — summary

The Windows app's model of "wireless" splits cleanly into two things that are
easy to conflate and must not be:

1. **Finding out what is paired, and to what, on the PC side.** When a
   physical 2.4G dongle is plugged in, it enumerates on Windows as its own HID
   device (own `CreateFile` handle, own VID:PID). The app recognizes it as a
   *dongle* (an object implementing `IDongle`/`IWireless`), and asks it — over
   the wire, with a real protocol command — which child device(s) are
   currently connected to it and what their PID is. This is genuine protocol
   traffic, but it targets **the dongle's own USB endpoint**, never the
   keyboard's.
2. **Starting a pairing.** This is **not** something the app's UI triggers.
   There is no "Pair now" button, no `PagePairing`/`PageBluetooth` screen, and
   the one method that looks like it would send a live pairing command
   (`SetRfPair`) has zero call sites anywhere in the shipped app. Pairing is a
   physical action the user performs *on the keyboard*: `Fn+1`/`Fn+2`/`Fn+3`
   select Bluetooth device slot 1/2/3, `Fn+Q` (held 3-4s) re-pairs — both are
   ordinary `CLASS_KEY` function bindings the firmware executes locally when
   the key is pressed. The app's only role here is to *read* those bindings
   (already the case for every other key) and label them correctly in the
   remap UI.

   **Correction:** the line above originally called `Fn+Q` "2.4G pairing",
   following `keymap.FUNCTION_NAMES[42]`'s decompiled name. The retail unit's
   own printed manual (`docs/investigations/manual-fn-shortcuts.md` §2-3, a
   first-party source, not a decompile) places `Fn`+`Q` under its
   **Bluetooth** section specifically, describing exactly the "hold 3-4s,
   the indicator blinks fast, then pair" sequence. Both may still be true at
   once — this keyboard has a physical 3-position radio switch (wired /
   2.4G / BT), and the same `Fn`+`Q` combo plausibly re-pairs whichever mode
   is currently selected rather than being hardwired to one — but nothing
   confirms that reading over the other, so `FUNCTION_NAMES[42]`'s
   "2.4G pairing" label should be read as "too narrow", not corrected
   outright, until one of the two claims is actually tested.

Beyond that, the app shows battery level (`BatteryFrame`/`BatteryManageFrame`,
already covered by this project's `CLASS_POWER` reads) and reacts to Windows
device-arrival/-removal notifications to refresh its UI — ordinary hotplug
handling, not a protocol concern.

**The single most important fact, already on record in `PROTOCOL.md` and
confirmed by the project owner's own hardware testing:** configuration (LED
effects, colours, profiles — everything this project currently implements)
**only works over the USB cable**. The keyboard's own firmware does not accept
these writes over the 2.4G dongle. Nothing found in this investigation
contradicts that, and one new fact reinforces it (§3.4).

## 2. Evidence

All decompiler output below is from `dnfile`/`dncil` against
`DeviceBase.dll` and `Products/TK51G0101.dll`, using this session's
`callsites.py` (who calls a given method — walks every method body and
resolves the operand of each `call`/`callvirt`, so a "no call sites" answer
means an edge search came up empty, not a string search) and `dumpil.py`
(a single method's IL, with its declaring type). Every `callsites.py` run
below was preceded by a `ToString` sanity check in the *same* assembly, per
this project's evidence discipline — a script that cannot find a known-good
positive cannot be trusted to report a negative. That check passed for
`DeviceBase.dll` (52+ call sites) and for `Central de Controle Husky.exe`
(thousands). **It did not pass for `Products/TK51G0101.dll`** — `ToString`
itself came back with zero call sites there, most likely because that
assembly's calls into `DeviceBase.dll` are cross-assembly `MemberRef`s the
resolver does not follow. Any "no call sites" statement about
`TK51G0101.dll` below is therefore **not a confirmed negative** — it is
flagged as such.

### 2.1 The class shapes match exactly what the prompt described — CONFIRMED

```
DareuProducts.TgDongle           extends DareuProducts.TgDeviceBase
DareuProducts.TgCommonDongle0042 extends DareuProducts.TgDongle
DareuProducts.TK51G0101Dongle    extends DareuProducts.TgCommonDongle0042
DareuProducts.TK51G0101          extends DareuProducts.TgKeyboard
DareuProducts.TK51G0101WL        extends DareuProducts.TK51G0101
```

`TK51G0101WL`'s own two constructors do nothing but chain to the base
(`TK51G0101`'s ctor, which hardcodes VID `9741`/PID `257`) — **no
product-specific override for anything wireless exists in the plugin DLL**.
Whatever differs between the wired and wireless connection lives entirely in
the shared framework (`DeviceBase.dll`), not in this product's plugin.

### 2.2 The dongle is its own USB device, with its own PID — CONFIRMED

`TgCommonDongle0042`'s constructor:

```
DareuProducts.TgCommonDongle0042::.ctor
   ldarg.0
   ldc.i4   9741        ; VID
   ldc.i4.s 66          ; PID
   call     .ctor       ; -> TgDongle(vid, pid)
```

`9741` decimal = `0x260D` — the same VID this project already hardcodes in
`ek75/core/device.py`. `66` decimal = `0x0042` — a **different PID from the
keyboard's own `0x0101`**, and the source of the class's name
(`TgCommonDongle0042` = "the common dongle whose PID is 0x0042"). "Common"
because this same class is reused for other Dareu products' 2.4G receivers —
it is not per-keyboard hardware.

`TK51G0101Dongle`'s constructor then sets which keyboard PID this particular
dongle *pairs with*:

```
DareuProducts.TK51G0101Dongle::.ctor
   ldarg.0
   ldc.i4.1
   newarr   int16[1]
   dup
   ldc.i4.0
   ldc.i4   257          ; 0x0101
   stelem.i2
   stfld    _connectablePid
```

`get_ConnectablePid` just returns that field. So: **the physical dongle
enumerates on the PC as VID `0x260D` PID `0x0042`; the wireless keyboard
behind it still identifies itself (in the protocol's own PID field, see 2.3)
as `0x0101` — the same PID the wired keyboard uses.** Both `66` and `257` are
present in the web driver's own `AVAILABLE_PID_LIST` (`global.js`), so the
web driver's device list agrees a `0x0042` device exists and is distinct from
`0x0101`.

### 2.3 `GetWirelessConnectStatus`/`get_ConnectablePid` are genuinely called — CONFIRMED

```
$ callsites.py DeviceBase.dll GetWirelessConnectStatus get_ConnectablePid get_IsWirelessDevice GetDongleFirmwareVer
ParseDeviceInfo               --callvirt--> GetWirelessConnectStatus
ParseDeviceInfo               --callvirt--> get_ConnectablePid
ScanDevice                     --callvirt--> get_ConnectablePid
ScanDevice                     --callvirt--> GetWirelessConnectStatus
DeviceArrival                  --callvirt--> get_ConnectablePid
DeviceArrival                  --callvirt--> GetWirelessConnectStatus
DeviceRemove                    --callvirt--> GetWirelessConnectStatus
DeviceRemove                    --callvirt--> get_ConnectablePid
findDeviceBgWorker_ProgressChanged --callvirt--> get_ConnectablePid
CloseDevice                     --call-->    get_IsWirelessDevice
SaveMacros                      --call-->    get_IsWirelessDevice
GetFirmwareVer                  --callvirt--> GetDongleFirmwareVer
```

Read together with `ParseDeviceInfo`'s IL: after the app matches a raw HID
device path to a plugin class by VID/PID (via reflection,
`Activator.CreateInstance` over every loaded product plugin), if the matched
instance implements the wireless interface it allocates a 128-byte buffer and
calls `HidDevice.GetWirelessConnectStatus(buffer, len)`, then decodes pairs of
bytes from the reply as `(status, pidHigh<<8 | pidLow)` per dongle slot. This
is the exact same decode `tgdevice.js`'s `TgDongleHidDevice.GetWirelessConnectState`
does (see 2.5) — **two independent vendor sources agree on this reply shape.**
`get_ConnectablePid` is then used to check whether a discovered slot's
reported PID is one this dongle plugin actually expects.

`get_IsWirelessDevice` (`DeviceBase::get_IsWirelessDevice`) is just
`this isinst <wireless-marker-type>` — used to skip/alter behaviour for
wireless devices in `CloseDevice` and `SaveMacros` (e.g. macros need
different handling wireless — not investigated further, out of scope here).

### 2.4 Pairing is a `CLASS_KEY` binding, not a live command — CONFIRMED

`tgdevice.js`'s `FUNCTION_INDEX` (also present, same values, in
`DeviceBase.dll`'s own enum):

```
BlueToothPair: 41, WirelessPair: 42
```

The vendor's own factory profile for this exact PID (`0101.json`,
`docs/vendor-reference/0101.json`) assigns them to the Fn layer of the keys
this project's owner already identified by testing:

| Key | Fn FunctionId | Fn FunctionData[0] |
|---|---|---|
| `1` | `BlueToothPair` (41) | `0` |
| `2` | `BlueToothPair` (41) | `1` |
| `3` | `BlueToothPair` (41) | `2` |
| `Q` | `WirelessPair` (42) | `0` |

`DeviceBase.dll` has getters `get_HID_FK_MODE_PAIR_RF`,
`get_HID_FK_MODE_PAIR_BLE1..4`, and they are called from `KeyDataToKeyCode` /
`KeyCodeToKeyData` — the same encode/decode pair this project's `keymap.py`
already ports for every other `FUNCTION_INDEX` value. **Nothing here sends a
live "start pairing" packet; the firmware acts on the Fn key press itself**,
the same way it already acts on `LightingSpeed`'s Fn cycle
(`PROTOCOL.md`'s `Speed` section, confirmed by `watch`).

`SetRfPair` (`UsbHidDevice.TgUsbHidDevice::SetRfPair(byte, byte)`) is the one
method that looks like a live pairing trigger — it builds a `CLASS_DEVICE`
packet and calls `CmdProcess` — but:

- it has **zero call sites** in `DeviceBase.dll` itself (the same
  `ToString`-sanity-checked search that found 52+ hits for `ToString` found
  none for `SetRfPair`);
- it has **zero call sites** in `Central de Controle Husky.exe` (sanity
  checked the same way, thousands of `ToString` hits there);
- reading its own IL shows it never writes `HDR_COMMAND` (buffer index 4) —
  only `HDR_STATUS`, `HDR_SIZE`, `HDR_CLASS` (=0, `CLASS_DEVICE`) and the two
  payload bytes are set, so the command byte it actually sends is `0`
  (`DEV_CMD_FW_VER`), not `DEV_CMD_WIRELESS_PAIR` (35) as its name implies.

Between the missing call sites and the method not even building the packet
its name promises, this reads as **dead or broken code in the shipped
app — not a reference to port.**

### 2.5 The web driver's independent implementation — CONFIRMED, agrees on shape

`tgdevice.js`:

```js
CLASS_DEVICE_CMD_LIST = {
  ..., DEV_CMD_WIRELESS_CONNECT_STATUS: 32, DEV_CMD_WIRELESS_RSSI: 33,
  DEV_CMD_RF_PROTOCOL_VER: 34, DEV_CMD_WIRELESS_PAIR: 35
}

class TgDongleHidDevice extends TgHidDevice {
  async GetWirelessConnectState(A) {
    // HDR_CLASS = CLASS_DEVICE (0), HDR_COMMAND = DEV_CMD_WIRELESS_CONNECT_STATUS | GET_CMD
    ...
    A.ConnectInfo[t].TargetId = (t + 1) << 4
    A.ConnectInfo[t].Pid = Data[i+1] << 8 | Data[i+2]
  }
}
```

`DeviceBase.dll`'s own `CLASS_DEVICE_CMD_LIST` enum has the **same field
names in the same order**, including a name (`DEV_CMD_DEVICE_COLOR`) the web
driver doesn't have — new, unconfirmed information (INFERRED — no method
was found using it). `TgUsbHidDevice::GetWirelessConnectStatus`'s IL sends
`HDR_CLASS=0`, `HDR_COMMAND=160` (`0x80 | 32` — `GET_CMD | DEV_CMD_WIRELESS_CONNECT_STATUS`,
matching the JS value exactly), and decodes the reply the same way `TgDongleHidDevice`
does. One difference: the DLL sets `HDR_SIZE=6` where the JS sets `HDR_SIZE=7`
— a field the GET request itself doesn't otherwise depend on, so low-risk, but
worth recording rather than glossing over. **Class, command, and reply
decoding are corroborated by both vendor sources; `HDR_SIZE` is not.**

### 2.6 A genuine disagreement between the two sources — CONFIRMED, NOT resolved

`TgUsbHidDevice::GetWirelessRSSI`'s IL sends `HDR_COMMAND = 147` (`0x93`).
`147 - 0x80(GET_CMD) = 19`. But `tgdevice.js` gives `DEV_CMD_WIRELESS_RSSI` the
value `33` (`0x80 | 33 = 161`, not `147`). `19` is `DEV_CMD_DOCK_MID` in the
web driver's own numbering — a value that has nothing to do with RSSI. Unlike
`GetWirelessConnectStatus` (§2.5), which the two sources agree on exactly,
**`GetWirelessRSSI` does not agree between the compiled app and the web
driver.** Given that (a) this method also has zero found call sites in either
`DeviceBase.dll` or the main app, and (b) `SetRfPair` in the very same class
was shown to be broken (§2.4), the more likely explanation is that this
particular method in the compiled `DeviceBase.dll` is stale/wrong, not that
the web driver is — but this project has no way to tell which, without a
hardware capture. **Do not port `GetWirelessRSSI` from either source without
independent confirmation** (golden rule 2).

### 2.7 The Report ID itself changes for non-wired connections — CONFIRMED, mechanism only

`device.js`'s `HidUsbDeviceBase` constructor (the base every `Tg*HidDevice`
class shares):

```js
this.ReportId = (2 == this.WirelessFlag) ? 7 : 0;   // for FwType 0/6/7 — our device is FwType 0
this.REPORT_SIZE = 64;
```

This project's own `ek75/core/device.py` already documents (and works
around) the wired case: *"The device does not declare a Report ID... every
buffer here is REPORT_SIZE + 1 bytes, with byte 0 fixed at 0x00."* That `0x00`
is exactly `ReportId` for `WirelessFlag != 2`. The JS confirms a **different
connection mode uses Report ID 7 instead of 0** for the very same Feature
Report structure. **What is not established:** which numeric `WirelessFlag`
value (0/1/2) corresponds to 2.4G-via-dongle versus direct Bluetooth, or
whether the 2.4G-dongle path changes the Report ID at all (only `== 2` does,
by this code) — marked INFERRED where the *existence* of the mechanism is
CONFIRMED but the exact wireless-mode-to-flag mapping is not.

### 2.8 Enumeration/pairing UI is ordinary hotplug handling — CONFIRMED

`Central de Controle Husky.exe` has no `PagePairing`/`PageBluetooth`/`PageDongle`
screen — the only wireless-adjacent UI classes are `PageDeviceInfoDisconnect`
and the battery pages. `Global::WirelessDeviceChangedNotifycation` — the
handler wired to Windows' device-change notifications — does nothing but:

```
OEMDriver.Global::WirelessDeviceChangedNotifycation
   brfalse.s -> WaitForDeviceArrival(...)
   -> WaitForDeviceRemove(...)
```

This is Windows' `RegisterDeviceNotification`/`WM_DEVICECHANGE` plumbing, the
same shape as any USB hotplug handler — not a protocol concern. Linux's
equivalent (`/dev/hidraw*` appearing/disappearing, or a udev rule) already
covers the same need with no porting required.

## 3. Protocol commands involved

**Yes, there are protocol commands — but they target the dongle's own USB
endpoint (VID `0x260D` PID `0x0042`), never the keyboard's `0x0101`
endpoint.** Class is `CLASS_DEVICE` (0) — already a named constant in
`ek75/core/protocol.py`, currently unused for anything.

| Sub-command | Value | Byte layout (as `TgUsbHidDevice` builds it) | Status |
|---|---|---|---|
| `DEV_CMD_WIRELESS_CONNECT_STATUS` | 32 | Request: `HDR_CLASS=0`, `HDR_COMMAND=160 (GET\|32)`. `HDR_SIZE` disagrees between sources — JS sets `7`, the DLL's `TgUsbHidDevice` sets `6` (a byte the request itself does not otherwise use, so low-risk, but not identical). Reply: `payload[0]`=connected-slot count, then 3 bytes/slot: `status`, `pidHigh`, `pidLow` | **Corroborated by both vendor sources (§2.5), with the one `HDR_SIZE` discrepancy just noted.** Never sent by this project. |
| `DEV_CMD_WIRELESS_RSSI` | 33 (JS) / 19 (DLL, disagreement) | `HDR_CLASS=0`, `HDR_COMMAND` disputed — see §2.6 | **Do not port — sources disagree, zero call sites either place.** |
| `DEV_CMD_RF_PROTOCOL_VER` | 34 | Not found built anywhere in either source during this pass | Not investigated further |
| `DEV_CMD_WIRELESS_PAIR` | 35 | `SetRfPair`'s IL never actually writes this value (§2.4) | **Dead/broken in the shipped app — not a command to port** |
| `DEV_CMD_DEVICE_COLOR` | not confirmed (past 35) | No method found using it | INFERRED to exist; unconfirmed |

Pairing itself involves **no protocol command from the host at all** — it is
triggered locally by the firmware on `Fn+1/2/3` (Bluetooth) / `Fn+Q` (2.4G),
already-known `CLASS_KEY` bindings (`FUNCTION_INDEX.BlueToothPair`=41,
`WirelessPair`=42). This project's read side (`keymap.py`/`CLASS_KEY`) already
decodes these FunctionIds generically the same way it decodes every other one
— nothing wireless-specific needs to be added there.

### 3.4 Reinforces the existing "USB cable only" rule

`GetWirelessConnectStatus` — the one command in this whole investigation that
is solidly confirmed — is used by the Windows app purely to **report** which
wireless peripheral is paired to a dongle, for UI display. Nothing in either
vendor source shows the app sending `CLASS_LIGHTING`/`CLASS_PROFILE` writes
*through* a dongle object — every LED/profile method found belongs to the
keyboard's own `TgKeyboard`/`TgUsbHidDevice` object, addressed directly. This
is consistent with, and adds no exception to, `PROTOCOL.md`'s existing
"configuration only works over the USB cable" finding.

## 4. What is portable to Linux, and what is not

**Portable (concept, not code):**

- The idea of matching a *second* physical device (the dongle) by its own
  VID:PID (`0x260D:0x0042`) is exactly what `find_device()` already does for
  the keyboard — a second, analogous `find_dongle()` matching PID `0x0042`
  (by report descriptor, the same way, since it too will expose several HID
  interfaces) is a natural extension of the existing pattern in
  `ek75/core/device.py`.
- `CLASS_DEVICE`/`DEV_CMD_WIRELESS_CONNECT_STATUS`'s request/reply shape is
  pure logic — a `build_get_wireless_connect_status()` /
  `parse_wireless_connect_status_response()` pair belongs in
  `core/protocol.py` exactly like every existing builder, testable the same
  way (byte-match test, no I/O).
- Device arrival/removal handling: Linux already does this better than
  Windows needs code for (`/dev/hidraw*` nodes appear and disappear on their
  own; a udev rule can watch for it). No porting needed — there's nothing to
  port.
- The Fn-key pairing shortcuts need no protocol work: they are ordinary
  `CLASS_KEY` FunctionIds this project's existing key-decoding path already
  handles generically.

**Not portable / Windows-specific:**
- `ParseDeviceInfo`'s enumeration mechanics (`CreateFile`, `HidD_GetAttributes`,
  `HidD_GetPreparsedData`, `HidP_GetCaps`, `Activator.CreateInstance` reflection
  over plugin DLLs) — Win32 HID API and .NET reflection, with no Linux
  equivalent needed; `hidraw` + a static PID→device mapping already does the
  job this project needs.
- The exact `WirelessFlag`→`ReportId` mapping (§2.7) is a fact about the
  firmware/protocol, portable in principle, but **which WirelessFlag value
  applies to the 2.4G dongle specifically was not determined** — see §6.
- `GetWirelessRSSI` and `SetRfPair` as found in `DeviceBase.dll` — not
  portable because they are not trustworthy (§2.4, §2.6), regardless of
  platform.

## 5. Proposed plan — slices, order, risk

> **Update: a dongle turned out to be available after all.** This section
> assumed "this project owns no dongle" throughout — wrong by the time steps
> 1 and 2 were actually built. The machine this project is developed on has
> one plugged in (VID `260D` PID `0042`, "USB 2.4G Receiver"). Steps 1 and 2
> below are done; what stopped them from reaching hardware was a permission,
> not an absent device — see PROTOCOL.md's `CLASS_DEVICE` section for the
> full account. The plan below is left as originally written, for the record.

No code is proposed to be written yet; this is a slicing proposal for future
approval, ordered from lowest to highest risk/effort.

1. ~~**Read-only: detect the dongle's presence.**~~ **Done.** `find_dongle()`
   in `core/device.py`, sharing its search logic with `find_device()` via one
   `_find_vendor_feature_report(vid, pid)` helper rather than a copy.
   Confirmed by hand on the real dongle: correctly and uniquely returns
   `/dev/hidraw3` out of its 5 HID interfaces, using the existing detector
   unmodified.
2. ~~**Read-only: `GetWirelessConnectStatus`.**~~ **CONFIRMED ON HARDWARE.**
   `protocol.build_get_wireless_connect_status` / `parse_wireless_connect
   _status`, byte-match tested against both vendor sources (which agree on
   class/command, disagree on `HDR_SIZE` — ported the web driver's) — and now
   also confirmed by an actual reply: the owner extended
   `packaging/60-ek75.rules` to cover the dongle's PID, `device.open_dongle()`
   opened `/dev/hidraw3`, and the reply decoded to exactly one connected slot
   carrying the keyboard's own PID (`0x0101`) — matching a dongle paired to
   this keyboard over 2.4G. See PROTOCOL.md's `CLASS_DEVICE` section for the
   exact bytes.
3. **CLI/GUI surface.** Still nothing exposed there — this investigation's
   own read confirmed the protocol, not a decision to add a user-facing
   dongle status panel. Revisit as its own, separate slice if that is
   wanted.
4. **Stop here regardless.** Everything past step 3 —
   `DEV_CMD_WIRELESS_RSSI`, `DEV_CMD_RF_PROTOCOL_VER`, any pairing trigger —
   should not be implemented at all under the current golden rules: rule 2
   ("never send a byte you have not validated") and rule 2's byte-match-test
   requirement cannot be met without hardware to validate against, and §2.6
   already shows the vendor sources cannot even agree on `GetWirelessRSSI`'s
   byte layout. Now that a dongle is available, redo this investigation's
   §2.6 and §2.7 findings as hardware-verified facts before writing a single
   builder for them — once the permission above is granted.

No slice here touches `CLASS_DFU` or anything CLAUDE.md already gates.

## 6. What could NOT be determined

- **Which `WirelessFlag` numeric value corresponds to the 2.4G dongle versus
  direct Bluetooth**, or whether they use the same value at all. Only that
  `WirelessFlag == 2` selects Report ID 7 for FwType 0 keyboards (§2.7); 0 and
  1's meaning was not traced further in the time available.
- **What `HDR_STATUS`/`TargetId` value the host should use when addressing
  the keyboard *through* a dongle.** The web driver's reply-decoding shows
  `TargetId = (slot+1) << 4` for *reading which slot is connected*, but
  nothing in this pass confirmed whether a subsequent `CLASS_LIGHTING`/
  `CLASS_KEY` command addressed to that slot would even be accepted — and
  §3.4 suggests it plausibly would not be, for configuration commands at
  least.
- **The real byte value of `DEV_CMD_WIRELESS_RSSI`** — the two vendor sources
  disagree (§2.6) and neither is corroborated by a call site.
- **Whether `SetRfPair`/`get_DongleName`/`get_DonglePath`/`SetDongleVidPid`
  are called anywhere in `Products/TK51G0101.dll`.** This assembly's own call
  graph could not be resolved by this session's tooling — even the `ToString`
  sanity check came back empty there — so their absence from
  `DeviceBase.dll`'s and the main `.exe`'s call graphs is not proof they are
  unused everywhere; it is proof only for those two assemblies.
- **What `DEV_CMD_DEVICE_COLOR` (past `DEV_CMD_WIRELESS_PAIR` in
  `DeviceBase.dll`'s enum, absent from the mirrored `tgdevice.js`) is for.**
  No method using it was found.
- **Anything about actual on-air pairing behaviour** — RF channel selection,
  BLE bonding, retry/timeout behaviour — none of this is protocol-visible in
  either vendor source; it is presumably entirely inside the RF/BLE
  firmware stack the two USB-side protocols never touch.
- **Updated after the fact**: the wireless-status read (§ above) is now
  hardware-confirmed, once a dongle became available and the udev rule was
  extended — the caveat above described this document's state when it was
  first written, when no dongle existed on this project's bench and every
  finding was decompiler/JS evidence only. Pairing itself (`Fn`+`1/2/3`/
  `Fn`+`Q`) is still unconfirmed by a captured packet — that claim rests on
  the absence of any `SetRfPair` call site, not on a read-back.
