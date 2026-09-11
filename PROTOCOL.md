# Protocol

## How this was found

Unlike open-m711pro (USB traffic captured from the official Windows app
running in a VM), this protocol was recovered by **decompiling the vendor's
own web driver**: [dr.dareu.com](https://dr.dareu.com/), a WebHID-based
configuration tool that Dareu — the actual chip/firmware vendor behind this
keyboard, regardless of which brand's name is printed on the case — hosts
publicly, unauthenticated. Its JavaScript is minified but not obfuscated:
class and method names, constant names, and comments all survive.

The specific file is `https://dr.dareu.com/js/device/tgdevice.js`
(`TgKeyboard` / `TgKeyboardHidDevice` / `HidUsbDeviceBase` classes), fetched
with `curl -A "Mozilla/5.0" -e "https://dr.dareu.com/"` (a bare `curl` gets a
0-byte body — the server appears to gate on User-Agent/Referer, not on
anything meaningful for security). Every constant below is a direct transcription
of that file, not a guess, and every packet shown as "confirmed" was replayed
against real hardware and produced the described effect or reply.

This means the protocol is almost certainly correct for **every keyboard this
driver's device list supports** — which spans multiple rebrands (see
README.md) — not only the one it was tested on here.

## A second vendor source: the official Windows application

The web driver above was the first source. A second one turned up later and
settled several things the JavaScript never explained: **Husky's own Windows
application**, "Central de Controle Husky" (installer
`Central de Controle Husky Installer_v1.0.0.4_20250815.exe`, Inno Setup),
unpacked with `innoextract` and decompiled with `dnfile` + `dncil`.

Its layout:

```
Central de Controle Husky.exe   the WPF app (pages, sliders, the direction radios)
DeviceBase.dll                  the protocol — TgUsbHidDevice, TgDevice, ...
TgApi.dll                       a native (non-.NET) helper
UiLib.dll, LangLib.dll          widgets and translations
Products/TK51G0101.dll          the plugin for *this exact PID*
```

`Products/TK51G0101.dll` carries a `.pdb` path of
`E:\OEM\HUSKY\DareuProducts\Products\HUSKY\TK51G0101\...` — which is how
the Husky-branded keyboard was tied back to Dareu in the first place.

**Why it matters:** it is an independent implementation of the same wire
protocol, written by the vendor against this firmware. Where it agrees with
`tgdevice.js`, a byte layout stops being "one source says so". Where it says
something the JavaScript never did, it is new information.

### It agrees with the web driver, byte for byte

`DeviceBase.dll`'s `TgUsbHidDevice.SetLedEffect(profileId, ledId, effectId,
flag, speed, colorList)` builds the same packet this repo does. Its buffer is
offset by one because index 0 is the HID report-number byte — exactly like the
65-byte buffers `ek75/core/device.py` passes to `HIDIOCSFEATURE`:

```
buf[1] = _selTargetDev            -> byte 0   HDR_STATUS
buf[2] = 5 + colorList.Count      -> byte 1   HDR_SIZE
buf[3] = 3                        -> byte 2   CLASS_LIGHTING
buf[4] = 2                        -> byte 3   LED_CMD_EFFECT | SET_CMD
buf[5] = profileId                -> byte 4   HDR_PROFILE
buf[6] is never written           -> byte 5   (the "unused" byte, confirmed)
buf[7] = ledId                    -> byte 6   RegionId
buf[8] = effectId                 -> byte 7   Effect
buf[9] = flag                     -> byte 8   Flag
buf[10] = speed                   -> byte 9   Speed
buf[11] = colorList.Count / 3     -> byte 10  colour count
buf[12+i] = colorList[i]          -> byte 11+ colours
```

`TgUsbHidDevice.SetLedBrigtness(profileId, ledId, lvl)` likewise matches this
repo's `build_set_lighting_brightness` in every byte.

### `Flag` (byte 8) is the animation direction

The JavaScript names this field `flag` and never says more, and grepping all
ten mirrored JS files finds "direction" only as `FUNCTION_INDEX.LightingDirection`
— a *key binding*, not a packet field. The Windows app answers it directly:

```csharp
// PageLedRegionTg.SetLedDirection(byte direction)
var p = _currentProfile.LedParams[ID];
if (p != null && p.Flag != direction) {
    _currentLed.SetLedEffect(p.RegionId, p.ActiveEffect, direction,
                             p.Speed, p.ColorList, 1);
    SetDirctionButtonState(p.ActiveEffect, direction);
}
```

The direction goes straight into `SetLedEffect`'s `flag` argument, which is
byte 8. **`Flag` is the direction.**

It is **binary, not a 0-3 compass**. `SetDirctionButtonState(effect, direction)`
decides which pair of arrows is live, and the value is 0 or 1 within that pair:

```csharp
if (effect == 5 || effect == 141) {        // horizontal
    left/right enabled, up/down disabled, control visible
    checked = (direction == 0) ? LeftToRight : RightToLeft
} else if (effect == 130) {                // vertical
    up/down enabled, left/right disabled, control visible
    checked = (direction == 0) ? UpToDown : DownToUp
} else {
    all four disabled, the control is collapsed
}
```

So among the effects in `TG_LIGHT_EFFECT_INDEX` (0-32), only **`Wave` (5)**
has a direction, and it is horizontal. Ids 130 and 141 are outside that enum
and are not explained anywhere this project has looked — recorded here rather
than guessed at; the app renders some effects in software (`LedInterface` has
`RainbowWRun`, `RaindropRun`, `DiffusionRun` and friends, plus
`SetVirtualLedEffectFrame`), so ids at 128+ are plausibly that, unverified.

### `Speed` is 1-3, not 0-255 — confirmed by the firmware itself

`PageLedRegionTg`'s compiled XAML declares the speed slider `Minimum="1"`
`Maximum="3"`, which is why the UI shows three labels (slow / normal / fast),
and `SetLedParamControllerState` rewrites a stored `0` to `2` before
displaying it — "normal" being the middle of a three-position control. The
same method disables the slider entirely for effects without a speed;
`protocol.EFFECTS_WITH_SPEED` is that list.

**Confirmed on hardware, without writing anything.** This keyboard binds
`LightingSpeed` (48) to `Fn`+`←` and `Fn`+`→` (see the CLASS_KEY section — the
device profile hides this). Running `open-ek75 watch 1` and pressing them makes
the firmware change its own stored value, and `watch` prints what moved:

```
speed=0  ->  3  ->  2  ->  1  ->  2  ->  3  ->  2
```

It never produced 0 and never exceeded 3. The XAML said 1-3; the firmware's own
key handler agrees, which is a stronger tier of evidence than reading a slider
declaration — and it cost no write. Note that a *stored* 0 does exist (it was the
value before the first keypress); the Fn cycle simply never produces one, which
is why the vendor's app rewrites a stored 0 to 2 before displaying it.

### Brightness: a 0-255 byte, shown as 1-100

Settled by three things that agree. The slider is declared `Minimum="1"`
`Maximum="100"` in the XAML, and filled with:

```csharp
sliderBrightness.IsEnabled = (ActiveEffect > 0);
sliderBrightness.Value = (int)((float)Brightness / 255f * sliderBrightness.Maximum);
```

So the wire carries a raw byte and the UI shows it as a percentage of 255.

### The colour list is capped at five

```csharp
n = colorList.Count / 3;
if (n > 5) return 0;          // refuses to send
```

The web driver has no such check. `build_set_lighting_effect` now raises rather
than sending a packet the vendor's own software would refuse.

### `DefaultProfile.xml` — and an independent check of this repo's readings

`Products/TK51G0101.dll` embeds `TK51G0101.Resources.DefaultProfile.xml`, the
factory profile for this exact model. Its lighting section:

```xml
<ProfileLedParam>
  <RegionId>1</RegionId> <ActiveEffect>5</ActiveEffect>
  <Flag>0</Flag> <Speed>0</Speed> <Brightness>120</Brightness>
  <ColorList />
</ProfileLedParam>
<ProfileLedParam>
  <RegionId>4</RegionId> <ActiveEffect>2</ActiveEffect>
  <Flag>0</Flag> <Speed>0</Speed> <Brightness>70</Brightness>
  <ColorList>255 255 255</ColorList>
</ProfileLedParam>
```

This is **exactly** what this project independently read off real hardware
before ever seeing this file: region 1 = `Wave`, brightness 120; region 4 =
`Breathing`, white, brightness 70. It confirms the region numbering (1 = key
matrix, 4 = side light) from the vendor's own data rather than from this
repo's brute-force sweep, and it confirms the read path parses these fields
correctly. `tests/test_protocol.py::test_vendor_default_profile_round_trips`
pins it.

The same file also holds the full default key map (172 `KeyId`/`FunctionId`/
`Data` entries across the base and Fn layers) — the reference material for
`CLASS_KEY` whenever key remapping is ported.

### The app also renders the effects in software — and that is portable

`DeviceBase.dll`'s `LedInterface` is the official software's own animation
engine, with one method per effect family: `RainbowWRun`, `LightWaveRun`,
`SteadyStreamRun`, `DiffusionRun`, `RaindropRun`/`RaindropTrigger`,
`CollisionRun`, `FireworksRun`, plus `GetGradient`/`GetGradientVertical` and
`GetOutDirection`. It exists because the app draws an animated keyboard on
screen, which is the same problem `ek75/gui/keyboard_view.py` has.

Two things have been ported from it so far — the colour tables above — and
they were the ones that mattered most, because they are *data* rather than
behaviour: a wrong table is invisible until someone compares against real
hardware, whereas a wrong animation shape is obvious on sight. The `*Run`
methods themselves are still unported; anyone improving the preview should read
them before inventing an animation, and `TK51G0101`'s `_matrixIds` (the LED
grid's key mapping) and `_pathData` (the traversal order the running-light
effects follow) are the two remaining pieces of data worth extracting. Both are
nested arrays in the constructor's IL rather than flat ones, which is the only
reason they are not here yet.

### Which effects accept a colour — a wrong reading, and the correction

`PageLedTg.CheckSupportCustomColor(effect)` returns 0 for
`{0, 3, 5, 9, 10, 28, 29}` (plus 129/130/135, out of range), 2 for the
CustomFrame range 13-17, and 1 for everything else. That much is a plain
reading of its IL and is not in question.

**What it means is another matter, and this file got it wrong first.** It was
recorded here as "these effects are RGB-only, the firmware picks their
colours", and the GUI was changed to hide the colour picker for them. The
owner of the test unit immediately contradicted it: `Wave` accepts a fixed
colour *and* RGB on real hardware, which anyone with the keyboard can see in a
second.

Following the value to its consumer shows the mistake. It is passed to
`SetCustomColorControllerEnableState`, which toggles a set of `gdMask*` panels
over `cmbbColorMode` — the app's **saved custom-colour palette** UI, the one
behind `SaveColorToDevice`, `GenerateCustomColorButton` and
`btnDeleteCustomColor_Click`. The method gates *that* feature, which this
project does not implement at all. It says nothing about whether an effect
honours a colour.

So `protocol.EFFECTS_WITHOUT_COLOR` now holds two entries, both on evidence
rather than inference:

- `Off` — no colour by construction.
- `Neon` — cycling to it with the keyboard's own `Fn` + `[` made the firmware
  return an empty ColorList for the region, seen through `open-ek75 watch`.
  The firmware cleared the colours itself.

Everything else keeps its colour picker until this hardware is seen to ignore
one. The general lesson is worth more than the specific fix: **a method name is
a hint, not a specification.** `CheckSupportCustomColor` reads like it answers
"does this effect support a custom colour", and it does not. Following the
return value to whatever consumes it costs one more lookup and is the only
thing that establishes meaning.

The `Waterfall` question raised earlier is void along with the rest of that
inference — there was never a real disagreement to resolve.

### The Fn layer, decoded

None of this keyboard's Fn shortcuts are printed on the case, and the owner had
to search the web to learn them. They are all in the device profile, as a
function id plus five data bytes per key, and the ids are `FUNCTION_INDEX` from
`device.js`. Two of them carry a standard USB HID usage:

```
CombineKey (6)  data = [modifier bitmask, Keyboard-page usage, ...]
MediaKeys  (8)  data = [usage >> 8, usage & 0xFF, ...]   Consumer page
```

So `Fn` + `I` has `default-fn-function-Id: 6` and data `[0, 70]` — usage 0x46,
Print Screen. `Fn` + `F1` has id 8 and `[1, 148]` — usage 0x194, "My computer".

`ek75/core/keymap.py` decodes this and `ek75/gui/pages/home.py` lists the
result. 38 of the 83 keys carry a shortcut that does something; the other
Fn assignments simply repeat the base layer (Fn+Tab is still Tab) and are
filtered out by comparing the two assignments directly rather than by
guessing from labels.

### Other facts worth recording

- `TK51G0101.get_MinSleepTime` = 3.0 and `get_MaxSleepTime` = 30.0, matching
  the official UI's sleep-timer slider. That is the range to use when
  `CLASS_POWER`'s `SetTimeToSleep` is ported.
- The app has a `gdDisableWl` panel it hides when connected wirelessly —
  independent corroboration that configuration is a wired-only operation on
  this model.

### What is NOT taken from it

**No file from that application is redistributed in this repository**, and no
artwork from it is used. The mirrored `docs/vendor-reference/*.js` are a
different case: they are served publicly and unauthenticated from
`dr.dareu.com`. The Windows app is proprietary software distributed in an
installer; copying its binaries or its embedded assets (its keyboard render is
a single 345KB `images/tk51g.png` bitmap) into a GPL-3 repository would be
straightforward infringement. What is taken is *knowledge of the wire
protocol* — facts about how to talk to hardware the owner bought, which is
what every line above is. The keyboard this project draws comes from the
geometry in `ek75/data/0101.json`, which is functional data from Dareu's own
public JSON.

## Does this work with your keyboard?

Run `lsusb` and look for **`260d:0101`**:

```
Bus 003 Device 003: ID 260d:0101  EK75_Keyboard
```

`260D` is registered to a small OEM and is shared with at least a 2.4G
dongle/receiver product (`260D:0042`) unrelated to this protocol — only
`0101` is this keyboard.

The official Dareu web driver's device profile for this PID says:

```json
{
  "PID": "0101",
  "Model": "TK51G",
  "ProductName": "EK75",
  "Type": 1,
  "FwType": 0,
  "HasBattery": true
}
```

(`Type: 1` selects the keyboard branch of `CreateHidDevice` — see below;
`FwType: 0` selects the 64-byte wired Feature Report branch.) Fetch it
yourself at `https://dr.dareu.com/products/0101/0101.json` to confirm — it is
served with no authentication.

Other PIDs almost certainly share this exact wire format if their
`FwType` is also 0 (see "Report ID and size" below) — worth checking before
assuming a different PID needs new reverse-engineering from scratch.

## Transport

**HID Feature Reports**, sent via `ioctl(HIDIOCSFEATURE)` and read back via
`ioctl(HIDIOCGFEATURE)`, on whichever `/dev/hidraw*` node exposes the vendor
Feature Report interface. The keyboard exposes **5 HID interfaces**; only one
carries this protocol. `ek75/core/device.py`'s `find_device()` identifies it
by reading `/sys/class/hidraw/*/device/report_descriptor` and looking for the
signature described below, rather than hardcoding an interface number —
interface numbering is not guaranteed stable across firmware revisions.

### The interface's report descriptor

Decoded byte-by-byte from the real device (a Husky HTG-series unit):

```
05 0c              Usage Page (Consumer)              — cosmetic; vendor pages
09 01              Usage (0x01)                          often piggyback on an
a1 01              Collection (Application)              unrelated declared page
06 00 ff           Usage Page (Vendor-Defined 0xFF00)  <- the real marker
09 02              Usage (0x02)
15 00              Logical Minimum (0)
25 01              Logical Maximum (1)                 (looks wrong for an
                                                          8-bit field; harmless —
                                                          Feature reports are not
                                                          range-validated by the
                                                          kernel or this driver)
75 08              Report Size (8 bits = 1 byte)
95 40              Report Count (0x40 = 64)
b1 01              Feature (Data, Var, Abs)
c0                 End Collection
```

64 bytes, one Feature item, Vendor-Defined usage page, **no Report ID
declared** (no `0x85` tag anywhere in this collection). `find_device()`
matches on the `06 00 ff` (Vendor-Defined page) and `95 40 b1` (Report Count
64 immediately followed by a Feature item) byte sequences together, which is
specific enough not to match the keyboard's other four interfaces (boot
keyboard, consumer control, a digitizer-like touch interface, and a mouse/
media combo — none of them declare a Feature item this size).

### Report ID and size

From `tgdevice.js`'s `HidUsbDeviceBase` constructor (verbatim logic, renamed
from single-letter minified params):

```js
constructor(Device, FwType, TargetId, WirelessFlag) {
  ...
  if (FwType == 0 || FwType == 6 || FwType == 7) {
    this.ReportId = (WirelessFlag == 2) ? 7 : 0;
    this.REPORT_SIZE = 64;
  } else if (FwType == 1) {
    this.ReportId = 10; this.REPORT_SIZE = 64;
  } else if (FwType == 2 || FwType == 3) {
    this.ReportId = 8;  this.REPORT_SIZE = 16;
  } else if (FwType == 4) {
    this.ReportId = 0;  this.REPORT_SIZE = 16;
  } else if (FwType == 255) {
    this.ReportId = 255;
  }
}
```

For `FwType=0` (this keyboard, wired — `WirelessFlag` is 2 only over the 2.4G
dongle, which this repo does not implement): **`ReportId = 0`, `REPORT_SIZE =
64`**, matching the descriptor above exactly.

**Linux quirk**: even though the device declares no Report ID, `hidraw`
still requires a report-number prefix byte on both `HIDIOCSFEATURE` and
`HIDIOCGFEATURE`. Every buffer this code passes to those ioctls is therefore
65 bytes: a leading `0x00`, then the 64-byte packet described below. This is
a Linux/hidraw convention, not part of the wire protocol — WebHID on the
browser side does not need it, which is why `tgdevice.js`'s own buffers are
64 bytes, not 65.

## Packet layout

Constants from `tgdevice.js` (`DATA_INDEX`, `CMD_CLASS`, `GET_CMD`/`SET_CMD`),
ported verbatim into `ek75/core/protocol.py`:

```
byte 0   HDR_STATUS    write: TargetId (0 for a wired, non-dongle connection)
                        reply: low nibble == 2 marks "ready" (see below)
byte 1   HDR_SIZE      length of the payload that follows HDR_PROFILE
byte 2   HDR_CLASS     command class (CMD_CLASS.*)
byte 3   HDR_COMMAND   subcommand | GET_CMD (0x80) or | SET_CMD (0x00)
byte 4   HDR_PROFILE   profile id (1 = the default profile)
byte 5   (unused — always 0 in every capture and every accepted write)
byte 6.. PAYLOAD_BASE  command-specific payload
```

### Command classes (`CMD_CLASS`)

```
0 CLASS_DEVICE      5 CLASS_PROFILE       10 CLASS_TEST
1 CLASS_KEY         6 CLASS_MACRO         11 CLASS_LCD
2 CLASS_BUTTON      7 CLASS_POWER         12 CLASS_FLASH
3 CLASS_LIGHTING    8 CLASS_AUDIO         13 CLASS_MAGNETIC_AXIS
4 CLASS_SENSOR      9 CLASS_DFU
```

Only **`CLASS_LIGHTING` (3)** is implemented in this repo so far. The others
are transcribed here so the next person does not have to re-extract them from
`tgdevice.js` — see "What is not implemented yet" below, and note the warning
about `CLASS_DFU`.

### Lighting subcommands (`CLASS_LIGHTING_CMD_LIST`)

```
0 LED_CMD_ID_LIST     <- implemented 5 LED_CMD_CAL_DATA
1 LED_CMD_ATTRIBUTE   <- implemented 6 LED_CMD_CHARGE_CTRL
2 LED_CMD_EFFECT      <- implemented 7 LED_CMD_DPI_STAGE_INDICATOR_COLOR
3 LED_CMD_BRIGHTNESS  <- implemented 8 LED_CMD_CUSTOM
4 LED_CMD_FRAME
```

Implemented here means "there is a builder and a byte-match test". Only
`LED_CMD_EFFECT` has additionally been *replayed on hardware and visually
confirmed*; the three others are transcriptions of the vendor driver, two of
them read-only. The distinction is kept explicit throughout this file.

### `LED_CMD_EFFECT` payload (write — `SetLightingEffect`)

```
byte 6   RegionId
byte 7   Effect        (see the effect table below)
byte 8   Flag          (always 0 in every case tested; meaning unknown)
byte 9   Speed         (0 in every case tested; presumably animation speed
                         for the effects that use it — Static/Breathing did
                         not visibly change with different values)
byte 10  N             number of colours that follow (0-based count, not
                         index)
byte 11.. R,G,B × N    3 bytes per colour, N times
```

`HDR_SIZE` (byte 1) is `5 + 3*N`.

### `LED_CMD_EFFECT` payload (read — `GetLightingEffect`)

Request: just `byte 6 = RegionId`, `HDR_SIZE = 1`.

Reply: same payload layout as the write (`Effect`, `Flag`, `Speed`, colour
count, colours), read back from `PAYLOAD_BASE+1` onward.

### `LED_CMD_BRIGHTNESS`

**Read** — request: `byte 6 = RegionId`, `HDR_SIZE = 2`. Reply:
`byte 7 = Brightness`. Confirmed live: the factory values 120 (region 1) and
70 (region 4) were read back from real hardware.

**Write** (`SetLightingBrightness`, ported, **not yet confirmed on hardware**)
— same header, `HDR_SIZE = 2`, payload `byte 6 = RegionId`,
`byte 7 = Brightness`:

```js
async SetLightingBrightness(A) {
  D[HDR_STATUS]  = this.TargetId;   D[HDR_SIZE]    = 2;
  D[HDR_CLASS]   = CLASS_LIGHTING;  D[HDR_COMMAND] = LED_CMD_BRIGHTNESS | SET_CMD;
  D[HDR_PROFILE] = A.ProfileId;
  D[PAYLOAD_BASE + 0] = A.RegionId; D[PAYLOAD_BASE + 1] = A.Brightness;
}
```

The *scale* is the open question, not the layout: the two factory readings
(70, 120) are consistent with an 0-255 byte but do not prove the firmware
accepts the whole range, and the official software's slider reads 1-100. The
GUI exposes 0-255 and labels the control as unconfirmed. Writing a value and
reading it back (`open-ek75 regions`) is the cheap way to close this.

### `LED_CMD_ATTRIBUTE` (read only, implemented)

Port of `GetLedRegionAttribute`. This is how the vendor driver learns **which
effects a region actually supports**, instead of offering all 33.

Request: `byte 6 = RegionId`, `HDR_SIZE = 1`. Note it leaves `HDR_PROFILE`
(byte 4) at **0** — the driver does not set it for this command, unlike every
other lighting command. Reply:

```
byte 6   RegionId (echo)      byte 9,10  Matrix (rows, columns)
byte 7   Type                 byte 11    number of supported effects, N
byte 8   FPS                  byte 12..  the N effect numbers
```

The driver filters effects 13-18 (`CustomFrame1`-`5`, `StreamingFrame`) out of
the list it shows the user, because those need per-frame payloads rather than a
colour list. `parse_led_region_attribute_response` reproduces that filter in
`effects` and keeps the unfiltered list in `effects_raw`.

### `LED_CMD_ID_LIST` (read only, implemented)

Port of `GetLedRegionIdList` — the correct way to discover RegionIds, replacing
this repo's original brute-force sweep of 0-7 (which is kept as a fallback).
It is a **multi-packet** read; see the next section.

Its reply is filtered by the driver itself: RegionIds 0 and 1 collapse into
whichever of the two appears first, all other ids are kept as-is. The JS gives
no reason for this and `parse_led_region_id_list` reproduces it verbatim rather
than second-guessing it.

## Multi-packet reads (`GetMultiPacketCmd`)

Some replies do not fit in one 64-byte report. The driver reads them in two
steps, and `ek75/core/device.py:get_multipacket()` is a direct port.

**Step 1 — probe.** A normal GET with `HDR_SIZE = 1` and the command's own
arguments (if any) in the payload. The reply carries the total byte count at
`PAYLOAD_BASE + <number of argument bytes>`, big-endian over `width` bytes
(`width` is 1 for every command this repo uses; the driver supports up to 4).

**Step 2 — chunks.** Repeat a GET whose payload is `<args> <Total> <Offset>`
(Total and Offset each `width` bytes, big-endian), with
`HDR_SIZE = chunk + len(args) + 2 * width`. Each reply carries up to
`TG_BLOCK_SIZE = 48` bytes of data starting at
`PAYLOAD_BASE + len(args) + 2 * width`. Repeat until `Total` bytes are read.

The same mechanism carries `PFL_CMD_ID_LIST` (the profile list) and macro
data, so porting either of those is now transport work already done.

### Waiting for a reply

The device does not answer synchronously. `tgdevice.js`'s `CommandProcess`:

```js
async CommandProcess(pkt, out) {
  await this.Device.sendFeatureReport(this.ReportId, pkt);
  for (let i = 0; i < 20; i++) {
    const reply = await this.Device.receiveFeatureReport(this.ReportId);
    if ((reply[HDR_STATUS] & 0x0F) == 2) { out.Data = reply; return true; }
    await wait(10);
  }
  return false;
}
```

Ported as `ek75.core.device.command_process`: `SET_FEATURE` the request, then
`GET_FEATURE` in a loop (up to 20 tries, 10ms apart) until
`protocol.is_response_ready()` — `(status & 0x0F) == 2` — is true.

## Effects (`TG_LIGHT_EFFECT_INDEX`)

Transcribed in full from `lighting.js`. **Only `Static` and `Breathing` have
been sent to real hardware and visually confirmed** (see below); everything
else is untested and may need a payload shape this repo does not model —
several names (`CustomFrame1`-`5`, `StreamingFrame`) strongly suggest a
per-frame data format under `LED_CMD_FRAME`/`LED_CMD_CUSTOM`, not a simple
colour list.

| # | Name | # | Name | # | Name |
|---|------|---|------|---|------|
| 0 | Off | 12 | Heatup | 24 | AreaReactive |
| 1 | **Static** ✅ | 13 | CustomFrame1 | 25 | LineReactive |
| 2 | **Breathing** ✅ | 14 | CustomFrame2 | 26 | Waterfall |
| 3 | Neon | 15 | CustomFrame3 | 27 | Scanning |
| 4 | Reactive | 16 | CustomFrame4 | 28 | Heartbeat |
| 5 | Wave | 17 | CustomFrame5 | 29 | Fluxay |
| 6 | Raindrop | 18 | StreamingFrame | 30 | HeartBreath |
| 7 | Gather | 19 | Lap | 31 | MoonBreath |
| 8 | Ripple | 20 | RainbowW | 32 | StarBreath |
| 9 | RunningLight | 21 | LightWave | | |
| 10 | Rotate | 22 | SteadyStream | | |
| 11 | Starlit | 23 | StartUp | | |

`Off` (0) is listed by the driver but has **not** been sent to hardware here
— see "What to try next".

## Regions — **not from the vendor driver, found by sweeping this hardware**

`tgdevice.js` discovers a keyboard's valid `RegionId`s at runtime via
`LED_CMD_ID_LIST`. That is now ported (see "Multi-packet reads" above) and is
what `open-ek75 probe` and the GUI try first. The two regions below, however,
were originally found by brute-force — sending `LED_CMD_EFFECT|GET_CMD` for
`RegionId` 0 through 7 and seeing which ones replied — and that sweep is kept
as the fallback for when `LED_CMD_ID_LIST` does not answer. `probe` prints
which of the two produced its answer, so a sweep is never mistaken for the
firmware's own list.

| RegionId | Confirmed to control | Attributes read from the device | Factory state |
|----------|----------------------|----------------------------------|----------------|
| 1 | The per-key backlight matrix | `Type=4 FPS=33 Matrix=6x15` | `Wave`, brightness 120 |
| 4 | The side light bar | `Type=4 FPS=33 Matrix=1x16` | `Breathing`, white, brightness 70 |
| 0, 2, 3, 5, 6, 7 | Do not exist on this unit | — | — |

**`LED_CMD_ID_LIST` is confirmed on hardware**: `open-ek75 probe` reports
`regions: [1, 4] (source: LED_CMD_ID_LIST)` — the firmware answered the
multi-packet query directly, so the brute-force sweep is no longer how these
are found, and `get_multipacket()`'s port of `GetMultiPacketCmd` is exercised
end to end. It returns exactly the two regions the sweep had found, and exactly
the two in the vendor's own `DefaultProfile.xml`.

**This mapping is specific to the unit it was found on** (a Husky HTG-series
keyboard, PID 0101). A different PID sharing this protocol, or even a
different SKU under the same PID, may number its regions differently —
`PROTOCOL.md`'s job here is to record the method (sweep 0-7 with
`GetLightingEffect`), not to claim universality for the numbers.

## Per-region effect lists, read from the firmware

`LED_CMD_ATTRIBUTE` is confirmed on hardware too. What each region reported:

```
region 1 (key matrix)   19 raw -> 18 after the driver's filter
  1 Static, 2 Breathing, 5 Wave, 11 Starlit, 4 Reactive, 9 RunningLight,
  6 Raindrop, 3 Neon, 10 Rotate, 20 RainbowW, 21 LightWave, 22 SteadyStream,
  26 Waterfall, 24 AreaReactive, 25 LineReactive, 27 Scanning, 28 Heartbeat,
  29 Fluxay                                      (18 StreamingFrame filtered)

region 4 (side light)    4 raw ->  3 after the filter
  0 Off, 2 Breathing, 1 Static                   (18 StreamingFrame filtered)
```

Three things follow, and each one matters:

**The device profile's `CustomEffectList` is NOT the firmware's effect list.**
`0101.json` lists 15 effects for region 1 —
`[1, 2, 4, 5, 6, 9, 11, 19, 20, 21, 22, 24, 25, 27, 28]`. The firmware lists
18, and the two disagree in both directions: the firmware has `3 Neon`,
`10 Rotate`, `26 Waterfall` and `29 Fluxay` that the JSON omits, and the JSON
offers `19 Lap`, which the firmware does not implement. The JSON is the web
UI's curated menu; `LED_CMD_ATTRIBUTE` is the hardware's own answer. **Always
prefer the device.** This repo keeps the JSON only as a last-resort fallback
for when the command does not answer, and the GUI labels which source it used.

**`Off` (effect 0) is per-region, not universal.** Region 4 lists it; region 1
does not. So "turn the key matrix off" may not be expressible as effect 0 on
this firmware at all, and anything that offers it should check the region's
own list first — the GUI now disables its "Turn off" button for a region that
does not advertise effect 0.

**The order is the official software's grid order.** The firmware returns the
effects in the exact sequence the Husky application lays out its effect tiles
(checked position by position against a screenshot of it: Estático,
Respiração, Onda, Iluminado por Estrelas, Reativo, RunningLight, Gota de
chuva, RGB Néon, Difusão, Arco Iris, Onda de Luz, Fluxo Estável — 12 for 12).
So the list should be presented in the order received, not sorted.

### Effect names, from the vendor's own string table

`LangLib.dll` in the Windows application carries `themes/en.baml` and
`themes/ptbr.baml`, whose effect labels line up 1:1 with
`TG_LIGHT_EFFECT_INDEX`. Two are worth recording because the user-facing name
differs from the protocol name:

| # | `lighting.js` name | Official label (EN) | Official label (pt-BR) |
|---|--------------------|---------------------|------------------------|
| 10 | `Rotate` | **Diffusion** | **Difusão** |
| 29 | `Fluxay` | Fluxay | **Fluxo** |
| 18 | `StreamingFrame` | `StreamingFream` (sic) | `StreamingFream` (sic) |
| 23 | `StartUp` | `StrartUp` (sic) | Inicialização |

Effect 10 is the one to watch: the wire calls it `Rotate`, every user of the
official software calls it "Difusão". `ek75/gui/i18n.py` carries the full table
verbatim so this project's UI names match what those users already know.

## The Fn lighting shortcuts

Decoded from `ek75/data/0101.json`'s `default-fn-function-Id` fields against
`FUNCTION_INDEX` in `docs/vendor-reference/device.js`. Only three of the 83
keys carry a lighting function on this model:

> ⚠️ **The table below is the vendor profile's answer, and on this unit it is
> wrong.** It is kept because it is what `0101.json` says, and because the
> reasoning it led to is worth not repeating. The **measured** map — read from
> the keyboard with `open-ek75 keys` — is under "The device profile disagrees
> with the keyboard — 23 times" in `CLASS_KEY` below, and that one is
> authoritative.

| Shortcut | `FUNCTION_INDEX` | What it does | Measured on this unit |
|----------|------------------|--------------|-----------------------|
| `Fn` + `[` | 53 `LightingModeV2` | cycles the effect | ❌ plain `[` |
| `Fn` + `]` | 55 `LightingColorAdjustV2` | cycles the colour | ✅ correct |
| `Fn` + `Space` | 54 `BrightnessAdjust` | cycles the brightness | ❌ plain `Space` |

**What this section used to conclude — that no key is bound to `LightingSpeed`
(48) — was false**, and it cost an experiment. `Fn`+`←`/`→` are bound to it;
the profile simply does not show it. `Speed` was settled by watching after all
(see "`Speed` is 1-3"). What survives is `LightingDirection` (49): no key binds
it on this unit, and that is now measured rather than inferred.

Observed with `watch` on region 1: pressing the effect-cycling shortcut moved
the effect from `Static` to `Neon` and the colour list from `[(255, 0, 0)]` to
`[]` — the firmware clears the colours for an effect it colours itself, which
corroborates treating `Neon` as a colourless effect in the UI. *This
observation was originally written as "`Fn` + `[`", naming the key from the
profile rather than from the keyboard; the key that actually cycles the effect
here is `Fn`+`\` (or `Fn`+`R-Alt`). The observation stands — what the firmware
did is what was watched — only the key's name in it was wrong.*

## Under sustained traffic, reads trail the keyboard's real state

**Writes are never lost. Reads lag.** That sentence is the whole finding, and an
earlier version of this section got it wrong in a way worth keeping on the
record, because the wrong version pointed at the wrong fix.

### What was first written here, and why it was wrong

The first draft said *"a read right after a write can be stale"*, with a table
of delays between the write and the read. It came from a real, deterministic
experiment — the numbers reproduce exactly — but the conclusion drawn from it
did not survive being attacked:

- An **isolated** write followed by an immediate read, with the bus quiet
  beforehand, is correct **30 times out of 30**. The write→read gap is not the
  variable.
- Adding three extra reads per iteration made the *first* read correct 20 times
  out of 20, even though that read still happened ~9 ms after the write.

A fix built on the first draft would have been a delay before every read: it
would have cost latency on every screen in the GUI and fixed nothing, because
the gap it lengthened was never the problem.

### What the variable actually is

Sustained back-to-back command traffic. In a loop that writes and reads with no
pause, the keyboard's replies trail its real state, and the trailing shrinks as
the loop slows down. Measured on region 1, alternating `Static` and `Wave`, with
a uniform pause between *every* command:

| Pause between commands | Reads returning an earlier state |
|---|---|
| 0 ms | 8 / 16 |
| 10 ms | 8 / 16 |
| 20 ms | 7 / 16 |
| 40 ms | 5 / 16 |
| 80 ms | 0 / 16 |

The error is never garbage — it is a *coherent, earlier* state, which is the
kind that gets believed.

### Writes are safe, and this was tested directly

Three bursts of 24 rapid alternating writes, each ending on a known effect, each
read back after the traffic stopped: the final state matched the last write
every time. Nothing is dropped, nothing is corrupted, nothing needs retrying.
`restore` and `restore_key_map` land what they send — the 166-assignment restore
verified with 0 divergences is the same result at a larger scale.

### How long the keyboard needs to catch up

After a burst of 24 commands, reading the effect back:

| Quiet time after the burst | First read wrong |
|---|---|
| 0 ms | 4 / 8 |
| 50 ms | 4 / 8 |
| 100 ms | 0 / 8 |
| 200 ms | 0 / 8 |
| 300 ms | 0 / 8 |

**100 ms of quiet is enough.** This is the number any fix should be built on.

### Where it actually bites

It is narrower than it first looked. A GUI that writes one value and refreshes
is the isolated case, which is correct. What is not correct is reading right
after a *burst* — which is exactly how it was found: `open-ek75 restore` twice
in a row, then `open-ek75 regions`, reported the state from the run before.
Every command was acknowledged and nothing errored.

So the rule for this codebase is: **after a run of commands, be quiet for
100 ms before reading.** Not "wait before every read".

That rule is `device.SETTLE_AFTER_BURST` (150 ms — the measured 100 plus a
margin that is a judgement call, not a measurement) and `device.settle()`, which
`Session.restore` and `Session.restore_key_map` call in a `finally` once per
burst. Counted on commands *attempted*, not acknowledged: `command_process`
sends before it polls, so a call that raised still put bytes on the wire, and an
aborted burst is precisely when the caller reads next.

Verified by re-running the scenario that exposed it — two restores then a read,
six times: 0 wrong, where it had failed roughly one run in three. The cost on a
166-assignment key-map restore is 17.3 s to 17.5 s.

## Two grades of confirmation

This file uses "confirmed" in two different strengths, and conflating them is
how a wrong packet ships:

- **Acknowledged** — the command was sent and the device's reply reached
  `(status & 0x0F) == 2`, i.e. the firmware processed it and reported ready.
  Stronger than `HIDIOCSFEATURE` returning 0 (which says nothing), weaker than
  seeing the light change. An acknowledged command with the wrong semantics is
  still wrong.
- **Visually confirmed** — a human looked at the keyboard and saw the described
  effect.

### `LED_CMD_BRIGHTNESS` on write — confirmed, read back

The last lighting command in this repo that had never been sent. It works, and
it is confirmed the strong way: written, then read back and compared.

```
region 1: brightness 51  -> wrote 120 -> read back 120
region 4: brightness 20  -> wrote 180 -> read back 180
```

The layout was already corroborated by two vendor implementations; what this
adds is that the firmware accepts an arbitrary byte in that range and stores
it. Nothing suggests a 1-100 clamp: 120 and 180 both survived a round trip.

### `Flag` and `Speed` are stored by the firmware

Also confirmed by round trip, on region 1 with `Wave`:

```
wrote flag=1 speed=2 -> read back flag=1 speed=2
wrote flag=0 speed=2 -> read back flag=0 speed=2
wrote flag=1 speed=3 -> read back flag=1 speed=3
```

So the bytes are accepted and persisted, not silently dropped.

### `Speed` is rendered — the one field of the three that is

**Confirmed visually.** With everything else held identical — same effect
(`Wave`), same empty colour list, same brightness, same `flag` — only the speed
byte was changed, 1 then 3, and a human watched:

    speed=1  ->  the wave runs
    speed=3  ->  clearly and obviously faster

That closes the last of the three fields in `LED_CMD_EFFECT` whose rendering was
unknown, and the three did not come out the same way:

| Field | Stored by the firmware | Drawn | Seen on |
|---|---|---|---|
| `Speed` | yes | **yes** | region 1, `Wave` |
| `Flag` (direction) | yes | no | region 1, `Wave`, twice |
| `colors[1..4]` | yes | no | region 1, `Static` and `Wave` |

Every row is one region and one or two effects. `Wave` is the effect all three
were tested on because it is the only one the vendor gives a direction control
and the only animated one with an obvious pace — not because it is
representative of the other seventeen.

Three fields, one packet, one round trip each saying "stored" — and three
different answers to the only question that matters to a user. It is the
clearest argument in this file for why "the firmware acknowledged it" is not a
result, and why each of these needed its own look by a person.

For `Speed` the range had already been settled without writing anything, by
watching the firmware walk its own value under `Fn`+`←`/`→` (see "`Speed` is
1-3"). That proved which numbers are legal. This proves they do something.

### The colour list is used by some effects, over time — not across the keys

This section said the opposite for one commit, and the way it was wrong is the
useful part.

**First conclusion, from looking at two effects:** `Static` with red+green+blue
showed all red, and `Wave` with the same three showed all red sweeping. Both
were read back byte-identical first, so the firmware was storing the list and
appeared to be drawing only `colors[0]`. It was written up as a confirmed
negative, scoped to those two effects — and review pointed out the hole: an
effect cycling the list **over time** would look like one colour in any single
glance. That was the right question and the answer is yes.

**`Breathing` cycles the list.** Two colours alternate between breaths; three
go red, green, blue and repeat. Watched over several cycles rather than glanced
at, which is the only way this is visible.

So the list is not decoration and the distinction is not spatial-versus-nothing,
it is **which effect**:

| Effect | Colours drawn | How |
|---|---|---|
| `Breathing` (2) | the whole list | one per breath, in order, looping |
| `Static` (1) | `colors[0]` only | nothing to animate |
| `Wave` (5) | `colors[0]` only | the sweep is one colour |

### The vendor has a table for this, and it agrees

`OEMDriver.Pages.PageLedTg::CheckCustomColorCount(effect, count)` in the Windows
app — the `Tg` page is this chip family's — reduces to:

    effect in (1, 4, 9, 20, 21, 22, 132)  ->  1
    effect == 11 (Starlit)                ->  at most 2
    effect == 2  (Breathing)              ->  at most 2
    anything else                         ->  1

`PageLedWs`, `PageLedQf` and `PageLedJm` carry the identical method, so it is a
framework-wide rule rather than something special to this model.

It predicts every observation above without having been consulted first:
`Static` 1 (listed), `Wave` 1 (the default branch), `Breathing` more than 1.
Three agreements between a table read out of a binary and a human looking at a
keyboard. `Starlit` (11) is the table's other multi-colour effect and has not
been looked at.

**Where they disagree: the firmware is more capable than the vendor's UI.** The
app caps `Breathing` at two colours. This keyboard cycled three, in order. The
cap is the application's, not the hardware's — the same shape as `MAX_COLORS`
being the app's refusal to send a sixth rather than a firmware limit.

`ek75/core/protocol.max_colors_for()` encodes the vendor's table because it is
the only per-effect rule anyone has, and the GUI offers a colour list only for
the effects on it. Where the firmware turns out to allow more, that is recorded
here rather than assumed for effects nobody has watched.

### ...but `Flag` does not visibly do anything on this model

**Confirmed negative, twice.** `Wave` was run with `flag=0` and `flag=1`:

- first with a single red colour at brightness 51 — no change;
- then in the vendor's own default form (**empty colour list**, i.e. the
  rainbow sweep, where direction is unmistakable) at **brightness 255** — the
  wave still ran left-to-right both times.

The weak version of this test (dim, one colour, direction hard to see) was
eliminated deliberately before drawing the conclusion. On this firmware,
`Wave` renders in one direction regardless of `Flag`.

What that means, precisely — and the distinctions matter:

- `Flag` **is** the direction as far as the vendor's Windows software is
  concerned. `PageLedRegionTg.SetLedDirection` puts the direction into that
  argument and nothing else; that reading of the app is not in doubt.
- This keyboard's firmware **stores** the byte faithfully (round-tripped
  above) and **ignores it for rendering**, at least for `Wave`, which is the
  only firmware effect the vendor gives a direction control to.
- So the official software very likely shows the same dead arrows on this
  model. That is consistent with the rest of what is known: the app is one
  binary driving several product lines, and effects 130/141 in its direction
  table are outside this firmware's effect range entirely.

**Do not present this control as working.** `ek75/gui/` shows it with a label
saying the byte is stored but has no visible effect here, rather than removing
it — a sibling PID sharing this protocol may well render it, and the packet is
correct either way.

This is also the answer to "why did the Fn-key experiment not settle it": this
keyboard has no key bound to `LightingDirection`, and now it is clear the
firmware would have had nothing to show anyway.

### Acknowledged, visual confirmation still pending

Sent with `open-ek75` against a Husky HTG-series unit; the firmware
acknowledged each one:

| Command | Region | Note |
|---------|--------|------|
| `LED_CMD_EFFECT` `Wave(5)`, `speed=2` | 1 | first non-`Static` effect ever sent |
| `LED_CMD_EFFECT` `Wave(5)`, `speed=2`, red | 1 | with an explicit colour list |
| `LED_CMD_EFFECT` `Off(0)`, no colours | 4 | the empty colour list is accepted |
| `restore` from a backup | 1, 4 | round trip through `state.py` |

`Off(0)` on region 4 is worth calling out: the empty-colour-list packet this
repo builds (`HDR_SIZE = 5`, colour count 0) is accepted by the firmware.
Region 1 does not advertise effect 0 at all (see the effect lists above), so
this says nothing about turning the key matrix off.

### The side light "not coming back" was a brightness bug in this repo

Worth recording because it looked like a hardware or protocol mystery and was
neither. After `open-ek75 off 4`, the side light stayed dark through a
`restore` that reported success. The cause: `Session.restore()` re-applied the
effect and colours but **never wrote the brightness**, while its docstring
claimed it did. Region 4 came back as `Static` cyan at brightness 20/255 — 8%,
which reads as "still off".

Two lessons, both now enforced in code:

- A snapshot's *whole* state has to be part of the way back, or `restore` is
  not the safety net this project's hardware rule assumes it is. Fixed, with
  `tests/test_protocol.py::test_restore_writes_brightness_too` pinning it.
- "The command reported success" is not "the state came back". `restore` now
  reports failure per region if any of its writes goes unacknowledged.

## Confirmed on real hardware

1. `region=1, effect=Static(1), color=(255,0,0)` → the key matrix turned
   solid red. Visually confirmed, and still true.

2. `region=4, effect=Static(1), color=(0,200,255)` → **this one was wrong.**
   An earlier session recorded it as "the side light bar turned solid
   cyan-blue". Re-testing did not reproduce that: see below.

### The side light ignores the colour under `Static`

Region 4 lights up under `Static` — it is not dead, and `Off`/`Breathing`/
brightness all work on it. But it renders a **fixed multi-colour pattern** and
disregards the ColorList. Checked twice, deliberately, with the two least
ambiguous colours available:

```
set 4 static 255 255 255   -> unchanged (not white)
set 4 static 255 0 0       -> unchanged (not red)
```

Both packets were acknowledged, and reading region 4 back returns the colour
that was written — the firmware *stores* the ColorList and does not use it for
this effect. The same shape of result as `Flag`: accepted, persisted, not
rendered.

`Breathing` is the effect the vendor ships as this region's factory default
(`DefaultProfile.xml`: `ActiveEffect=2`, white), and it does light the strip.
Whether it honours the colour has not been isolated yet — the one test of it
used white, which cannot be told apart from "ignored" if the fixed pattern
happens to look white-ish.

**And the fixed pattern has a name.** `Products/TK51G0101.dll` carries a field
`_ledShowColor`, built in its constructor as sixteen literal
`Color.FromRgb(r, g, b)` calls — sixteen, exactly the number of LEDs
`LED_CMD_ATTRIBUTE` reports for this region:

```
 0 #0000FF   4 #FF00FF   8 #00FF00  12 #FFC810
 1 #00FF00   5 #FF80FF   9 #0000FF  13 #FF0000
 2 #FF0000   6 #0000FF  10 #FF00FF  14 #00FF00
 3 #FFC810   7 #00FF00  11 #FF80FF  15 #0000FF
```

That is the "fixed colours" the strip shows. It is not a fallback or a
failure mode — it is a hardcoded pattern the vendor ships for this SKU. The
table is transcribed in `ek75/core/vendor_tables.py` and the GUI draws it, so
the preview shows what the strip actually does rather than the colour that was
written and ignored.

The same constructor holds `_waveColorTabel`, the 24-step ramp the animated
effects cycle through. It is deliberately **not** an even HSV sweep — the steps
go `255,0,0`, `255,20,0`, `255,85,0`, `255,150,0` — which is why approximating
it with `colorsys.hsv_to_rgb` never looked quite like the hardware. Also
transcribed, and pinned by
`tests/test_protocol.py::test_vendor_colour_tables_match_the_hardware_they_describe`.

`protocol.COLOR_IGNORED` records the known case so the GUI can stop offering a
colour control that does nothing there.

**How this got into the docs wrongly matters more than the fact itself.** The
original claim came from one observation, written down as "visually confirmed",
and it then sat in `PROTOCOL.md` and in a test docstring as established fact
until someone looked again. This project's own rule — say which evidence a
claim rests on — is not worth much if a single glance gets recorded in the same
words as a repeated, controlled check.

And the read path: `GetLightingEffect`/`GetLightingBrightness` on region 1,
right after writing to it, returned exactly `Effect=1, Speed=0,
Brightness=120, colors=[(255,0,0)]` — the round trip is confirmed, not just
the write.

**The keyboard has persistent memory for this state.** Configuration only
works while connected by USB cable (not over the 2.4G dongle, per the
device's own manual/owner's testing), but once written it survives unplugging
the cable and power-cycling the keyboard — unlike, e.g., a HyperX SoloCast's
mute state, there is no daemon or boot-time script needed here. A single
successful `set` command is permanent.

## `CLASS_POWER` (7) — battery and the idle timer

Implemented **read-only**. Both reads were transcribed from `tgdevice.js` and then
answered by the real keyboard, so the values below are what the device returned.

```
CLASS_POWER_CMD_LIST
  0 PWR_CMD_BAT_STATUS    <- implemented (read)
  1 PWR_CMD_TIME_2_DIM        this keyboard does not answer it
  2 PWR_CMD_TIME_2_SLEEP  <- implemented (read); the write is deliberately absent
  3 PWR_CMD_LOW_INDICATOR_CTRL
  4 PWR_CMD_MAX_LED_BRIGHTNESS
  5 PWR_CMD_ADC
  6 PWR_CMD_USB_TIME_2_SLEEP  reads Control=0 while on the cable
```

### `PWR_CMD_BAT_STATUS` (read)

Request: `HDR_SIZE = 3`, class 7, command `0 | GET_CMD`. **`HDR_PROFILE` is not
written** — the vendor driver sets four header fields and stops, which makes sense:
charge is a property of the keyboard, not of a profile. This is the third builder in
this repo that sends profile 0, each for its own reason.

```
byte 6   Status        raw; the value set is not documented anywhere seen here
byte 7   Level
byte 8   MaxLevel
byte 9   Critical      raw
```

Read from this keyboard, plugged in: `Status=1 Level=100 MaxLevel=100 Critical=0`.

`parse_battery_status_response` derives a percentage from `Level / MaxLevel` rather
than assuming a 0-100 scale, and returns `None` for it when `MaxLevel` is 0. `Status`
and `Critical` are passed through unnamed: guessing what `1` means would be inventing
a meaning, and the GUI shows only the percentage for that reason.

### `PWR_CMD_TIME_2_SLEEP` (read)

Request: `HDR_SIZE = 3`, class 7, command `2 | GET_CMD`, **`HDR_PROFILE` set** — the
vendor driver writes `D[HDR_PROFILE] = A.ProfileId`, so the idle timeout is stored per
profile.

```
byte 6   Control       0 = the timer is off
byte 7-8 Second        big-endian; only read when Control != 0
```

Read from this keyboard, profile 1: `Control=1, Second=180`.

**Units.** The wire carries **seconds**; the official software's slider and
`TK51G0101.dll` (`MinSleepTime=3.0`, `MaxSleepTime=30.0`) are **minutes**. 180 s is
exactly those 3 minutes, which is the minimum — the two agree.

### Why `SetTimeToSleep` is not implemented

Its bytes are known and unremarkable — same header, `SET_CMD`, `payload[0] = Control`,
`payload[1..2] = Second` big-endian. It is left out on purpose:

**The effect cannot be observed on the only connection this project supports.**
Configuration works over the USB cable, and `PWR_CMD_USB_TIME_2_SLEEP` reads
`Control=0` — the keyboard does not sleep while on the cable. A write could therefore
be acknowledged, read back correctly, and never be seen to do anything. That reaches
L3 on this project's ladder and can never reach L4.

That is a weaker position than every other write here, and the rule in golden rule 2
is not "send it and see" — so the bytes are recorded and the command is not shipped.
Whoever implements it should say in the same breath how they intend to confirm it,
and "the value read back" is not an answer to "does the keyboard sleep".

## `CLASS_KEY` (1) — reading the key map

Implemented **read-only**, via `KEY_CMD_ASSIGN`.

    GetKeyAssign  HDR_SIZE=8, class 1, cmd 3|GET, HDR_PROFILE=profile
      payload:    [0]=keyId  [1]=layer      0 = base, 1 = Fn
      reply:      [2]=FunctionId  [3..7]=FunctionData (5 bytes)

The reply has the same shape as the device profile's `default-function-Id` /
`default-function-data` pair, so `ek75/core/keymap.py` decodes both with one
function. Layer 0/1 meaning was not assumed: reading both back and matching them
against the profile's base and Fn fields is what identifies which is which.

Confirmed on hardware: **all 83 keys answered on both layers**, 166 reads in
1.56 s, no failures. `KEY_CMD_BULK_ASSIGN` (8) exists and is not used — a second
untested packet shape to save about a second is a bad trade.

### `FunctionData` for `CombineKey` (6) is *two* fields, not one

    data[0]  HID modifier bitmask
    data[1]  Keyboard-page (0x07) usage
    data[2..4]  zero on every assignment this keyboard reports

Reading only `data[1]` costs nothing on an ordinary key and reports the **wrong
key** on a combination: an assignment of Ctrl+C arrives as `[0x01, 0x06, 0, 0,
0]` and gets described as "C". The modifier is not decoration, it is half of
what the key does.

The bit order is the standard USB HID boot-keyboard report's modifier byte, and
this keyboard confirms it — its eight modifier keys read back on the base layer
as exactly these single-bit values:

| Bit | Value | Key on this model |
|---|---|---|
| 0 | `0x01` | `L-Ctrl` |
| 1 | `0x02` | `L-Shift` |
| 2 | `0x04` | `L-Alt` |
| 3 | `0x08` | `L-Win` |
| 4 | `0x10` | `R-Ctrl` |
| 5 | `0x20` | `R-Shift` |
| 6 | `0x40` | `R-Alt` |
| 7 | `0x80` | *(no key — Right Win)* |

A **bare** modifier — bitmask set, usage 0 — is a real assignment and worth
naming in a full key listing. It is only uninteresting in an *Fn-shortcut*
list, where "Fn+Shift is still Shift" is noise; that filter now lives in
`keymap.is_bare_modifier`, asked for by the two shortcut builders, rather than
inside the decoder where it silently applied to combinations too.

### The data bytes of the lighting functions, as observed

Listing the copyable assignments for the GUI's remap page put them side by side,
which is the first time their data bytes could be compared. Read from this
keyboard:

| Shortcut | FunctionId | data |
|---|---|---|
| `Fn`+`↑` | 54 Cycle brightness | `[4, 0, 0, 0, 0]` |
| `Fn`+`↓` | 54 | `[4, 0, 1, 0, 0]` |
| `Fn`+`=` | 54 | `[1, 0, 0, 0, 0]` |
| `Fn`+`-` | 54 | `[1, 0, 1, 0, 0]` |
| `Fn`+`→` | 48 Lighting speed | `[0, 0, 0, 0, 0]` |
| `Fn`+`←` | 48 | `[0, 1, 0, 0, 0]` |
| `Fn`+`\` | 53 Cycle effect | `[1, 1, 0, 0, 0]` |
| `Fn`+`R-Alt` | 53 | `[4, 1, 0, 0, 0]` |
| `Fn`+`]` | 55 Cycle colour | `[1, 1, 0, 0, 0]` |
| `Fn`+`F12` | 45 Win/Mac layout | `[2, 0, 0, 0, 0]` |
| `Fn`+`L-Win` | 47 Lock the Windows key | `[2, 0, 0, 0, 0]` |
| `Fn`+`~` | 46 Show battery level | `[0, 0, 0, 0, 0]` |

The pairs that differ only in their direction differ in **one byte**, and not
the same byte: brightness in `data[2]` (0 up, 1 down), speed in `data[1]`.
`data[0]` varies between pairs that do the same thing (`Fn`+`↑` is 4 where
`Fn`+`=` is 1), so it is plainly not the direction.

**No meaning is claimed for any of this.** It is recorded because it is what the
device reports, and because the alternative — a UI offering "Cycle brightness"
four times with no way to tell the entries apart — is what made it visible. The
remap page sidesteps the question entirely by copying the whole five-byte value
and labelling it with the key it came from, so a user picks "what `Fn`+`↑`
does" without anyone having to know why it is a 4.

### How an unnamed `FunctionId` gets found

Read both layers and look for rows that fall through to the raw `fid=NN`
fallback. That is how `Fn`+`L-Win` turned up as function id **47** — an
assignment **the device profile does not contain at all**, so no amount of
checking against `0101.json` could have surfaced it. The vendor's index in
`docs/vendor-reference/device.js` names 47 `LockWin`, between
`ShowBatteryLevel` (46) and `LightingSpeed` (48), both of which this project
already trusts from that same list.

After adding it, all 166 assignments on this unit decode to a name and none
falls through.

### The device profile disagrees with the keyboard — 23 times

This is the most useful thing learned here, and it is a warning about every
other use of `ek75/data/0101.json`.

Sweeping the whole map and comparing it against the profile found **23
assignments that differ**. The divergence is systematic rather than random:

```
Fn + W A S D    profile: mouse cursor        keyboard: ordinary keys
Fn + Z X C V    profile: mouse buttons       keyboard: ordinary keys
Fn + [          profile: cycle effect        keyboard: the "[" key
Fn + Space      profile: cycle brightness    keyboard: Space
Fn + Delete     profile: Windows/Mac layout  keyboard: Delete
Page Down       profile: HID 75 (Page Up)    keyboard: HID 77 (End)
```

The entire mouse-emulation block is absent from this keyboard. The most likely
explanation is that `0101.json` describes a **different variant behind the same
PID** — Dareu's profile for `0101`, not Husky's Nomadic specifically.

**What the keyboard actually binds for lighting**, none of which the profile
gets right:

| Function | Keys |
|---|---|
| `BrightnessAdjust` (54) | `Fn`+`↑` `Fn`+`↓` `Fn`+`-` `Fn`+`=` |
| `LightingSpeed` (48) | `Fn`+`←` `Fn`+`→` |
| `LightingModeV2` (53) | `Fn`+`\` `Fn`+`R-Alt` |
| `LightingColorAdjustV2` (55) | `Fn`+`]` |

**This corrects an earlier claim in this file.** The Fn-shortcut section above
was derived from the profile and said this keyboard has no key bound to
`LightingSpeed` (48), so `Speed` could not be settled by watching the firmware
change its own state. That was wrong: `Fn`+`←`/`→` are exactly that, and the
experiment is available after all. What survives is the conclusion about
`LightingDirection` (49) — **no key binds it**, and that is now measured rather
than inferred from a source that turned out to be unreliable.

The consequence for the code: **the keyboard is the authority.** The GUI reads
the map from the device and lists nothing when none is connected, rather than
falling back to a profile known to be wrong for this unit. `open-ek75 keys
--diff` prints the divergence for any unit.

### `SetKeyAssign` — implemented, and how it was proven

    SetKeyAssign  HDR_SIZE=8, class 1, cmd 3|SET, HDR_PROFILE=profile
      payload:    [0]=keyId [1]=layer [2]=FunctionId [3..7]=FunctionData

Byte-identical to `GetKeyAssign` in the header; only the command byte and the
three extra payload fields differ. That matters for the risk analysis: payload
[0] and [1] were **already proven** to address the right key, because the GET
uses the same two offsets and returned the right key's data 166 times out of
166. Only [2] and [3..7] were unproven.

This project earlier stated that implementing this was circular — that
`restore` could not be the way back for the very command it is built from. That
was correct and it is what this section had to answer before any byte was sent.

#### The way back is not this project's code

    Fn + Esc  ->  function id 44, Factory reset

The firmware binds it. Read from the live key map, not from the vendor profile.
It runs on the keyboard, travels over no bus, and does not care whether
`SetKeyAssign` is broken — which is exactly what `restore` cannot claim. A
factory reset also clears the lighting configuration; that half already has a
confirmed `backup`/`restore`, so the recovery order is **Fn+Esc, then
`open-ek75 restore`**.

It has not been pressed. Testing the escape hatch means performing the
destructive act it exists to undo. Dareu's WebHID tool at `dr.dareu.com` is the
second hatch, and the one that requires trusting nothing in this repository.

#### The validation ladder, as actually run

Every step below was run on hardware, in this order, with the full 166-entry
map already saved to disk first.

1. **Byte-match test** against `tgdevice.js`.

2. **The identity write.** Write one key's *existing* bytes back to it
   (`Fn`+`[`, key id 50, layer 1, `fid=6 data=[0,47,0,0,0]`), then re-read the
   **whole map** and diff it. Result: ACK, **0 of 166 changed**.

   What this proves and what it does not: it proves the firmware parses and
   accepts a packet of this class, command, size and shape, and — via the wide
   diff — that the write did not land on some *other* key. It does **not**
   prove the write path executed at all: firmware commonly skips a flash write
   when the payload already matches. A narrow re-read of the one key would have
   proven even less, which is why the diff is over all 166.

3. **Two round trips on one expendable assignment.** `Fn`+`[` was chosen from
   the live map: it is on the Fn layer (the base `[` is never touched), and it
   is one of the 45 Fn assignments that are pure passthrough — it does nothing
   a user would miss. *An earlier draft named `Scroll Lock`; this is a 75%
   board and has no such key. Naming a key that does not exist is how a "safe
   test" becomes a packet aimed at an id nobody checked.*

   | Write | Read back | Collateral in the other 165 |
   |---|---|---|
   | `fid=6 data=[0,71,0,0,0]` (Scroll Lock, a key this board lacks) | exact | 0 |
   | `fid=8 data=[0,183,0,0,0]` (MediaKeys, consumer Stop) | exact | 0 |
   | revert to `fid=6 data=[0,47,0,0,0]` | exact | 0 |

   Trial A moves only the data bytes; trial B also moves `FunctionId`. Between
   them, offsets [2] and [3..7] are each confirmed by a change that produced
   exactly the requested read-back. Final whole-map diff against the
   pre-experiment capture: **0 changed**.

4. **The full restore.** `restore --keys-only` wrote all 166 assignments:
   166/166 acknowledged, and a whole-map diff against the original capture
   showed 0 divergences. It takes **~17 s** — roughly 100 ms per write, against
   ~9 ms per read. A key-map restore is not instant and the UI must not pretend
   it is.

#### What is deliberately still missing

There is no way to choose a *new* assignment — no remap command, no picker.
The only bytes this write can send are bytes read back from the same keyboard.
Selecting new functions is the next slice, and it is a UI problem (naming 57
function ids and the HID usage tables) rather than a protocol one.

## `CLASS_PROFILE` (5) — how many profiles, and which one is live

Implemented **read-only**. The official Windows app offers Profile 1 / 2 / 3;
this section is the half of that feature which can be proven without writing.

    PFL_CMD_ID_LIST  0   implemented (read)
    PFL_CMD_CREATE   1   write, persistent, its undo is untested
    PFL_CMD_DELETE   2   the undo for CREATE, itself untested
    PFL_CMD_ACTIVE   3   implemented (read); the SET is not
    PFL_CMD_NAME     4   no GetProfileName exists in the vendor source
    PFL_CMD_RESET    5   write, destroys a profile's contents

### `GetProfileIdList` — a multi-packet read, profile 0

    GetMultiPacketCmd(profileId=0, class=5, cmd=PFL_CMD_ID_LIST|GET, args=null)

Same machinery as `LED_CMD_ID_LIST`, same ProfileId 0 — asking which profiles
exist is not a question about one of them. It needed no new transfer code.

**Its post-processing is not the same, and this is the trap.** The LED list
collapses region ids 0 and 1 into whichever appears first; `GetProfileIdList`
ends with `ProfileList = new Uint8Array(DataArray)` and filters nothing.
Decoding the profile list by analogy with its sibling — the obvious move, since
both are multi-packet id lists — would silently swallow a profile. A test
asserts the two parsers disagree on one shared input.

### `GetActiveProfileId` — the answer arrives in the header

    HDR_SIZE=0, class 5, cmd 3|GET, HDR_PROFILE **not written**
      reply: profile id at HDR_PROFILE (byte 4), not at PAYLOAD_BASE

Both zeros on the way out are load-bearing: the request carries no payload for
`HDR_SIZE` to describe, and asking *which* profile is active cannot take a
profile id as input. Note the zero size is **not** shared with
`GetBatteryStatus`, the other profile-less read here — that one sets
`HDR_SIZE=3`. The two resemble each other in the profile byte only, which is
the kind of half-resemblance that gets a 3 written by analogy.

**Confirmed on hardware, with one honest limit.** The reply came back as:

```
02 00 05 83 01 00 01 00 ...
      ^  ^  ^     ^
      |  |  |     └─ byte 6, PAYLOAD_BASE — the same 01
      |  |  └─ byte 4, HDR_PROFILE — the byte the vendor driver reads
      |  └─ byte 3, command 0x83 = PFL_CMD_ACTIVE | GET_CMD
      └─ byte 2, class 5 = CLASS_PROFILE
```

This keyboard puts the id in byte 4 **and** byte 6, so it cannot tell the
header reading from the payload reading apart. The vendor driver is the only
reason to prefer the header — which is reason enough — but this is not a
confirmed byte position. A sibling model with only one of the two filled in is
what would settle it.

### What the keyboard actually answers

```
profiles: [1]   active: 1
```

**One profile, and it is the active one.** This project previously stated "this
code always uses profile 1" with nothing behind it; now it is measured. The
consequence for the feature the owner asked for: Profile 2 and 3 are not
hidden, they do not exist *on the device*. Creating one there needs
`PFL_CMD_CREATE`, a persistent write whose only undo, `PFL_CMD_DELETE`, has
never been sent to this hardware either.

That is not the same as saying the feature needs it. The next section is the
investigation into exactly that question, and its answer is that the
user-facing "Profile 1/2/3" is reachable with no device write at all — read it
before treating `PFL_CMD_CREATE` as the way in.

### Creating profiles 2 and 3: what the investigation found

Asked to look without writing anything. The answer reframes the feature.

**Nothing in the vendor's web driver creates a profile.** Counting definitions
against call sites in `tgdevice.js` — which is a device-communication library,
so read the limits of that on the next page before leaning on it:

| Command | Defined | Called |
|---|---|---|
| `GetProfileIdList` | 1 | 2 |
| `GetActiveProfileId` | 1 | 2 |
| `SetActiveProfileId` | 2 | 1 |
| `CreateProfile` | 1 | **0** |
| `DeleteProfile` | 1 | **0** |
| `ResetProfile` | 1 | **0** |

The three writes exist in the HID layer and nothing in the driver invokes them —
the same pattern as `MCO_CMD_SOTRAGE_INFO` and `MCO_CMD_MINI_DELAY`. The driver
reads whatever profiles the firmware ships with and switches between them. On
this keyboard that is one.

**How far that evidence actually reaches.** `tgdevice.js` is the device layer,
not the whole application: the site's UI code is not among the files in
`docs/vendor-reference/`, and it is where the macro *encoder* turned out to live
too. So the honest claim is "the driver's own orchestration never creates a
profile", not "nothing anywhere does". What makes it more than nothing is that
the sibling calls *are* here — `GetProfileInfo` calls `GetProfileIdList` and
`GetActiveProfileId`, and `TgKeyboard.SetActiveProfileId` wraps the setter — so
profile orchestration as a whole does live in this file, and creation is absent
from it.

Their packets are trivially known and identical in shape, which was never the
difficulty:

    CreateProfile / DeleteProfile / ResetProfile
      HDR_SIZE=0, class 5, cmd 1|SET / 2|SET / 5|SET, HDR_PROFILE=target

The difficulty is semantics, and there is **no reference flow to copy**: nothing
says whether creating switches the active profile, whether a new profile starts
empty or cloned, or what `DELETE` does to the one that is active. Sending them
would be guessing four answers at once with "the keyboard stops typing" as the
failure mode.

### "Profile 1 / 2 / 3" in the Windows app is a list on the PC — settled

This was left as "probably" and flagged as the one piece of work that would turn
it into an answer: the Windows app is a *second, independent* implementation and
could create device profiles through its own HID layer. It was checked, and it
does not.

`Central de Controle Husky.exe`, `DeviceBase.dll` and `Products/TK51G0101.dll`
were walked instruction by instruction (`dnfile` + `dncil`), resolving the
operand of every `call`/`callvirt` so the question is about edges rather than
about names appearing in metadata:

- **`DareuProducts.DeviceBase::CreateProfile` is `ldnull; ret`.** The base
  implementation returns null and does nothing. It is a virtual stub.
- **`DareuProducts.TK51G0101::CreateProfile`** — the override for *this exact
  model* — is a local object factory:

      newobj .ctor
      ldsfld s_profileDefault
      callvirt CopyFunctionParam

  It constructs a profile in memory and copies the embedded default into it.
  There is no packet, no HID call, nothing that reaches the keyboard.
  `s_profileDefault` is `DefaultProfile.xml`, the resource discussed above.
- **`DeleteProfile` is not overridden for this product at all.**
- The call sites are UI code: `OEMDriver.Pages.PageProfileConfig::
  ProfileOperationCopy` and `ProfileOperationImport`, working on an
  `ObscProfiles` observable collection through `get_Count` and `get_Name` — a
  list bound to a window, not a device.

So **both** vendor implementations agree, for different reasons: the web driver
defines the three `CLASS_PROFILE` writes and calls none of them, and the Windows
app's `CreateProfile` for this PID never leaves the PC. Profile 1/2/3 is an
application-side list, seeded from the factory template, applied to the one
device profile this keyboard has.

⚠️ **On trusting this kind of negative.** The first version of the script that
produced it found no call sites for *anything*, including `ToString` — its
reader did not implement dncil's interface and every failure was swallowed by a
bare `except`. It was caught by running it against a name that had to be there.
A tool that cannot find a positive cannot report a negative, and the control run
is part of the evidence: 3383 method bodies read, 0 failed, 52 `ToString` call
sites found.

### The safe way to ship this feature

Named local profiles — **implemented**: `core/profiles.py`, `open-ek75
profiles`, and the GUI's Profiles page. Several `backup`-format files, the user
picks one, applied through the existing `restore` path. Zero new device writes, zero new
packet shapes — and now known to be **what the vendor's own app does**, rather
than merely a safe substitute for it.

`PFL_CMD_CREATE` stays unsent. Not out of caution about an unknown any more, but
because nothing known uses it: two independent vendor implementations both
decline to, and this keyboard reports one profile because that is how many it
has.

What it would NOT give: switching profiles with a key on the keyboard, which
needs a real device profile and therefore `PFL_CMD_CREATE`. Nobody should send
that byte without a captured reference from the real Dareu software — the same
standard `CLASS_DFU` is held to, for the same reason: there is no way back that
does not depend on the thing being tested.

### What is deliberately not implemented

`SetActiveProfileId` is the interesting near-miss. Unlike CREATE it is
*reversible* — switch back — so it is the natural next write to validate. It is
still pointless until a second profile exists, and it is still a byte this
hardware has never been sent. Both reasons have to stop applying, not one.

## `CLASS_MACRO` (6) — reading what is stored

Implemented **read-only**, and it turned up something the project did not
expect: **this keyboard has a macro on it.**

    GetMacroIdList  GetMultiPacketCmd(profile=0, class=6, cmd=1|GET, args=null, width=1)
                    -> DataArray with every zero dropped

    GetMacroData    GetMultiPacketCmd(profile=0, class=6, cmd=5|GET,
                                      args=[macroId], width=2)
                    -> DataArray, verbatim

The device profile `0101.json` does not contain the word "macro", so the profile
would have said this keyboard has no macros. It has one, and only the keyboard
knows — the same lesson as the 23 key-map divergences, from a different class.

### Three id lists over one transport, decoded three ways

    LED_CMD_ID_LIST   collapses ids 0 and 1 into whichever appears first
    PFL_CMD_ID_LIST   filters nothing at all
    MCO_CMD_ID_LIST   drops every zero

Same command family, same multi-packet transport, three different rules in the
vendor's own driver. This is the clearest argument in the project against
porting one of these by analogy with its neighbour; a test asserts all three
disagree on one shared input rather than describing the difference in prose.

### `GetMacroData` exercises a transport combination nothing else does

It is the only command here that passes `GetMultiPacketCmd` an **argument** and
uses a **two-byte** length. The id sits at `PAYLOAD_BASE`, and the Total and
Offset fields the chunk requests add follow it, two bytes each, big-endian:

    00 | 35 | 06 | 85 | 00 | 00 | 03 | 00 64 | 00 00
                                     id   total   offset
    HDR_SIZE = chunk + args + 2*width = 48 + 1 + 4 = 53

Confirmed on hardware, which was not expected — the plan for this slice assumed
a keyboard with no macros would leave the combination untestable, and said so.

### What is stored, and what is not claimed about it

```
macros:   [1]
          1: 27 bytes  04 e0 0a 80 05 e0 0b 09 5e 04 e0 0a 6d
                       05 e0 0b 07 9d 04 e0 0a 5f 05 e0 0b 04 71
```

27 bytes is 3 x 9, and the groups are visibly regular:

    04 e0 0a XX      05 e0 0b YY ZZ      (x3)

**The format is not decoded and no meaning is claimed for it.** The vendor's web
driver passes macro data straight through — `SetMacroData` hands its argument to
`SetMultiPacketCmd` untouched — and the code that *builds* it lives in the
site's UI layer, which is not among the files in `docs/vendor-reference/`. The
repeating structure is recorded because it is reproducible and because whoever
implements the write half will want it, not because it has been understood.
(0xE0 is the HID usage for Left Ctrl, which may be a clue or may be a
coincidence; nothing here rests on it.)

### Deliberately not ported

- **`MCO_CMD_SOTRAGE_INFO` (0)** and **`MCO_CMD_MINI_DELAY` (6)** appear exactly
  once each in `tgdevice.js` — inside the enum that declares them. The vendor's
  own driver never sends either, so there is no reference packet and building
  one would be guessing.
- **`GetMacroName` (`MCO_CMD_NAME|GET`)** exists and the vendor **discards the
  reply**: it reads, ignores the result on both the success and the failure
  path, and returns the synthesised string `` `Macro ${id}` ``. Porting a read
  whose own author does not trust its output is guessing with extra steps. The
  GUI shows `Macro N` for exactly the reason the vendor does, and says so.
- **Every macro write** — `MCO_CMD_CREATE`, `MCO_CMD_DELETE`,
  `MCO_CMD_MEMORY|SET`, `MCO_CMD_NAME|SET`. All persistent, all going through
  `SetMultiPacketCmd`, a transport this project has never sent, and all of them
  needing the data format above, which is not decoded.

## `LED_CMD_FRAME` (4) — per-key colour, reconstructed but unsent

The biggest feature the official app has and this does not: painting each key
its own colour, and the audio visualiser, which runs through the same mechanism.
The packet layout below is complete. **Nothing here has been sent to a
keyboard.**

### The web driver is no help, and says so by omission

`CLASS_LIGHTING_CMD_LIST` declares nine commands. `tgdevice.js` sends three:

    LED_CMD_ID_LIST (0), LED_CMD_ATTRIBUTE (1), LED_CMD_EFFECT (2),
    LED_CMD_BRIGHTNESS (3)                                   <- implemented here
    LED_CMD_FRAME (4), LED_CMD_CAL_DATA (5), LED_CMD_CHARGE_CTRL (6),
    LED_CMD_DPI_STAGE_INDICATOR_COLOR (7), LED_CMD_CUSTOM (8)
                                    <- appear once each, in the enum, never sent

The same dead-enum pattern as the profile and macro writes. So this was
recovered from the **Windows app** instead, by walking `DeviceBase.dll`'s IL.

### The packet

`UsbHidDevice.TgUsbHidDevice::SetLedFrame`, the streaming overload. Its buffer
is offset by one against this project's, because it carries the HID report id at
index 0; the indices below are already corrected.

    HDR_STATUS   TargetId
    HDR_SIZE     6 + 3 * leds_in_this_packet
    HDR_CLASS    3   CLASS_LIGHTING
    HDR_COMMAND  4   LED_CMD_FRAME | SET_CMD
    HDR_PROFILE  not written
      payload[0]   region id
      payload[1]   flags — 0x01, OR 0x80 on the last frame
      payload[2]   frame number
      payload[3]   index of the first LED in this packet
      payload[4]   index of the last LED in this packet
      payload[5+]  R, G, B per LED, in order

`BLOCK_SIZE = 16`, read from `TgUsbHidDevice`'s constructor: sixteen LEDs per
packet, 48 colour bytes, 53 payload bytes in all. The single-frame overload is
the same command with the payload passed through whole and a cap of
`REPORT_SIZE - 1 - 6`.

**`HDR_SIZE` is 6 + 3n and the payload is 5 + 3n bytes.** That is not a typo
here: `build_set_lighting_effect` uses exactly `5 + 3n` for its own five payload
bytes, so the vendor's two commands disagree by one. Transcribed as found rather
than corrected — a "fix" would be this project inventing a byte the firmware may
well be counting.

`payload[0]` is the region id by inference, not by capture: every other
`CLASS_LIGHTING` command puts it there, and `TgDevice::SetMultiLedFrame` looks
up `RegionList[index]` and the matching `LedParams[index]` before handing off.
Strong, and still an inference.

### What is still missing before this can be sent

- **What a frame means to the firmware.** The byte layout is known; whether a
  frame persists, how many frames a sequence may have, and what the device does
  between frames are not.
- ~~**Which LED index is which key.**~~ **Done.** `TK51G0101::_matrixIds` is a
  90-entry int32 array in the product DLL's `FieldRva` data: six rows of
  fifteen, row-major, holding the KeyID at each LED position and 0 where there
  is no key. It is transcribed into `core/vendor_tables.KEY_MATRIX` and reads
  as the physical keyboard:

      Esc  F1  F2  F3  F4  F5  F6  F7  F8  F9 F10 F11 F12   ·   ·
        ~   1   2   3   4   5   6   7   8   9   0   -   = Bksp PgUp
      Tab   Q   W   E   R   T   Y   U   I   O   P   [   ]   \  Del
     Caps   A   S   D   F   G   H   J   K   L   ;   '   · Entr PgDn
    LShift  Z   X   C   V   B   N   M   ,   .   / RShift Up   ·   ·
     LCtrl LWin LAlt ·   · Space  ·   ·   · RAlt  Fn RCtrl Lft Down Rgt

  Checked against `0101.json`, which is public and was not involved in
  producing it: every id exists there, none repeats, the shape is the 6x15 the
  keyboard reports for region 1 through `LED_CMD_ATTRIBUTE`, and the only keys
  absent are 170-172 — `Mute`, `Volume +`, `Volume -`, the knob, which has no
  LED under it. Four independent ways for a bad transcription to show, and none
  of them did.
- **A way back.** Lighting is the safest write class here — `backup`/`restore`
  are confirmed — so this is a question of sequencing, not of danger.
- **`SaveCustomLed`**, which the app calls after streaming. Unread.

### `_brightnessLevel`: the Fn brightness ladder, probably

The product DLL's other `FieldRva` entry is five bytes — `0, 70, 120, 190, 255`
— and `TK51G0101::get_BrightnessLevel` returns a field of that name. Five steps
is what `BrightnessAdjust` on `Fn`+`↑`/`↓` would cycle through, and 255 is
`BRIGHTNESS_MAX`.

Inferred, not confirmed: nobody has watched the stored brightness walk those
values. It is cheap to settle and costs no write — `watch 1` while pressing
`Fn`+`↑`, the same experiment that settled the speed range.

### The other half: `SetAudiovisualizerParam`

`ILedTg.SetAudiovisualizerParam` is on this product's interface list, so the
audio visualiser is a feature of this model and not of a sibling. It is not in
the web driver either. Unread.

## What is not implemented yet

- **Multi-colour effects** — implemented for the effects that use them.
  `Breathing` and `Starlit` take a list and the GUI offers one for them;
  everything else draws `colors[0]` and gets a single picker. See "The colour
  list is used by some effects, over time". What is still open is `Starlit`,
  which nobody has looked at, and how far past three `Breathing` really walks.
- **`Flag` (direction)** — resolved on paper by two independent vendor
  implementations, stored faithfully by the firmware, and **confirmed not to be
  rendered** on this model. The control stays visible in the GUI with a label
  saying so. This bullet used to read "nothing has been written to hardware
  except `LED_CMD_EFFECT`"; that stopped being true when the brightness write,
  `SetKeyAssign` and the key-map restore were each confirmed on hardware.
- ~~**`Speed`, visually**~~ — **done.** `Wave` at speed 1 and at speed 3, with
  every other field held identical, is visibly faster at 3. See "`Speed` is
  rendered" above. It is the only one of the three unknown fields that turned
  out to work.
- **Effect ids 130 and 141** appear in the Windows app's direction and speed
  tables but are outside `TG_LIGHT_EFFECT_INDEX` (0-32). Probably the app's
  software-rendered effects, streamed as frames. Unverified.
- **`SetTimeToSleep`** — bytes known, deliberately unshipped; see `CLASS_POWER` above.
- **Choosing a new key assignment.** `SetKeyAssign` is implemented and
  confirmed (above), but its only caller is `restore`: the bytes it sends are
  always bytes read back from the same keyboard. A remap command needs a way to
  *name* 57 function ids and the HID usage tables, which is a UI problem, not a
  protocol one.
- **Every `CLASS_PROFILE` write** — `PFL_CMD_CREATE`, `PFL_CMD_DELETE`,
  `PFL_CMD_ACTIVE|SET`, `PFL_CMD_RESET`. The two reads are done and say this
  keyboard holds exactly one profile; see `CLASS_PROFILE` above for why
  creating the other two is its own slice.
- **Every `CLASS_MACRO` write**, and the macro data format itself — see
  `CLASS_MACRO` above. The two reads are done and this keyboard reports one
  stored macro.
- **Everything outside `CLASS_LIGHTING` and the two `CLASS_POWER` reads**:
  `CLASS_BUTTON`, `CLASS_SENSOR`/`CLASS_MAGNETIC_AXIS` (this
  model may not be Hall-effect, but the class exists in the shared
  framework), `CLASS_AUDIO`, `CLASS_LCD`, `CLASS_TEST`. Of `CLASS_POWER`, the
  two reads are done; what remains there is `TIME_2_DIM` (this keyboard does not
  answer it), `LOW_INDICATOR_CTRL`, `MAX_LED_BRIGHTNESS`, `ADC`,
  `USB_TIME_2_SLEEP`, and the `SetTimeToSleep` write above.
- **`CLASS_DFU` (9) — do not touch without a very good reason.** This is the
  firmware-update class. `tgdevice.js` implements it (`TgKeyboard` extends a
  base with DFU methods used by other product lines in the same framework),
  which means the *capability* exists in this keyboard's firmware even
  though nothing here exercises it. A wrong `CLASS_DFU` command sent from
  first principles, without capturing what the real Dareu updater sends
  first, risks bricking the keyboard. If this is ever pursued, do it by
  capturing `dr.dareu.com`'s firmware-update flow (WebHID traffic via
  `chrome://device-log` or a USB capture), never by guessing from the class
  list alone.

## What to try next

0. **`open-ek75 probe`** — read-only, writes nothing, and answers most of the
   questions below at once: which profiles exist and which is active, does
   `LED_CMD_ID_LIST` work on this unit, what does `LED_CMD_ATTRIBUTE` say each
   region's real effect list is, and what is every region's current state. Run
   this before anything else below.

1. **`open-ek75 watch 1`, then press the Fn lighting shortcuts.** Writes
   nothing: the firmware changes its own state and `watch` prints which field
   moved. This model binds four of them (see "The Fn lighting shortcuts"
   below) — effect, colour, brightness and speed — **but not direction, which
   no Fn key on this keyboard is bound to.** `Flag` can only be confirmed by
   writing it and looking at the keyboard.

   Speed is **done**: pressing `Fn`+`←`/`→` walked the stored value
   3 → 2 → 1 → 2 → 3 → 2 and never left 1-3, confirming the range without a
   single write (see "`Speed` is 1-3"). This entry was previously written as
   settling only three fields, because the vendor profile does not show the
   `Fn`+`←`/`→` binding and the live key map had not been read yet.

2. **`Wave` with each direction — the single most valuable test left.**

   ```bash
   open-ek75 set 1 wave 255 0 0 --speed 2 --flag 0
   open-ek75 set 1 wave 255 0 0 --speed 2 --flag 1
   ```

   `Wave` is the one effect the vendor gives a direction control, so this is
   where a wrong reading of `Flag` shows up immediately: if the animation
   reverses, the Windows app's meaning is confirmed on this firmware. It cannot
   be settled any other way — this keyboard has no Fn key bound to
   `LightingDirection` (see "The Fn lighting shortcuts"). Fully reversible with
   `backup`/`restore`.

3. **`Speed` 1 vs 3 on `Wave`** — the same command with `--speed 1` and
   `--speed 3`. The *range* is settled (above); what is still unobserved is
   whether the number changes how fast an animation actually runs, because
   everything sent before `Wave` was a non-animating effect. Watching the
   stored value move proves the firmware accepts and keeps it, not that it
   renders it — the same gap that `Flag` turned out to fall into.

4. ~~**Multi-colour effects**~~ — **done, and the answer depends on the
   effect.** `Breathing` cycles the whole list, one colour per breath, in
   order. `Static` and `Wave` draw only the first. The vendor's own per-effect
   table agrees and names `Starlit` as the other multi-colour one. See "The
   colour list is used by some effects, over time" above.

   Two answers were written here before this one. The first said "not tried";
   the second said "the answer is no", from looking at `Static` and `Wave` and
   generalising. What the second one missed is that a list can be spent over
   **time** rather than across the keys, which no single glance can see. It is
   the most instructive wrong answer in this file.

   **Still open:** `Starlit` (11) has not been looked at, and the vendor caps
   both multi-colour effects at two while this firmware cycled three — so how
   many `Breathing` really walks, up to the five the wire allows, is unmeasured
   past three.
5. If you have a **different PID** in this family (check its `FwType` at
   `https://dr.dareu.com/products/<PID>/<PID>.json` first — this exact
   `find_device()`/packet layout only applies to `FwType: 0`), the read path
   (`regions`/`backup`) is safe to try immediately: it never writes anything.
