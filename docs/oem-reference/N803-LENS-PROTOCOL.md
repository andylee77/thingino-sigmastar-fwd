# N803 head protocol

The N803-HS5X head (pan, tilt, 5x zoom and focus) is run by an **STM32** on the
`HSPTZ_POE+Audio_V1.0` PTZ base board with a **ULN2803A** stepper driver;
an AT24C08 (U3) holds calibration. The SoC talks to it over **ttyS2 (FUART) at
57600 8N1** (OEM `uart.conf devname=/dev/ttyS2 buadrate=57600 useptz=1`,
`ptz.conf protocol=0` = Pelco-D). **Captured live off the OEM (`nsd`) on
2026-10-29**, not inferred. Thingino drives the same head with `lensd` in its
Pelco mode (see [Thingino: lensd in Pelco mode](#thingino-lensd-in-pelco-mode)).

The link is **asymmetric**: Pelco-D commands go from the SoC to the STM32, and
the STM32 streams status back. The board side (connectors, the motors, why the
SoC drives no motor pin) is in the sibling doc `N803-PAD-MAP.md`; the JL12D2's
head, which shares the `51 01 04 78` frame family, is in `JL12D2-PTZ-PROTOCOL.md`.

## SoC → STM32: commands (standard Pelco-D)

`FF  01(addr)  cmd1  cmd2  panspeed  tiltspeed  checksum`
checksum = `(addr + cmd1 + cmd2 + panspeed + tiltspeed) & 0xff`.
The OEM sends the frame repeatedly while a button is held, then a **Stop**.
Every frame below was seen on the wire and its checksum validated:

| Action | Pelco-D frame | bit |
|---|---|---|
| Focus **Near** | `FF 01 01 00 24 24 4A` | cmd1 b0 |
| Focus **Far** | `FF 01 00 80 24 24 C9` | cmd2 b7 |
| Zoom **In** (tele) | `FF 01 00 20 24 24 69` | cmd2 b5 |
| Zoom **Out** (wide) | `FF 01 00 40 24 24 89` | cmd2 b6 |
| Tilt Up / Down | `FF 01 00 10 00 24 35` / `FF 01 00 08 00 1A 23` | cmd2 b4 / b3 |
| Pan Right / Left | `FF 01 00 04 1A 00 1F` / `FF 01 00 02 1A 00 1D` | cmd2 b2 / b1 |
| Iris Open / Close | `FF 01 02 00 24 24 4B` / `FF 01 04 00 24 24 4D` | cmd1 b1 / b2 |
| **Stop** | `FF 01 00 00 00 00 01` | — |

panspeed/tiltspeed ran ~0x1A–0x24; the head ignores them for zoom and focus.

**Direction bits.** The pan and tilt rows are named for the OEM web UI button
that sent them. On each axis the N803's OEM sends the opposite bit to the
JL12D2's stock firmware: the JL12D2 sends Up `00 08`, Down `00 10`,
Left `00 04` and Right `00 02` (`JL12D2-PTZ-PROTOCOL.md`), and `lensd`'s verb
table follows the JL12D2. Which way the N803 head turns for each bit under
Thingino is not recorded here.

## STM32 → SoC: status telemetry (not commands)

The STM32 **continuously** streams, ~tens of Hz:

`51 01 04 78  01 0D  <posA_hi posA_lo>  <posB_hi posB_lo>  01 00 00  SUM`
SUM = `sum(bytes 0..n-2) & 0xff`.

`posA` = zoom encoder position, `posB` = focus encoder position, both live. At
idle they sit ~`0x0150`/`0x00F3` and jitter ±4; driving zoom/focus ramps them
(seen going to `0x0425`/`0x0238`). The boot burst (`51 01 04 78 02 01 00` ready,
`01 07 …`) is the same direction. The stream carries no pan or tilt position.

> **The trap:** `nsd` also *builds* `51 01 04 78 …` frames (seen in Ghidra), so
> that family was first taken for the command set, and `0x52`/`0x89`/`01 0d`
> frames were hand-sent from Thingino over ttyS2. Nothing moved, because those
> are the board's **own status telemetry replayed back at it**. The command
> language is Pelco-D, which Thingino had not sent. Lesson: **sniff the OEM
> before porting a serial lens.**

## Thingino: lensd in Pelco mode

The port this doc planned on 2026-10-29 has landed. The N803 profile
`n803_ssc378qe_imx415` sets `BR2_PACKAGE_THINGINO_LENSD_MODE_PELCO=y` and the
head `hs5x` (`BR2_PACKAGE_THINGINO_LENSD_HEAD="hs5x"`), and `S33lensd` starts
`lensd -P`. The source is `package/thingino-lensd/files/lensd.c` in the Thingino
tree.

- **What `-P` skips.** The JL12D2's head needs an autofocus feed from the SoC;
  this one gets none. `-P` skips the ISP AF-stats load
  (`isp_load`/`af_values`/`af_apply`), the `END`/`VER` handshake and the
  per-frame `51 01 04 78 01 0d FVa FVb …` feed. The daemon then runs the
  FIFO → Pelco-D command path only.
- **The frames it sends.** `pelco()` emits `FF 01 c1 c2 d1 d2 ck`. The verbs
  `zoom_in` `00 20`, `zoom_out` `00 40`, `focus_far` `00 80` and `focus_near`
  `01 00` carry the captured cmd1/cmd2; the speed bytes differ (`01 01` for
  zoom, `00 00` for focus, where the OEM sent `24 24`), which the head ignores.
  Pan and tilt follow the JL12D2's bits (see [Direction bits](#soc--stm32-commands-standard-pelco-d));
  presets are the Pelco-D set, call and clear (cmd2 `03`, `07`, `05`).
- **Move and stop.** lensd sends a move frame once and holds it until the stop,
  where the OEM repeats the frame while a button is held. Its stop is the
  JL12D2 stock sequence: the position query `FF 01 9A 00 00 00 9B`, then the
  captured Stop five times, ~50 ms apart. lensd also sends that query once at
  start, in every mode; no N803 answer to it is recorded.
- **Status.** lensd does not decode this head's status stream: its parser reads
  the JL12D2's replies only (the `01 07`/`01 08` zoom digits, the `88` motion
  flag, the `90` position answer). `/run/lensd.status` reports `moving` and
  `motion` from the commands it sends.
- **Who drives it.** ONVIF PTZ (`lensctl`) and the web UI PTZ plugin write
  commands to the `/run/lensd.cmd` FIFO.
- **Head file.** `heads/hs5x.conf` has no measurements yet (FOV and speeds are
  blank), so ONVIF RelativeMove stays off on this head. With no pan or tilt
  position in the status stream, a RelativeMove here would be timed, as on the
  JL12D2.

Verified on a bench unit on 2026-10-31: `lensd -P` ran and drove the head over
Pelco-D; `/run/lensd.status` flipped to `moving=1 motion=<verb>` on each command
and the lens moved.

Focus Near/Far alone did not bring that unit fully sharp. The 2026-10-29
analysis put it down to focus range, back-focus or calibration, not the
protocol. A software focus sweep on top of the Pelco-D focus commands (step
focus across its range, score sharpness from the ISP's AF statistics, settle on
the peak) could add one-shot autofocus; it is not written.

## Capture method (for next time)

The reader's RX was tapped onto the board serial line (both directions were
visible at the tap), 57600 8N1, logging frames split on the `51 01 04 78` sync
with the jittering status bytes deduped so operator button-presses stand out.
Pelco-D `FF 01 …` frames appear interleaved between the status frames. The
Pelco-D commands were driven from the OEM web UI while the tap logged both
directions. The capture script was not kept.

## Unverified

None. The frames, checksums and positions above were seen on the wire in the
2026-10-29 capture, the board parts were read off the boards, and the Thingino
side was read from its source.
