# What this forward-port adds to Thingino

This firmware is upstream Thingino plus a SigmaStar Infinity6C layer. It ships as
a patch series — 21 patches onto `themactep/thingino-firmware` master and 8 onto
`gtxaspec/raptor-hal` — that bring up five camera models and carry a set of
general fixes meant to go back upstream.

This page describes **what** the port adds and **where** each change belongs,
at a product level rather than as a commit log. Development notes — process,
methodology, and the change-by-change history — are kept separately and can be
provided on request. For the headline summary and how to apply the patches, see
the [README](../README.md).

- **Part 1:** fixes and features that belong in the packages this port starts
  from, grouped by upstream project.
- **Part 2:** what the build adds on top of Thingino for SigmaStar cameras.
- **Part 3:** what is still open.

Nothing has been submitted upstream yet; this repository is the starting point.
Every item marked *verified* runs on at least one of the five camera models today
(MC-A85, JL12D2, YMF46D, N803, and the reference target).

## At a glance

| Upstream project | What this port carries | Submit as |
|---|---|---|
| OpenWrt [uhttpd](https://git.openwrt.org/project/uhttpd.git) | a conditional-request fix | one patch |
| [gtxaspec/raptor](https://github.com/gtxaspec/raptor) (Thingino's streamer) | day/night for PWM-dimmed IR banks, RTSP/ONVIF delivery, streaming and encoder rate-control, init hooks, a non-Ingenic link fix | small independent PRs |
| [gtxaspec/raptor-hal](https://github.com/gtxaspec/raptor-hal) | the SigmaStar Infinity6C backend (John Chia's) plus a bridge to the current HAL interface and a few ISP features | one series, with John Chia |
| [themactep/thingino-onvif](https://github.com/themactep/thingino-onvif) | a PTZ schema-order fix (Frigate) | one patch |
| [themactep/thingino-firmware](https://github.com/themactep/thingino-firmware) | generic platform-enabling fixes; the SigmaStar platform (John Chia's, re-cut onto current master); two new packages (`thingino-lensd`, `thingino-nettest`); five camera profiles | separate PRs per group |

## 1. Fixes and features for upstream

### 1.1 OpenWrt uhttpd

Conditional requests: `If-None-Match` decides when it is present, and
`If-Modified-Since` is ignored then (RFC 9110 §13.2.2). uhttpd tested the date
first, so a newer date answered 304 even when the ETag did not match — a browser
that last saw another device at the same address kept that device's files.
*Verified (curl matrix, MC-A85).*

### 1.2 Raptor (gtxaspec/raptor)

None of these is SigmaStar-only in effect: each fixes a general bug or adds a
general feature, found on SigmaStar first. They are individual patches in
`package/thingino-raptor/`, ready to split into small PRs.

- **Non-Ingenic link fix** — `LDFLAGS_HAL` stops hard-coding the Ingenic SDK
  libraries, so a non-Ingenic HAL backend links instead of failing on
  `cannot find -limp`. *Verified.*
- **Day/night for PWM-dimmed IR banks (ric)** — an `irled_cmd` hook for IR banks
  that are not on a GPIO, a luma trigger that treats them as IR, an IR level
  ladder that dims to the scene by night gain, and a fixed exposure-poll cadence.
  *Verified (MC-A85, YMF46D).*
- **Init hooks** — `/etc/raptor.d/*` run with `stop` before the daemons go down
  and `start` after, so a process that calls the ISP (a lens daemon) can release
  it first and the vendor MI module does not oops. *Verified (JL12D2).*
- **RTSP delivery in one piece** — TCP_CORK around each reply; the Happytime RTSP
  client in Zosi/Ansjer NVRs stalled on the token-at-a-time writes and showed
  "unconnected". *Verified (Zosi NVR).*
- **DESCRIBE with the parameter sets** — rsd waits for SPS/PPS before answering,
  so go2rtc/Frigate does not build MSE from a placeholder SPS and show 16:9 as
  4:3. *Verified; Frigate fixed.*
- **Preview fallback** — Ch1 previews fall back to the main JPEG channel when the
  sub has no JPEG channel. *Verified.*
- **ONVIF profiles report the real stream sizes.** *Verified.*
- **Streaming and encoder rate-control** — JPEG rings sized to the largest frame,
  explicit VBR caps, and stream frame rates constrained to divide the sensor rate.
  *Verified.*
- **ISP-capability reporting** — rvd reports which image controls the HAL actually
  applies, so the web UI can show only those. *Verified.*
- **raptor-watchdog** — saves fault reports and recovers a wedged stack.
  *Verified.*

### 1.3 raptor-hal (gtxaspec/raptor-hal)

The one carried fork. John Chia's SigmaStar Infinity6C backend and the
reconstructed MI 2.x / 3.0 ABI headers are carried verbatim; this port adds a
bridge to the current upstream HAL interface (his backend predates it), a
FlickerEx anti-flicker lock, a 0..255 image-knob scale map for the i6c ISP,
`ae_luma` reported on the 0..255 scale the ric luma trigger expects, a tunable
SCL→VENC ring depth, and an opt-in AE max-shutter cap. Submit as one series with
John Chia, since most of the code is his; the bridge disappears if his backend
moves to the current interface. Full detail in
[raptor-hal-FORK.md](raptor-hal-FORK.md).

### 1.4 thingino-onvif (themactep/thingino-onvif)

Each zoom default space is emitted in its schema-sequence position. Out of order,
zeep (Frigate's ONVIF parser) dropped the pan/tilt spaces, so Frigate showed the
zoom buttons but no arrows. *Verified (JL12D2 + Frigate).*

### 1.5 Thingino (themactep/thingino-firmware)

#### 1.5.1 Generic fixes

Small and independent; each is useful on Ingenic too.

- Do not default the ISP choice to Ingenic's stack on other vendors (it pulled
  the Ingenic SDK into a SigmaStar config).
- Really disable git submodules when a package turns them off (Buildroot still
  cloned them otherwise).
- Per-vendor `lib-serial-mac` — the global copy reads Ingenic serial registers,
  so elsewhere the hostname suffix came out empty.
- Hide the "Photosensing Config" web link when `thingino-daynightd` is absent
  (under raptor the link 404s).
- A cache policy so a reused camera address never shows the previous device's
  config or footer (with the uhttpd fix in 1.1).

#### 1.5.2 The SigmaStar Infinity6C platform

John Chia wrote SigmaStar support on a branch that fell 762 commits behind
upstream. This port re-cut it onto current master as an additive layer and fixed
what upstream had changed underneath it; it should go upstream as one series with
him, crediting his work. It comprises:

- the vendor packages `sigmastar-sdk`, `sigmastar-lib` and `sigmastar-uboot`
  (the MI stack), including two SDK sensor-load fixes — an `iqfile` alias so AWB
  initialises (otherwise a green picture) and GC8613 4-lane loading;
- Infinity6C board and SoC support, and the kernel seam (`kernels/sigmastar.mk`);
- ARM GCC 16 toolchain producers (glibc and uClibc);
- the config fragments and Config/Makefile wiring (SigmaStar packages sourced,
  U-Boot kept Ingenic-only, the Maruko family mapping, image assembly);
- a SigmaStar CI build job and a target-library check;
- building upstream Raptor on SigmaStar against the raptor-hal fork (1.3);
- a board-less reference target.

#### 1.5.3 New package: thingino-lensd (serial lens/PTZ boards)

For PTZ cameras built around a serial lens/PTZ board — the JL12D2's AF head and
the N803's Pelco-D manual-focus head. It provides:

- stock-equivalent **autofocus**, feeding the board two ISP-derived focus values
  each frame (measured against a stock unit);
- **ONVIF PTZ** — continuous pan/tilt/zoom, presets, home, zoom position — that
  Frigate renders with arrows and zoom;
- a **web UI PTZ plugin**: joystick with speed by reach, zoom/focus buttons,
  presets and home;
- **IR-cut driven over the serial frame** where the filter is on the lens head,
  following ric's day/night decision, not a GPIO;
- a **Pelco-only mode** (`lensd -P`, no AF feed) for manual-focus heads.

The AF feed uses SigmaStar's MI ISP API; the PTZ, ONVIF and web-UI parts are
protocol-level and would serve any Pelco-D board, so upstream may want them split
along that line.

#### 1.5.4 New package: thingino-nettest

A diagnostic tool, generic to any camera: a **Tools → Bandwidth test** web page
and CGI that run `iperf3` and read the PHY link rate, for chasing packet loss
across a switch or NVR path.

#### 1.5.5 Camera profiles

| Camera (owner's units) | Profile |
|---|---|
| reference (John Chia) | `noname_ssc377qe_imx335` |
| UVision MC-A85 / Anpviz IPC-D3B83B-S: SSC378DE + GC8613, fixed 4K | `yma85_ssc378_gc8613` |
| Jennov JL12D2 PTZ / UVision MCL12D2: SSC377D + IMX335, 20x zoom | `mcl12d2_ssc377d_imx335` |
| Anpviz IPC-B8A63WD-S / UVision MC-F46D: SSC377D + GC4653, 2560x1440 bullet | `ymf46d_ssc377d_gc4653` |
| N803 PTZ: SSC378QE + IMX415, 8 MP, 5x zoom, Pelco-D manual-focus head | `n803_ssc378qe_imx415` |

Each profile is one directory under `configs/cameras/<profile>/` (defconfig,
kernel `.config` fragment, overlay) plus a board device-tree patch under
`board/sigmastar/infinity6c/patches/linux/`. The JL12D2 and YMF46D share one
board DTS (same wiring); the MC-A85 and N803 have their own. All are decoded from
the stock device trees.

**Proprietary files:** the profiles reference the OEM sensor tuning files
(`gc8613.bin`, `gc4653.bin`, and the IMX415 tuning for the N803). Those are
vendor files, gitignored, and cannot be submitted.

**All profiles default to the Eastern timezone** (`America/New_York`) — the
owner's locale, a local default rather than an upstream candidate.

### 1.6 Not for upstream

Tooling and notes specific to this port, not candidates:

- **Flashing over the stock U-Boot:** an ANJOY888 image wrapper, web-UI flash,
  SSH flash with rollback, and a stock-backup tool.
- **Build scripts:** a per-camera build wrapper plus a build-all wrapper, with
  in-squashfs checks and a build-ID guard (an image built from uncommitted
  changes is stamped `-dirty`, and each build verifies the image matches the
  current commit).
- **Bring-up records and bench notes.**

## 2. What the build adds on top of Thingino (SigmaStar line)

### 2.1 Cameras supported

| Camera | Streams | Highlights |
|---|---|---|
| MC-A85 (fixed 4K) | 3840x2160 + 1280x720 H.264 | OEM tuning, FlickerEx, luma day/night with IR ladder, IR + white lights |
| JL12D2 (PTZ, 20x) | 2592x1944 + 1280x960 (native 4:3) | autofocus, pan/tilt/zoom/presets over ONVIF and web UI, microSD |
| YMF46D (bullet) | 2560x1440 + 960x540 (sub) | correct orientation, mic, IR + white lights, GPIO IR-cut, microSD automount |
| N803 (PTZ, 5x) | 3840x2160 + sub | Pelco-D pan/tilt/zoom/focus, limited autofocus, serial IR-cut, 256 MB DDR |

All five run upstream Raptor with Thingino's own web UI and its Raptor plugin.
They boot under the **stock OEM U-Boot and flash layout**, so a unit can be
flashed from stock and back without opening it.

### 2.2 Features, by area

- **Streaming:** upstream raptor/ipc/common/compy at Thingino's pins; only the
  HAL is specific to this port (1.3). Eight RTSP clients per profile — enough for
  Frigate plus an NVR plus viewers.
- **Day/night:** ric's luma trigger works with PWM-dimmed IR banks and its IR
  ladder dims to the scene; per-camera IR-cut GPIOs and pulse width; on the
  JL12D2 the IR-cut filter is on the lens head and driven over serial by `lensd`,
  following ric's decision (day colour, night mono + IR); a `light` tool for IR
  and white banks with brightness.
- **PTZ and lens:** stock-equivalent autofocus, zoom position read-back, ONVIF
  PTZ that Frigate shows with arrows and zoom, a web UI joystick with speed by
  reach, and 31 named presets plus home.
- **Encoder and rate control:** JPEG rings sized to the largest frame, the
  SCL→VENC ring depth tuned so the scaler cannot lap the encoder on a cascaded
  sub, explicit VBR caps, and frame rates constrained to divide the sensor rate.
- **Image Quality page honesty:** the web UI shows only the controls the HAL
  actually applies — on these SoCs brightness, contrast, saturation, AE
  compensation, anti-flicker, temporal NR, WDR and defog; the no-op sharpness and
  white-balance controls are gone. Flips save with a "restart stream" prompt,
  since the SoC only applies a flip on restart.
- **Night AE max-shutter cap:** an opt-in, per-profile shutter ceiling (off by
  default) to hold frame rate at night at the cost of gain.
- **Motion gating:** these HALs have no on-camera motion detection (Frigate does
  it), so the web UI hides the Motion control and the camera refuses to enable it.
- **Interop:** Zosi/Ansjer NVRs connect; Frigate/go2rtc always gets the parameter
  sets, so no 4:3 squish; ONVIF reports the real stream sizes.
- **Web UI:** never shows a stale config or footer (cache policy + the uhttpd
  fix); Ch1 previews work with JPEG off the main; no dead day/night link; the PTZ
  plugin; a bandwidth-test diagnostic.
- **Storage:** microSD as modules (SDIO, MMC block, exFAT), with mdev automount
  on the YMF46D and JL12D2.
- **Brick protection:** on the OEM layout the U-Boot env sits on the first block
  of the kernel partition, so `fw_setenv` used to wipe the uImage header; each
  profile keeps the env in a file instead.

## 3. Still open

- **Stream menus for MC-A85 and N803.** Per-profile stream config (geometry,
  rates, VBR caps) so their Streamer web UI reads correctly, as already done for
  the JL12D2 and YMF46D — config, applied when those units are next built.
- **Encoder keyframe-size cap.** Bound the size of individual I-frames.
- **ONVIF RelativeMove (Frigate autotracking, JL12D2).** Needs PTZ calibration at
  the bench; the board sends no motion flag for preset recalls, so MoveStatus must
  come from timing (details in
  [oem-reference/JL12D2-PTZ-PROTOCOL.md](oem-reference/JL12D2-PTZ-PROTOCOL.md)).
- **16:9 on the JL12D2.** The i6c backend scales the whole frame and cannot crop
  yet; this is raptor-hal work.
- **Night-mode settling.** The cameras take about 5 minutes to settle into night
  mode after a nighttime restart — cause not yet found.
- **Speakers (MC-A85, YMF46D).** The speaker-enable GPIO is unmapped.
- **Upstream submissions and CI.** Waiting on the owner's go-ahead — this
  repository is that step.
