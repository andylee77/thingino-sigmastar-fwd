# N803 lens/PTZ serial protocol — SOLVED: it's Pelco-D

The N803-HS5X zoom/focus/PTZ head is driven over **ttyS2 (FUART) @ 57600 8N1**
(`uart.conf devname=/dev/ttyS2 buadrate=57600 useptz=1`, `ptz.conf protocol=0` =
Pelco-D). The MCU is an **STM32** on the `HSPTZ_POE+Audio_V1.0` base board with a
**ULN2803A** stepper driver; AT24C08 (U3) holds calibration. **Captured live off
the OEM (`nsd`) on 2026-10-29** — not inferred.

The link is **asymmetric**:

## SoC → STM32 : commands = standard Pelco-D

`FF  01(addr)  cmd1  cmd2  panspeed  tiltspeed  checksum`
checksum = `(addr + cmd1 + cmd2 + panspeed + tiltspeed) & 0xff`.
Sent repeatedly while a button is held, then a **Stop**. Every frame below was
seen on the wire and its checksum validated:

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

(panspeed/tiltspeed ~0x1A–0x24; ignored for zoom/focus. This is exactly what
`lensd`'s `pelco()` + verb table already build — see below.)

## STM32 → SoC : status telemetry (NOT commands)

The STM32 **continuously** streams, ~tens of Hz:

`51 01 04 78  01 0D  <posA_hi posA_lo>  <posB_hi posB_lo>  01 00 00  SUM`
SUM = `sum(bytes 0..n-2) & 0xff`.

`posA` = zoom encoder position, `posB` = focus encoder position — both live. At
idle they sit ~`0x0150`/`0x00F3` and jitter ±4; driving zoom/focus ramps them
(seen going to `0x0425`/`0x0238`). The boot burst (`51 01 04 78 02 01 00` ready,
`01 07 …`) is the same direction.

> **The trap that cost this whole session:** `nsd` *builds* `51 01 04 78 …`
> frames too (Ghidra), so I assumed that family was the command set and hand-sent
> `0x52`/`0x89`/`01 0d` from Thingino over ttyS2 — nothing moved, because those
> are the board's **own status telemetry replayed back at it**. The real command
> language is Pelco-D, which Thingino never sent. Lesson: **sniff the OEM before
> porting a serial lens** (this is literally the documented Phase-2 plan).

## Port to Thingino — reuse `lensd`, add a "Pelco-only" mode

`lensd` (`tools/jl12d2-lens/lensd.c`, patches 0042/0045/0054/0056/0058/0060;
already in the build) **already speaks this exact Pelco-D**: `pelco()` emits
`FF 01 c1 c2 d1 d2 ck`, and the verb table maps `zoom_in`=`00 20`,
`zoom_out`=`00 40`, `focus_far`=`00 80`, `focus_near`=`01 00`, pan/tilt, presets —
byte-identical to the capture. ONVIF PTZ (0045) and the web-UI PTZ plugin (0054)
drive it through the `/run/lensd.cmd` FIFO.

The **only** JL12D2-specific parts are the autofocus machinery the N803 does not
have (it's manual focus): the ISP AF-stats load (`isp_load`/`af_values`/
`af_apply`), the `END`/`VER` handshake, and the continuous `51 01 04 78 01 0d
FVa FVb …` **feed** frame in the main loop. For the N803:

1. Add a flag (e.g. `-P` / `pelco_only`) that **skips `isp_load`, `af_apply`, the
   handshake, and the feed frame** — the daemon then just runs the FIFO→Pelco-D
   command loop (and optionally parses the N803 status for a zoom/focus readout).
2. Wire lensd into the `n803_ssc378qe_imx415` profile (init + raptor/ONVIF PTZ
   config) so it runs on boot — the MC-A85-cloned profile has no PTZ today, which
   is why nothing drove ttyS2.
3. N803 status parse differs from the JL12D2's (`01 0d` position pair vs the
   JL12D2 zoom-digit `01 07/08`, `88` moving, `90` query) — minor, informational.

Manual focus never reaching full sharpness is a focus-range/back-focus or
calibration matter; once Pelco-D focus near/far works from Thingino, a software
**AF sweep** (ramp focus across range via Pelco-D, score sharpness from the ISP,
settle on the peak) can add true autofocus on top — Phase 2+.

## Capture method (for next time)

Reader RX tapped on the board serial line (both directions were visible at the
tap), 57600 8N1, logging frames split on the `51 01 04 78` sync with the
jittering status bytes deduped so operator button-presses stand out. Pelco-D
`FF 01 …` frames appear interleaved between the status frames. The Pelco-D
commands were driven from the OEM web UI (default admin login) while the tap
logged both directions.
