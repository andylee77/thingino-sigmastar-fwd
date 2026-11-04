# JL12D2 PTZ + autofocus serial protocol (for the Thingino port)

How the stock JL12D2 / MCL12D2 (SSC377D + IMX335, 20x zoom pan/tilt) drives its
pan/tilt/zoom/focus motor-and-lens controller, so the Thingino port can
reproduce it and expose PTZ over ONVIF for Frigate.

**Source:** static disassembly of the V3.3.2.4 OEM binaries in
`refs/live_rootfs/opt/ch/` (`comm_server`, `media_server`, `web_server`) plus
the device tree in `build/live_flash/kernel.bin`, 2026-10-24. The section
below records what was then **verified on hardware** (2026-10-25); where it
disagrees with the inferred sections further down, it wins.

## Verified on hardware (2026-10-25)

Captured from a running stock unit with a ptrace syscall sniffer on
`comm_server` and a register/stats reader, then reproduced on the Thingino
unit by `lensd` (`tools/jl12d2-lens/`), where autofocus now works.

- **Port:** `/dev/ttyS2` (`fuart@1F220400`), 57600 8N1 raw, VMIN = VTIME = 0
  (read back off the live port). `comm_server`'s `thread_comm` does all the
  writing; `media_server` hands it the AF data over IPC (`AuxMsgAfData*` in
  `libtools.so`).
- **Wiring:** a 4-pin plug with two wires on the 5-pin D7 header, seated
  **from the right**. Seated one pin left, the lens board's TX lands on a SoC
  output: the link is dead both ways and the board keeps resetting (the lens
  "wanders" through calibration sweeps).
- **Lens MCU:** reports `CAM-YS183-AJ3-2.80 Dec  2 2025` to `VER`, but only
  shortly after its own power-up (stock caches it in `/tmp/AF_version.txt`).
- **AF frame,** one per sensor frame (stock: 20 Hz):
  `51 01 04 78 01 0d FVa_H FVa_L FVb_H FVb_L L S1 S2 S3 S4 CK`,
  `CK = sum(bytes 0..14) & 0xff`. `L` follows brightness (08/09 seen),
  `S = 01 00 02 00` throughout, including during and after zooms.
- **FVa / FVb:** `(f0 + f1 + f3 + f4) >> 9` of AF window 0 / window 1, from
  `MI_ISP_CUS3A_GetAFStats` (5 fields x 16 windows of 40-bit counters; the call
  writes 7168 bytes). Fit to the wire over 83 frames with a relative error of
  1e-4. Readable from a process other than the ISP owner.
- **AF configuration:** stock sets window 0 to (19,19)-(1003,1003) and window 1
  to (170,170)-(850,850) on the 0-1023 grid, plus its own AF filter and
  filter-sq; the other nine `MI_ISP_CUS3A_*AF*` structs match the vendor
  defaults. Without stock's windows the focus values are ~100x smaller.
- **The lens board runs the focus search itself.** After a zoom stops it
  refocuses from the FVs alone, in ~1.3-2 s (same on stock and on Thingino).
- **Commands** (stock bytes): zoom in `ff 01 00 20 01 01 23`, zoom out
  `ff 01 00 40 01 01 43` (speed bytes `00 00` are ignored), pan right
  `ff 01 00 02 20 00 23`. The ONVIF and web-UI stop is `ff 01 9a 00 00 00 9b`
  (position query) then `ff 01 00 00 00 00 01` five times, ~50 ms apart;
  `/cgi-bin/ptz_ctrl?stop=1` sends the stop once, with no query.
- **Speed applies to pan/tilt only.** The web UI's Speed (1-10, default 5)
  and the CGI's `speed=` change the pan/tilt data byte (table below); zoom
  sends `01 01` at every speed, through the CGI and ONVIF alike. The lens zooms
  about 6 steps/s on the board's 1-30 scale (wide to tele in ~5 s), measured
  the same on stock and on Thingino.
- **Replies:** `51 01 04 78 <type> <len> <payload> <ck>`, same checksum.
  While zooming: `01 08 0b 1a D1 D2 21 26 26 26` (two digits) or
  `01 07 0b 1a D1 21 26 26 26` (one), the board's own zoom number, up to `3 0`
  at the tele end. The stock overlay shows 1x-30x while zooming, so this is
  likely its source, but the mapping is unverified: the board also sends `1 0`
  at the wide end. It is not optical magnification. `88 02 01 02` moving /
  `88 02 01 00` stopped; `90 06 ...` answers the 9A query.
- **Zoom range: ~13.5x optical, the same on both units.** The board's zoom
  number runs 1 (wide) to 30 (tele), and stock's on-screen zoom shows the same
  1X-30X (an ONVIF zoom-in on stock stops at 30X; its `DzoomConfig
  multiple_max="10.0"` digital zoom did not engage). Wide-to-tele ratio by
  image cross-correlation: 13.3x on Thingino, 13.9x on stock. Absolute check on
  stock with a 2 ft level at ~28 ft: wide HFOV ~44.5 deg (level = 268 of 3072
  px), tele HFOV ~3.5-4 deg (frame just narrower than the level), so ~11.5-13.5x.
  Assuming stock's 3072x2048 stream spans the full sensor width (5.18 mm), that
  is roughly 6.3 mm to 85 mm, short of the advertised 4.7-94 mm "20x" at both
  ends; whether the board stops short of the lens's wide end is not known.
- **Function presets.** The live config (`/mnt/nand/config.xml`, from
  Jennov's `/mnt/nand/cust/config.default.xml`) maps the PTZ functions to
  presets: LeftMargin set 35, RightMargin set 36, AreaScanOn call 38,
  AreaScanOff set 38, CruiseOn call 41, CruiseOff set 255, HumanTraceOn
  call 92, HumanTraceOff call 94, PtzRestore set 107 then call 64. The
  81/82/83 margins and area scan in `/opt/ch/config.default.mcl12d2.xml` are
  the generic Anjvision defaults, which the Jennov file overrides. The wake-up
  borrowed from majestic-af's Pelco-D lens tool (the
  `51 01 04 79 01 0d 0a 2e 02 7e 00 00 00 95` frame, call presets 0x53 = 83
  and 0x52 = 82, then aux night/day) was sent once on Thingino before AF was
  confirmed. On this board 82 and 83 are not function presets, but calling
  them may still move the head to a stored position. **AF does not need the
  wake-up:** from a cold power-on, with `lensd` (which does not send it) and
  none of the GPIO writes copied off stock, the lens refocuses after every
  zoom (2026-10-25).
- **The `VER` query goes unanswered at boot.** The board answers only shortly
  after its own power-up, and `lensd` starts later (after raptor, ~20 s), so
  it logs `lens board version: (no reply)`. Harmless.

## Transport

- **Device:** `/dev/ttyS2` — the **fuart** (`serial2 = fuart@1F220400`, pads
  PAD_FUART_RX/TX). Not UART1. `comm_server` always opens `/dev/ttyS2`; the
  `[Ptz] ComPort` in the config is ignored.
- **Baud: 57600**, 8N1, raw. (The config's `BaudRate="9600"` is only logged;
  the value actually used is 57600, selected because `af.flag` is present.
  `stty -F /dev/ttyS2` on the live unit still needs to confirm this.)
- **termios:** `c_cflag = CREAD | CLOCAL | CS8`, iflag/oflag/lflag = 0,
  VMIN = VTIME = 0, `TCSANOW`.
- **Ownership:** `comm_server` writes commands; `media_server` reads replies and
  streams autofocus statistics. (HARDWARE.md's "mainctrl = PTZ steering" is
  wrong.)

## Pan / tilt / zoom / focus — Pelco-D

Standard Pelco-D, address **01**, checksum = `sum(bytes 1..5) & 0xFF`. Pan
speed goes in data1, tilt speed in data2. Command templates live in
`comm_server` `.data` (0x3f600).

Speed byte for stock's speed level (web UI / `/cgi-bin/ptz_ctrl?speed=`),
measured on the wire:

| Level | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
|---|---|---|---|---|---|---|---|---|---|---|
| Byte | `01` | `04` | `0a` | `12` | `19` | `20` | `27` | `2e` | `35` | `3f` |

ONVIF `ContinuousMove` velocity v sends the byte for level `floor(10v) + 1`,
capped at 10: 0.1 → `04`, 0.25 → `0a`, 0.5 → `20`, 0.75 → `2e`, 1.0 → `3f`.

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

Vendor cmd2 extensions: `A1` light-alarm on/off, `97` PTZ reboot, `A3` guard
preset.

**Absolute move** (`web_server __tptz__AbsoluteMove`, needs the
`absolute_move_onvif` flag, which is set): `FF 01 99 PH PL TH TL SX SY ZH ZL SZ CK`.
Positions are `((v*100+100)/2)*65535/100` → 0..65535; speeds 0..255 (`FF` =
unspecified); `CK = sum(bytes 1..11)`. (`move3DPoint FF 01 93 …` is gated to
other product types and not used here.)

## Position feedback

- **Query:** `FF 01 9A 00 00 00 9B`.
- **Reply framing** (`media_server` parser 0xdd5dc): `51 01 04 RW TYPE LEN <data> CK`,
  `CK = sum(all prior bytes)`.
  - RW `78` / TYPE `90` / LEN `07`: pan16, tilt16, zoom16 (big-endian) + 1 byte.
    ONVIF value = `2*raw/65535 - 1`.
  - RW `90` / TYPE `22`: zoom ratio = `(hi*256+lo)/10`.
  - Other TYPEs: OSD text (`63/64/E1`), manual-focus mode (`CF`), alarm bits
    (`79/91`).
- **Measured on a JL12D2 board (2026-10-25)** — the reply is
  `51 01 04 78 90 06 <pan16> <tilt16> <zoom16> CK` (LEN `06`, not `07`):
  - pan and tilt are always `0000`: the head has no position feedback;
  - zoom16 is the zoom position, `0000` at the wide end and `ffff` at the
    tele end (`92f7` at board zoom step 12, `d747` at 19), readable at any
    time, not only while zooming. ONVIF's zoom space is 0..1, so `raw/65535`.
- **Motion flag:** the board sends `51 01 04 78 88 02 01 02` when it starts
  moving and `... 88 02 01 00` when it stops (seen on Thingino). **Not for preset
  recalls** (2026-10-26): a call `07` moves the head with no flag, so
  "moving" cannot come from the board during a GotoPreset. This matters for
  Frigate's MoveStatus.
- **Presets** are stored by the board (Pelco-D set `03` / call `07` / clear
  `05`); a set position is recalled to within a few pixels. **Only presets
  1-32 store a position:** a set then call of 33 leaves the head where it is
  (bench, 2026-10-26: store, pan away, call -> no movement; same test on 32
  -> back to within noise). `lensctl` therefore keeps user presets to board
  presets 1-31 (slots 0-30) and home to 32. An earlier build put home on 33,
  so its home button did nothing (forward-port 0060). Function presets: 35+,
  see "Function presets" above.

## Autofocus — the firmware must feed the lens board

`AfConfig type="2"` selects `CAfV3`. `CAfV3::Thread_Handle` runs **once per ISP
frame**: it reads CUS3A AF statistics (MI_ISP call id `0x2e0d`) and sends a
16-byte frame to the lens board over ttyS2:

```text
51 01 04 78 01 0D  FVa_H FVa_L  FVb_H FVb_L  L  S1 S2 S3 S4  CK
```

- `FVa`/`FVb` = `(Σ four 40-bit stat values >> 6) >> 3`, from stats offsets
  {0,80,240,320} and {5,85,245,325} — inferred to be AF windows 0 and 1
  (IIR high/low + Sobel).
- `L` = an AE/brightness value; `S1..S4` = ISP state getters (semantics
  unverified).
- `CK = sum(bytes 0..14)`.

**The zoom board runs the focus search itself.** Our firmware does **not** need
its own focus loop — but it **must stream this frame every video frame**, or the
lens will not focus after a zoom. The stats struct layout is inferred; confirm
against the SigmaStar MI headers or a UART capture of the stock firmware.

Startup (`bSendOnStart=1`): AF-stat forwarding simply starts at boot rather than
after the first move. A version handshake runs first — `"END"+D7` ×8 at 60 ms,
then `"VER"+ED` (fallback `"EXVER"+8A`); the reply lands in `/tmp/AF_version.txt`.
No lens-type or zoom-curve command was found. `BootAction=0` → no position reset.

## What the Thingino port needs — reuse vs. bespoke

**Status (2026-10-25): built; this supersedes the plan below.** The
`thingino-lensd` package (forward-port patches 0042 and 0045) follows the OEM
model: `lensd` streams the AF frame and the board runs the focus search.
`lensctl` is the backend of `thingino-onvif`'s ptz section:

- continuous pan/tilt (with diagonals) and zoom, and Stop;
- GetStatus with the zoom position;
- presets the board stores.

`/usr/bin/motors` exists only because the ONVIF server enables PTZ when
`/bin/motors` does. Absolute and relative moves are refused: there is no
pan/tilt position. Two assumptions below proved wrong:

- the AF statistics are readable from a process other than rvd;
- no custom focus-search code was needed.

**Hazard found on the way:** an ISP call from `lensd` that lands while rvd
tears the ISP channel down oopses the vendor MI module
(`MI_ISP_IMPL_GetIQApiData` → data abort) and leaves the MI device's rwsem
held. The next rvd then hangs in `MI_DEVICE_Open`, so a web UI streamer
restart leaves no video until a reboot. Raptor patch 0006 (forward-port 0043)
makes `S31raptor` run `/etc/raptor.d` hooks with `stop` before any daemon
goes down and `start` after, and `lensd`'s hook stops it first. Moving the AF
read into rvd itself (raptor-hal) would remove the hazard at the source.

Most of this assembles from parts we already have; only the AF forwarder is
genuinely new.

**Reusable:**

- **ONVIF PTZ for Frigate:** `thingino-onvif` (onvif_simple_server fork) already
  serves ONVIF PTZ and shells out to configurable move/stop/zoom/preset
  commands. Point those at our Pelco-D sender; Frigate drives it unchanged.
- **AF statistics read:** `raptor-hal` has AF getters (`hal_isp_get_af_metrics`,
  `_af_hist`, `_af_zone`, `_af_weight`) **but only in the Ingenic backend**
  (`src/hal_isp.c`). The **SigmaStar backend has none** — `src/infinity6c/`
  explicitly runs CUS3A as AE+AWB only (`ae_awb[] = {1,1,0}`, no AF), and our
  reconstructed i6c ABI headers declare no `MI_ISP_CUS3A_Get*Af*` symbol. So the
  AF read is **not** reusable code; the Ingenic getters are only a structural
  template. Neither the public SigmaStar SDK docs (the Ikayaki/SSD2xx bundle is
  fixed-focus, no AF) nor OpenIPC/divinus (uses CUS3A only for 3A-enable and
  grayscale) has it.

**Bespoke (small):**

1. A **Pelco-D serial sender**: open `/dev/ttyS2` @ 57600 8N1 raw and write the
   7-byte frames above. Trivial. (`thingino-motors` / `timps` motors are for
   Ingenic VCM/GPIO/I2C lenses, not a serial Pelco-D zoom board, so they do not
   apply.)
2. A reader for the `51 01 04` reply frames, for ONVIF GetStatus / zoom ratio.
3. **The autofocus path.** Two possible architectures:
   - **OEM model (what the stock firmware does):** the SoC reads CUS3A AF stats
     and streams the 16-byte `51 01 04 78 01 0D …` frame to the STM32 every
     frame; the **STM32 runs the focus search**.
   - **OpenIPC model (simpler for us):** the SoC reads the same stats, runs the
     focus search **itself**, and sends plain **Pelco-D focus near/far** to the
     STM32 (which we already map). No vendor AF-frame protocol needed.

   **Use the OpenIPC model, with [`OpenIPC/majestic-af`](https://github.com/OpenIPC/majestic-af)
   (MIT) as the reference.** It is autofocus for this exact hardware class — a
   Pelco-D lens head on an STM32 over `/dev/ttyS2` @ 57600, on SigmaStar
   (the SSC30KQ/i6e board in OpenIPC issue #2512 even uses the same IMX335). Its
   independently reverse-engineered AF-stats layout **matches our disassembly
   byte-for-byte** (CUS3A ctrl `0x2E0D` = 11789, zones at 0x00/0x50/0xE0/0x130,
   fields IIRH/IIRL/SBLV/SBLH/Luma; focus value = high-band IIR blended with
   vertical Sobel), so the layout is high-confidence without a capture.

   Work to do:
   - **Add in-process CUS3A AF-stats reading to raptor-hal's SigmaStar backend**
     (enable the AF bit; call the `0x2E0D` getter). It **must** run in the
     process that owns the ISP (rvd) — a standalone ioctl fails
     (`Not support - Ctrl ID = 11789`).
   - **Port majestic-af's search + actuator** (`af2.c`/`engine.c`/`act_uart.c`,
     Pelco-D over a tty) onto raptor. It is coupled to majestic through one
     plugin ABI header, so this is a port of its engine, not a drop-in.
   This is the gating item for usable zoom; pan/tilt/zoom/presets do not depend
   on it. A UART capture of the stock firmware is still worth taking to validate
   end to end.

Open items, all settled by a short UART capture of the stock firmware **before**
we reflash a unit (worth doing on the bench JL12D2 while it still runs stock):
the live baud (`stty -F /dev/ttyS2`), the exact AF stats→`FVa`/`FVb` mapping, the
meaning of AF bytes `L` and `S1..S4`, and the MCU's `VER` reply format.

## Stock ONVIF verification (2026-10-24)

Exercised the stock ONVIF PTZ over the network before reflashing, to confirm the
head and establish a known-good reference (an ONVIF test script):

- **Zoom: verified** — `ContinuousMove` zoom in/out moved `GetStatus` zoom from
  −0.23 → +0.43 → −0.24; `AbsoluteMove` zoom 0 recentred to ~0. Zoom position
  read-back is accurate.
- **Pan / tilt: commands accepted** (every `ContinuousMove` + `Stop` returned a
  clean response), **but `GetStatus` pan/tilt sits at a constant −1/−1** — this
  head has no pan/tilt position encoder (matches the research: only zoom comes
  back reliably). Physical motion confirmed visually, not by telemetry. **The
  Thingino ONVIF backend should report zoom position and leave pan/tilt
  unknown/moving**, not try to report an absolute PT position.
- **Presets:** `SetPreset` → token 1, `GotoPreset` accepted. **Absolute move:**
  accepted (zoom axis confirmed). `Stop` halts motion.

This is OEM behaviour to reproduce, not something we build on. On stock, ONVIF
rides HTTP :80 with `OnvifAuth=0` (no auth by default).
