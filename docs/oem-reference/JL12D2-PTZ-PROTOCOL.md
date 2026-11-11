# JL12D2 head protocol (Pelco-D and AF frames)

The JL12D2 (also sold as the MCL12D2; SSC377D SoC, IMX335 sensor) has an integrated pan, tilt, zoom, focus and IR-cut head that the SoC drives over one serial port. This page is the reverse-engineered protocol on that port and the head's measured behaviour, so a firmware can reproduce what the stock firmware does. How the Thingino port uses it (lensd, lensctl, the ONVIF mapping) is described with the port, not here. The day/night half of the AF frame has its own page: [JL12D2-IRCUT-MECHANISM-RE.md](JL12D2-IRCUT-MECHANISM-RE.md).

The evidence is a static disassembly of the V3.3.2.4 OEM binaries (2026-10-24), then captures on stock and on Thingino units from 2026-10-25 to 2026-11-08 ([Evidence and method](#evidence-and-method)). Where a capture and the disassembly disagree, the capture wins; where two captures disagree, the later one is stated and the earlier one named.

## At a glance

- One port, `/dev/ttyS2` at 57600 8N1, carries everything: Pelco-D commands (address 01) to the head, and one 16-byte AF frame per sensor frame from the SoC, which feeds the head's own focus search and carries the day/night flag that moves the IR-cut filter.
- The head answers only a status query (`FF 01 9A`), about 0.55 s late, and the answer holds the zoom position only. There is no pan or tilt position feedback by any command.
- While zooming it streams its own 1-30 zoom number. It raises no motion flag during a preset recall or a zoom.
- Board presets 1-32 store a position. Higher numbers are function presets, and their numbers depend on the unit's OEM config.
- Optical zoom: about 13.5x by image cross-correlation and about 10.6x by the FOV table, against the "20x" (4.7-94 mm) it is sold as. The wide end is 48.1 x 36.1 deg.
- Pan and tilt ramp up to a top speed that the Pelco-D speed byte sets: at level 10, 24.76 deg/s pan and 16.77 deg/s tilt.

## Transport

- **Device:** `/dev/ttyS2`, the FUART (`serial2 = fuart@1F220400`, pads `PAD_FUART_RX`/`PAD_FUART_TX`), not UART1. `comm_server` always opens `/dev/ttyS2`; the config's `[Ptz] ComPort` is ignored.
- **Baud: 57600, 8N1, raw.** The config's `BaudRate="9600"` is only logged; `comm_server` uses 57600 because `af.flag` is present. Read back off the live stock port (2026-10-25) and confirmed by a sweep on Thingino (2026-11-08): the status query answers only at 57600, and 9600, 38400 and 115200 are silent. Nothing is hidden behind another baud.
- **termios:** `c_cflag = CREAD | CLOCAL | CS8`, iflag, oflag and lflag 0, VMIN = VTIME = 0, `TCSANOW`.
- **Wiring:** the head's plug has 4 pins and two wires and sits on the 5-pin D7 header, seated from the right. Seated one pin to the left, the head's TX lands on a SoC output: the link is dead both ways and the head keeps resetting, so the lens "wanders" through calibration sweeps.
- **Who writes on stock:** `comm_server`'s `thread_comm` does all the writing (fd 6), seen in the captures of 2026-10-25, 2026-10-27 and 2026-11-08. `media_server` computes the AF data and hands it over IPC (`AuxMsgAfData*` in `libtools.so`). The reply parser that the disassembly found is in `media_server` (0xdd5dc); `media_server` holds the port open but made no read and no write on it during the 2026-10-27 capture. An earlier note's "mainctrl = PTZ steering" is wrong.
- **Reply latency:** the head answers a query 525-585 ms later, often split across two reads, so reassemble the full frame. A listen window under about 600 ms misses the reply entirely; that is the one real "are we seeing every packet" trap, and it is timing, not baud. With a 900 ms window and about 1 s between queries, five of five status queries were answered, all with valid checksums (2026-11-08).

## Lens board start-up

- **Version:** the board reports `CAM-YS183-AJ3-2.80 Dec  2 2025` to `VER`, but only shortly after its own power-up; stock caches the reply in `/tmp/AF_version.txt`. A driver that starts later (on Thingino, lensd starts after raptor, about 20 s in) gets no reply. That is harmless.
- **Stock start-up** (`bSendOnStart=1`): a version handshake first (`"END"+D7` eight times at 60 ms, then `"VER"+ED`, falling back to `"EXVER"+8A`), then AF-frame forwarding starts at boot rather than after the first move. No lens-type or zoom-curve command was found. `BootAction=0`: no position reset at boot.
- **No wake-up is needed.** majestic-af's Pelco-D lens tool sends one (the frame `51 01 04 79 01 0d 0a 2e 02 7e 00 00 00 95`, calls of presets 0x53 = 83 and 0x52 = 82, then aux night/day); it was sent once on a Thingino unit before autofocus was confirmed. From a cold power-on, with a driver that sends no wake-up and none of the GPIO writes copied off stock, the lens refocuses after every zoom (2026-10-25). What a call of 82 or 83 does depends on the unit's function-preset map ([Presets](#presets)).

## Pelco-D commands

Standard Pelco-D, `FF addr cmd1 cmd2 data1 data2 ck`, address `01`, `ck = sum(bytes 1..5) & 0xFF`. Pan speed goes in data1, tilt speed in data2 (`pp` and `tt` below). The OEM command templates are in `comm_server`'s `.data` (0x3f600).

| Action | Frame |
|---|---|
| Up | `FF 01 00 08 00 tt ck` |
| Down | `FF 01 00 10 00 tt ck` |
| Left | `FF 01 00 04 pp 00 ck` |
| Right | `FF 01 00 02 pp 00 ck` |
| Up-left / up-right | cmd2 `0C` / `0A` |
| Down-left / down-right | cmd2 `14` / `12` |
| Stop | `FF 01 00 00 00 00 01` |
| Zoom in | `FF 01 00 20 pp tt ck` |
| Zoom out | `FF 01 00 40 pp tt ck` |
| Focus far | `FF 01 00 80 00 00 80` |
| Focus near | `FF 01 01 00 00 00 01` |
| Preset set | `FF 01 00 03 00 NN ck` |
| Preset goto | `FF 01 00 07 00 NN ck` |
| Preset clear | `FF 01 00 05 00 NN ck` |
| Status query | `FF 01 9A 00 00 00 9B` |

- **Vendor cmd2 extensions:** `A1` light-alarm on/off, `97` PTZ reboot, `A3` guard preset.
- **Zoom carries no speed.** Stock sends `01 01` in the data bytes at every speed: zoom in `ff 01 00 20 01 01 23`, zoom out `ff 01 00 40 01 01 43`; with `00 00` there the frame is ignored. The speed setting changes the pan and tilt byte only, through the web UI, the CGI and ONVIF alike.
- **Stop:** the stock ONVIF and web-UI stop is a status query `ff 01 9a 00 00 00 9b`, then `ff 01 00 00 00 00 01` five times about 50 ms apart. `/cgi-bin/ptz_ctrl?stop=1` sends the stop once, with no query.
- **Absolute move** (`web_server`'s `__tptz__AbsoluteMove`, behind the `absolute_move_onvif` flag, which is set): `FF 01 99 PH PL TH TL SX SY ZH ZL SZ CK`. Positions are `((v*100+100)/2)*65535/100`, giving 0..65535; speeds 0..255 (`FF` = unspecified); `CK = sum(bytes 1..11)`. On stock only its zoom axis could be confirmed ([Stock ONVIF behaviour](#stock-onvif-behaviour)). `move3DPoint` (`FF 01 93 …`) is gated to other product types and not used on this model.
- **No mixed moves:** the head latches an axis and slows diagonals ([Head kinematics](#head-kinematics)), so a driver that times its moves runs one axis at a time.

### Speed byte per level

Stock's speed level (the web UI's Speed, 1-10, default 5, and `/cgi-bin/ptz_ctrl?speed=`) sets this pan and tilt byte, measured on the wire:

| Level | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
|---|---|---|---|---|---|---|---|---|---|---|
| Byte | `01` | `04` | `0a` | `12` | `19` | `20` | `27` | `2e` | `35` | `3f` |

Stock's ONVIF `ContinuousMove` with velocity v sends the byte for level `floor(10v) + 1`, capped at 10: 0.1 gives `04`, 0.25 `0a`, 0.5 `20`, 0.75 `2e`, 1.0 `3f`.

### ONVIF to Pelco-D on stock

Sniffing `comm_server`'s writes while an ONVIF client drove the PTZ move suite against stock firmware (2026-11-08) reproduced the 2026-10-25 capture byte for byte. Nothing new turned up: no further head feedback and no further command. The host-to-head frames:

| ONVIF verb | Pelco-D frame |
|---|---|
| Pan right / left | `FF 01 00 02 20 00 23` / `FF 01 00 04 20 00 25` |
| Tilt up / down | `FF 01 00 08 00 20 29` / `FF 01 00 10 00 20 31` |
| Zoom tele / wide | `FF 01 00 20 01 01 23` / `FF 01 00 40 01 01 43` |
| Stop | `FF 01 00 00 00 00 01` |
| Status poll, about every 2 s | `FF 01 9A 00 00 00 9B` |

The AF feed (`51 01 04 78 01 0d …`) streamed on unchanged throughout. It carries no motion: every pan, tilt and zoom move is an `FF 01` Pelco-D frame. (An earlier note read `01 0d` as a pan/tilt command; that is wrong.)

## Position feedback and replies

- **Only the status query returns status.** A sweep on Thingino (2026-11-08) sent `FF 01 CC 00 00 00 ck` for every CC from 0x80 to 0xA5 (skipping the movers 0x93 and 0x99), and the 0x78 vendor forms `52` (init), `89` (query), `79`, `90` and `22`: all silent. There is no hidden pan/tilt position query.
- **Reply framing** (disassembly, `media_server`'s parser at 0xdd5dc): `51 01 04 RW TYPE LEN <data> CK`, with `CK` the sum of all earlier bytes, `& 0xff`.
  - RW `78`, TYPE `90`, LEN `07`: pan16, tilt16, zoom16 (big-endian) and one more byte. ONVIF value = `2*raw/65535 - 1`.
  - RW `90`, TYPE `22`: zoom ratio = `(hi*256+lo)/10`.
  - Other TYPEs: OSD text (`63`, `64`, `E1`), manual-focus mode (`CF`), alarm bits (`79`, `91`).
- **The status reply as measured** (2026-10-25, again 2026-11-08) is `51 01 04 78 90 06 PH PL TH TL ZH ZL CK`: LEN `06`, not `07`.
  - Pan and tilt read `0000` at every zoom and every position. The head has no pan or tilt encoder.
  - zoom16 is the zoom position: `0000` at the wide end, `ffff` at the tele end (`92f7` at board zoom step 12, `d747` at 19), readable at any time, not only while zooming. ONVIF's zoom space is 0..1, so the ONVIF zoom is `raw/65535`. It tracks: `0x0000` wide, `0xAF2F` after a 2.5 s zoom-in, `0x0000` again after zooming back.
- **The zoom-number stream:** during a zoom the head streams frames at about 10 Hz: `51 01 04 78 01 07 0b 1a D1 21 26 26 26 CK` (one digit) or `51 01 04 78 01 08 0b 1a D1 D2 21 26 26 26 CK` (two digits). The digits are the board's own zoom number, 1 (wide) to 30 (tele), counting up on a zoom-in and down on a zoom-out.
  - It is not optical magnification ([Zoom range and field of view](#zoom-range-and-field-of-view)).
  - `[I]` The stock overlay shows 1X-30X while zooming, the same range, so this number is probably its source; but the board also sends `1 0` at the wide end, so the mapping is not settled.
- **The motion flag:** the board was seen to send `51 01 04 78 88 02 01 02` when it starts moving and `51 01 04 78 88 02 01 00` when it stops (2026-10-25). It sends no flag during a preset recall (2026-10-26, again 2026-11-06), none for a zoom (2026-11-08: the zoom-number stream is the only sign), and for pan and tilt no flag outlasts the stop. So a driver cannot take "moving" from the board during a recall; it has to time the recall itself.

## Presets

- **Board presets** are stored by the head (Pelco-D set `03`, call `07`, clear `05`); a set position is recalled to within a few pixels.
- **Only presets 1-32 store a position.** A set and then a call of 33 leaves the head where it is (2026-10-26: store, pan away, call, no movement; the same test on 32 comes back to within noise). Thingino's lensctl therefore keeps user presets on board presets 1-31 (slots 0-30) and home on 32; an earlier build put home on 33, so its home button did nothing.
- **Recalls** take the short way round and turn all axes at once. Timed on the video on a Thingino unit (2026-11-08): about 0.4 s to start, then about 24 deg/s pan and about 18 deg/s tilt, so about 8 s for about 180 deg (a recall from about 185 deg away took 8.15 s). The earlier timing (2026-11-06) gave about 4 s from 90 deg away and about 7 s from 180; the 2026-11-08 timing supersedes it. A 180-deg recall landed about 0.4 deg off the stored spot (2026-11-06). No motion flag is raised.
- **Function presets** are higher numbers that the OEM config maps to head functions, and the numbers differ between config versions. Read the unit's own `config.xml` before assuming one.
  - One unit's live `/mnt/nand/config.xml` (from Jennov's `/mnt/nand/cust/config.default.xml`): LeftMargin set 35, RightMargin set 36, AreaScanOn call 38, AreaScanOff set 38, CruiseOn call 41, CruiseOff set 255, HumanTraceOn call 92, HumanTraceOff call 94, PtzRestore set 107 then call 64. The 81/82/83 margins and area scan in `/opt/ch/config.default.mcl12d2.xml` are the generic Anjvision defaults, which the Jennov file overrides on that unit.
  - Another unit's live config (2026-11-08): HumanTraceOn call 97, HumanTraceOff 96, CruiseOn 101, CruiseOff 255, LeftMargin 81, RightMargin 82, AreaScan 83.
- **HumanTrace does nothing on this head.** On that other unit, on stock (2026-11-08), with `track_human="1"` set, `media_server` restarted to re-read it, person detection armed by day, and HumanTraceOn (preset 97) accepted over ONVIF (HTTP 200), a person moving in view for 60 s produced 1472 AF frames and no `FF 01` move frame. The OEM's detect-to-track path never reaches the Pelco-D head on this model, so tracking needs an outside detector driving ONVIF moves.

## Head kinematics

Measured under Thingino on one unit at the wide end (2026-11-06), with lensd timing each move to about 2 ms. The ruler is the camera's own image: snapshots before and after each move and back, at four or five lengths per level, the shift found by cross-correlation. Degrees are linear in the frame (as the ONVIF FOV space is) and scaled to true degrees by a full pan turn of identical steps. The bench scene was near (a few metres); a second unit with a far scene agreed within about 4 % on pan at every level and about 5 % on tilt at levels 1-9.

| Level | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
|---|---|---|---|---|---|---|---|---|---|---|
| Pan, top speed (deg/s) | 1.30 | 1.65 | 2.53 | 4.18 | 5.75 | 8.17 | 12.58 | 17.08 | 20.37 | 24.76 |
| Tilt, top speed (deg/s) | 1.58 | 1.98 | 2.93 | 4.57 | 5.92 | 7.80 | 10.89 | 13.36 | 14.86 | 16.77 |

- **The head ramps.** A move of t ms turns `v * (t - L - R/2)` once past its ramp: dead time L, then an even ramp of R ms to the top speed v.
  - Level-10 pan: L 120 ms, R 620 ms (about 0.6 s of ramp).
  - Level-10 tilt: L -140 ms (it runs on past the stop), R 1140 ms.
  - At 300 ms every level from 5 to 10 has turned the same 0.8 deg pan and 1.5 deg tilt, so the acceleration is shared and the byte sets only the top speed, which saturates near level 10.
  - The fit per level is good to 0.01-0.13 deg rms. Levels 1-4 were measured past their ramp only, so their L and R are pinned down only as `L + R/2`. Every level's L and R are in thingino-lensd's `heads/ys183.conf`.
- **The head latches an axis.** A frame that drops an axis (up-right, then right) leaves the dropped axis running, even straight after a stop frame.
- **Diagonals are slower.** A diagonal turns each axis slower than alone (level 10: pan -20 %, tilt -8 %). With the latch, this is why a timed move runs one axis at a time: pan, a stop, then tilt.
- **Stops:** no motion flag outlasts the stop. Thingino's lensd, which sends five stop frames, reports idle about 0.26 s after the move's time.
- **Recalls:** see [Presets](#presets).
- **Snapshots for this kind of measurement:** on Thingino, `raptorctl rvd save jpeg` hands back the frame encoded at the previous save (the substream JPEG runs at 1 fps), so prime each snapshot with a save first.

## Zoom range and field of view

The head is sold as a 20x zoom (4.7-94 mm). Measured, it is about 13.5x optical, the same on both units measured:

- **Image cross-correlation** of the wide and tele ends: 13.3x on a Thingino unit, 13.9x on a stock unit.
- **An absolute check on stock** with a 2 ft level at about 28 ft: wide HFOV about 44.5 deg (the level = 268 of 3072 px), tele HFOV about 3.5-4 deg (the frame just narrower than the level), so about 11.5-13.5x. If stock's 3072x2048 stream spans the full sensor width (5.18 mm), that is roughly 6.3 mm to 85 mm, short of the advertised 4.7-94 mm at both ends. Whether the head stops short of the lens's wide end is not known.
- **The FOV table** (below) gives about 10.6x: 48.1 deg at the wide end, 4.5 deg at zoom readout 62071, within about ±13 %. `[I]` It reads lower than the cross-correlation partly because its last point is 62071, short of the tele end at 65535, so the lens zooms on past it; the table's own ±13 % may account for some of the rest, and the remainder is not explained.
- **The board's zoom number** runs 1 (wide) to 30 (tele), and stock's on-screen zoom shows the same 1X-30X. An ONVIF zoom-in on stock stops at 30X; its digital zoom (`DzoomConfig multiple_max="10.0"`) did not engage. The number is not the optical magnification.

The wide-end FOV is **48.1 x 36.1 deg**: 48.1 across from the full pan turn of 2026-11-06, and the vertical from the 4:3 frame. The 44.5 deg above was the older stock estimate made with the level.

FOV against the zoom readout (zoom16 to HFOV in deg, on the far-scene unit, the same small pan at each zoom, about ±13 %):

| zoom16 | 0 | 6683 | 14279 | 19851 | 31071 | 39071 | 45771 | 62071 |
|---|---|---|---|---|---|---|---|---|
| HFOV (deg) | 48.1 | 46.8 | 37.6 | 31.2 | 20.1 | 14.6 | 10.1 | 4.5 |

How the zoom moves:

- By the board's zoom number the lens zooms about 6 steps/s, wide to tele in about 5 s, measured the same on stock and on Thingino (2026-10-25).
- Timed zooms against the readout (2026-11-07, 100 ms to 3 s, both ways): the board moves the zoom in 50 ms ticks. A zoom command of 130 + 50k ms moves about 52 units plus k ticks, the same both ways; 150 ms or less moves just the 52 or so. Now and then it moves a tick more, or ignores the command. The speed is about 20.2 units/ms up to about 44000 and falls toward tele, to about 4.5 units/ms at the end. A full tele-to-wide move takes about 7.5 s.
- So short zoom commands move it very unevenly (120 ms gives about 50 units, 250 ms about 2000). Steer the zoom by its readout, not by time.

## The AF frame

The SoC sends the head one 16-byte frame per sensor frame:

```text
51 01 04 78 01 0d  FVa_H FVa_L  FVb_H FVb_L  L  S1 S2 S3 S4  CK
```

| Byte | Field | Meaning |
|---|---|---|
| 0-5 | `51 01 04 78 01 0d` | header: `51 01 04`, command `0x7801` (the AF command), length `0x0d` |
| 6-7 | FVa | focus value of AF window 0, big-endian |
| 8-9 | FVb | focus value of AF window 1, big-endian |
| 10 | L | a brightness (AE) value: `08`/`09` (2026-10-25), `01` (2026-10-27), about `06` (2026-11-08) |
| 11 | S1 | the day/night flag: `00` day, `01` night; the head moves the IR-cut filter from it |
| 12 | S2 | `03` in both stock captures; meaning not known |
| 13 | S3 | `00` by day, `0x32` about 1 s into night (a night-mode parameter) |
| 14 | S4 | `00`; meaning not known |
| 15 | CK | `sum(bytes 0..14) & 0xff` |

- **A stock frame by day** (2026-11-08): `51 01 04 78 01 0d 3c 98 1b 2c 06 00 03 00 00 00`; the bytes before the last sum to 512, so `CK` is `00`.
- **S1..S4 by day** are `00 03 00 00` in the two stock captures (2026-10-27 and 2026-11-08). The 2026-10-25 notes give `01 00 02 00` throughout, the values the Thingino driver was first built with; the later captures supersede them. Bytes 11 and 13, and the capture of a day-to-night flip, are in [JL12D2-IRCUT-MECHANISM-RE.md](JL12D2-IRCUT-MECHANISM-RE.md).
- **FVa and FVb** are `(f0 + f1 + f3 + f4) >> 9` of AF window 0 and window 1, from `MI_ISP_CUS3A_GetAFStats` (5 fields x 16 windows of 40-bit counters; the call writes 7168 bytes). Fit to the wire over 83 frames with a relative error of 1e-4 (2026-10-25). The stats are readable from a process other than the ISP owner.
- **AF configuration:** stock sets window 0 to (19,19)-(1003,1003) and window 1 to (170,170)-(850,850) on the 0-1023 grid, plus its own AF filter and filter-sq; the other nine `MI_ISP_CUS3A_*AF*` structs match the vendor defaults. Without stock's windows the focus values are about 100x smaller.
- **Where it comes from** (disassembly): `AfConfig type="2"` selects `CAfV3`. `CAfV3::Thread_Handle` runs once per ISP frame, reads the CUS3A AF statistics (MI_ISP call id `0x2e0d`) and builds the frame: `FVa`/`FVb` = `(sum of four 40-bit stat values >> 6) >> 3`, from stats offsets {0, 80, 240, 320} and {5, 85, 245, 325}. The wire fit above confirmed this. OpenIPC's majestic-af, autofocus for the same hardware class (a Pelco-D lens head on `/dev/ttyS2` at 57600 on SigmaStar), reverse-engineered the same CUS3A AF statistics independently (control `0x2E0D` = 11789; fields IIRH, IIRL, SBLV, SBLH, Luma).
- **The head runs the focus search itself.** After a zoom stops it refocuses from the focus values alone, in about 1.3-2 s, the same on stock and on Thingino. A firmware therefore needs no focus loop of its own, but it must stream this frame every video frame, or the lens will not focus after a zoom.
- **Rate:** one frame per sensor frame. On Thingino that is 20 Hz on the JL12D2 profile (20 fps). The stock captures recorded 20 Hz (2026-10-25), 25 Hz (2026-10-27) and about 27 Hz (2026-11-08); the stock rate is listed under [Unverified](#unverified).
- **Idle on stock** (no PTZ, no target): only these AF writes, no `FF 01` frame and no head replies. The head speaks only when queried.

## Stock ONVIF behaviour

The stock ONVIF PTZ was exercised over the network before the first reflash (2026-10-24, an ONVIF test script), as the known-good reference:

- **Zoom works.** `ContinuousMove` zoom in and out moved the `GetStatus` zoom from -0.23 to +0.43 to -0.24; `AbsoluteMove` zoom 0 recentred it to about 0. The zoom read-back is accurate.
- **Pan and tilt are accepted but not reported.** Every `ContinuousMove` and `Stop` returned a clean response, but the `GetStatus` pan/tilt sat at a constant -1/-1: there is no pan/tilt encoder, and only the zoom comes back. Motion was confirmed by eye, not by telemetry. A driver for this head can report the zoom position only.
- **Presets:** `SetPreset` returned token 1 and `GotoPreset` was accepted. `AbsoluteMove` was accepted (its zoom axis confirmed). `Stop` halts motion.
- The Pelco-D frames each verb sends are in [ONVIF to Pelco-D on stock](#onvif-to-pelco-d-on-stock).

This is OEM behaviour to reproduce, not something to build on.

## Evidence and method

| Date | What | How |
|---|---|---|
| 2026-10-24 | The OEM V3.3.2.4 binaries: `comm_server`, `media_server`, `web_server` (the OEM rootfs's `/opt/ch/`), `libtools.so`, and the device tree in the OEM kernel; stock ONVIF PTZ over the network | static disassembly; an ONVIF test script |
| 2026-10-25 | Port settings, AF frame, commands, replies, version, zoom range, function presets, on a stock unit; reproduced on a Thingino unit, where autofocus then worked | a ptrace syscall sniffer on `comm_server` and a register and stats reader on stock; the Thingino lens driver |
| 2026-10-26 | Which presets store a position; no flag during a recall | set, pan away, call, on a Thingino unit |
| 2026-10-27 | AF-frame bytes 11 and 13 across a day/night flip on stock | the same sniffer ([JL12D2-IRCUT-MECHANISM-RE.md](JL12D2-IRCUT-MECHANISM-RE.md) section 6) |
| 2026-11-06 | Speed per level, ramps, axis latch, recalls (the earlier timing, the 0.4 deg landing), wide FOV | timed moves, snapshots and a full pan turn on a Thingino unit; a second unit as a check |
| 2026-11-07 | Zoom ticks and speed | timed zooms of 100 ms to 3 s, each read back |
| 2026-11-08 | The command-space sweep and baud sweep | `affeed` (send a frame, dump every received byte with timestamps) on a Thingino unit, with the lens driver stopped |
| 2026-11-08 | Recall timing: start delay, pan and tilt speed, about 8 s for about 180 deg | preset recalls called over ONVIF on a Thingino unit, timed on the video from the call, less about 0.35 s of call and stream |
| 2026-11-08 | Stock AF frames, the ONVIF move suite, HumanTrace forced on | `ttysniff` (a ptrace syscall sniffer) attached to the running `comm_server` on a unit reverted to stock |

- The stock captures need root access on the OEM firmware, which is out of scope here.
- The probe and capture tools (`affeed`, `ttysniff`, the calibration script) and the raw captures are not published.

## Unverified

| ID | Open fact | Why open | How to close | Needs the user's go |
|---|---|---|---|---|
| U-29 | The AF-frame rate on stock firmware: the captures recorded 20 Hz (2026-10-25), 25 Hz (2026-10-27) and about 27 Hz (2026-11-08). All agree it is one frame per sensor frame. | No capture timed the frames against the sensor's own frame rate. `[I]` The 2026-11-08 HumanTrace capture logged 1472 AF frames while a person moved in view for about 60 s, which fits 25 Hz better than 20 if the capture spanned that minute. | Time a stock capture and read the sensor frame rate in the same session. | yes: a capture on a unit running stock firmware |

Not known, and not tracked as open facts: the meaning of AF bytes 12 and 14 (S2, S4); how the board's 1-30 zoom number maps to the stock overlay; whether the head stops short of the lens's wide end.
