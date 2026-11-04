# What this forward-port adds to Thingino

> **Detailed rationale catalog.** This page explains each change and where it
> should go upstream, keyed to the original development commits (the `NNNN`
> numbers below). The repository ships these as a **consolidated 21-patch series**
> in [`patches/`](../patches/), grouped by concern and proven byte-identical to the
> development tree — so the `NNNN` here are for rationale and traceability, not the
> patch filenames. Current to forward-port 0087 — five cameras, including the
> N803. For the headline summary see the [README](../README.md).

This firmware is upstream Thingino plus a SigmaStar layer. The build tree is the
`sigmastar-fwd` branch: upstream `themactep/thingino-firmware` master at
`f083382c1` (2026-10-23), plus the commits mirrored under
[`patches/`](../patches/). This page lists what those commits change and where
each change should go:

- **Part 1:** fixes and features that belong in the packages it starts from,
  grouped by upstream project, ready to submit.
- **Part 2:** what the build adds on top of Thingino for SigmaStar cameras, by
  feature.
- **Part 3:** what is still open.

**Status.** Nothing has been submitted upstream yet; this repository is the
starting point for that discussion. Every item marked *verified* runs on at
least one of the five camera models today (MC-A85, JL12D2, YMF46D, N803, and the
reference target), at forward-port 0087.

**Where the code is.**

- Each tree commit is mirrored as a patch in
  [`patches/thingino-sigmastar/`](../patches/thingino-sigmastar/),
  numbered `NNNN` below.
- Patches carried against other upstreams sit inside those commits, as
  package patch files. They are listed per project in Part 1.
- The one fork, raptor-hal, is described in
  [`raptor-hal-FORK.md`](raptor-hal-FORK.md); its own patches are in
  [`patches/raptor-hal/`](../patches/raptor-hal/).

## At a glance

| Upstream project | What this port carries | Submit as |
|---|---|---|
| OpenWrt [uhttpd](https://git.openwrt.org/project/uhttpd.git) | 1 bug fix (conditional requests) | one patch |
| [gtxaspec/raptor](https://github.com/gtxaspec/raptor) (Thingino's streamer) | 11 patches: build, day/night (ric), init hooks, RTSP (rsd), JPEG rings, ISP-capability reporting | small independent PRs |
| [gtxaspec/raptor-hal](https://github.com/gtxaspec/raptor-hal) | SigmaStar Infinity6C backend (John Chia's) + a bridge to the current HAL interface | one series, with John Chia |
| [themactep/thingino-onvif](https://github.com/themactep/thingino-onvif) | 1 fix (PTZ schema order, Frigate) | one patch |
| [themactep/thingino-firmware](https://github.com/themactep/thingino-firmware) | generic fixes; the SigmaStar platform (John Chia's, re-cut onto current master); two new packages (`thingino-lensd`, `thingino-nettest`); 5 camera profiles | separate PRs per group |

## 1. Fixes and features for upstream

### 1.1 OpenWrt uhttpd

| Patch | Change | Why | State |
|---|---|---|---|
| `thingino-uhttpd/0007-file-if-none-match-overrides-if-modified-since.patch` (in 0053) | `If-None-Match` decides when present; `If-Modified-Since` is ignored then | RFC 9110 13.2.2. uhttpd tested the date first, so a newer date answered 304 even when the ETag did not match: a browser that last saw another device at the same address kept that device's files | verified (curl matrix, MC-A85) |

The Thingino side of the same fix is in 1.5.1 (0053).

### 1.2 Raptor (gtxaspec/raptor)

All eleven live in `package/thingino-raptor/` as `0001`-`0011` and are
written against Thingino's raptor pin `6afaff9`. None is SigmaStar-only in
effect: each fixes a general bug or adds a general feature, and SigmaStar
cameras are where it surfaced.

| Patch | Change | Why | Added in | State |
|---|---|---|---|---|
| 0001 `Makefile: link libimp and libalog for Ingenic platforms only` | `LDFLAGS_HAL` stops hard-coding the Ingenic SDK libraries | any non-Ingenic HAL backend failed to link (`cannot find -limp`) | 0016 | verified (all builds) |
| 0002 `ric: irled_cmd hook for an 850 nm bank that is not on a GPIO` | `[ircut] irled_cmd`: ric runs `<cmd> on\|off` when there is no `gpio_irled` | PWM-dimmed IR banks (MC-A85, YMF46D) never lit at night | 0019 | verified |
| 0003 `ric: luma trigger for irled_cmd banks, and days that stick` | the luma trigger treats an irled_cmd bank as IR, plus two stability fixes | the day test ran on IR-inflated luma; flapping | 0029 | verified (MC-A85, YMF46D) |
| 0004 `ric: IR level ladder for irled_cmd banks` | dimmable IR stepped by night gain (`ir_levels`, `ir_step_gain`) | one fixed level floods near walls or under-lights far fields; night gain went 29460 at 5% to 3003 at 100% | 0029 | verified |
| 0005 `ric: poll exposure on a fixed cadence` | exposure polled on a timer, not once per wake | every control request (the web UI's gain readout) woke the loop early, so debounce shrank from 4.9 s to 0.3 s | 0032 | verified (measured) |
| 0006 `S31raptor: run hooks around the stack` | `/etc/raptor.d/*` run with `stop` before the daemons go down and `start` after | a process outside the stack that calls the ISP (a lens daemon) must stop first, or the vendor MI module oopses and the next rvd hangs | 0043 | verified (JL12D2) |
| 0007 `rsd: send each RTSP reply in one piece` | TCP_CORK around each request's dispatch | compy wrote replies a token at a time on a TCP_NODELAY socket (~20 segments); the Happytime RTSP client in Zosi/Ansjer NVRs stalled and showed "unconnected" | 0051 | verified (Zosi NVR) |
| 0008 `rsd: answer DESCRIBE with the parameter sets, not before them` | DESCRIBE asks for an IDR and waits up to 2 s for SPS/PPS | after a restart, rsd answered without `sprop-parameter-sets`. go2rtc (Frigate) keeps that SDP and builds MSE from a 128x96 placeholder SPS, so 16:9 streams showed at 4:3 | 0059 | verified: 2 of 3 restarts failed before, none after; Frigate fixed |
| 0009 `rvd: size JPEG rings for the largest JPEG, not the average` | JPEG ring buffers sized to the worst-case frame | undersized rings dropped or overran JPEGs on busy high-res scenes | 0067 | verified (YMF46D) |
| 0010 `S31raptor: export /etc/default/raptor to the daemons` | the init script exports the per-profile defaults into the daemons' environment | per-profile knobs (such as the night AE cap) could not otherwise reach the daemons | 0084 | verified |
| 0011 `rvd: get-isp-caps reports which ISP controls the HAL applies` | a new command returns the image controls the HAL actually implements | the web UI offered controls that silently did nothing (sharpness, white balance); the page now shows only what applies | 0085 | verified |

### 1.3 raptor-hal (gtxaspec/raptor-hal)

**What this fork carries:** fork branch `sigmastar` (`d9cd147`) on upstream
`8897102`. Thingino builds SigmaStar against it (0016); every other vendor
keeps upstream raptor-hal.

| Part | Origin | Notes |
|---|---|---|
| `sigmastar-headers/` (MI 2.x / 3.0 ABI headers) | John Chia, verbatim | reconstructed from the vendor ABI (see `VENDORED.md`) |
| `src/infinity6c/` backend + SigmaStar glue | John Chia, verbatim | |
| build hooks (`Makefile`, `hal_caps.c`, `hal_internal.h`) | John Chia's hook diff | |
| bridge to the upstream HAL interface (`i6c_upstream_compat.{h,c}`) | this port | his backend predates the current interface |
| FlickerEx anti-flicker lock | this port | `MI_ISP_AE_SetFlickerEx` manual lock (MC-A85) |
| knob scale map + host test | this port | upstream raptor sends 0..255 to every image knob; the i6c ISP wants native units |
| `ae_luma` reported 0..255 | this port | the ric luma trigger compares 8-bit luma |
| SCL→VENC ring depth (`RSS_SCL_RING_DIV`) | this port | a quarter-frame ring let the scaler lap the encoder on a cascaded sub (YMF46D); a half or whole frame fixed it (patch 0007) |
| opt-in AE max-shutter cap (`RSS_AE_MAX_SHUTTER_US`) | this port | a per-profile night shutter ceiling, off by default; capping at 1/30 s held 25 fps on a YMF46D at more gain (patch 0008) |

**How to submit:** as one series together with John Chia, since most of the
code is his. The bridge would go away if his backend moved to the current
interface.

### 1.4 thingino-onvif (themactep/thingino-onvif)

| Patch | Change | Why | State |
|---|---|---|---|
| `thingino-onvif/0001-ptz-emit-each-zoom-default-space-in-schema-order.patch` (in 0046) | each zoom default space emitted in its `xs:sequence` position | with zoom on, the zoom spaces came before the pan/tilt ones. zeep, Frigate's ONVIF parser, then dropped the pan/tilt spaces, so Frigate showed zoom buttons but no arrows | verified (JL12D2 + Frigate) |

### 1.5 Thingino (themactep/thingino-firmware)

#### 1.5.1 Generic fixes (not SigmaStar-specific)

Small, independent PRs; each is useful on Ingenic too.

| # | Change | Why |
|---|---|---|
| 0011 | thingino-isp: no Ingenic ISP stack on other vendors | the ISP choice defaulted to Ingenic's stack and pulled ingenic-sdk/-lib/libimp into a SigmaStar `.config` |
| 0024 | thingino-raptor-hal: submodules really off for SigmaStar | Buildroot enables git submodules for any non-empty `<PKG>_GIT_SUBMODULES`, so `= NO` still cloned `ingenic-headers` |
| 0027 | thingino-system: per-vendor `lib-serial-mac` | the global copy reads Ingenic serial registers; elsewhere the hostname suffix came out empty |
| 0030 | thingino-raptor: Ch1 previews fall back to JPEG channel 0 | with `[stream0] jpeg = false` there is no JPEG channel 1, so the web UI's Ch1 snapshot and MJPEG returned 503 |
| 0031 | webui: "Photosensing Config" only with thingino-daynightd | under raptor the link 404s |
| 0043 | thingino-raptor: `/etc/raptor.d` hooks (with raptor 0006) | see 1.2 |
| 0044 | thingino-raptor: ONVIF profiles carry the streams' real sizes | S96onvif_discovery left onvif.json's 1920x1080 / 640x360 defaults |
| 0053 | thingino-uhttpd: cache policy | `uhttpd -H /etc/uhttpd-cache.json`: runtime-config.js always sent fresh with no-store, `/x/` CGI no-store, the rest revalidated; with the uhttpd fix (1.1). A reused camera address showed the previous camera's footer and config |
| 0019 | thingino-raptor: `BR2_..._IRCUT_IRLED_CMD` knob | the Kconfig side of raptor 0002 |

#### 1.5.2 The SigmaStar Infinity6C platform

John Chia wrote the SigmaStar support on `johnchia/thingino-firmware`
`sigmastar-6b0-platform` (`36e2df606`). That branch is 762 commits behind
upstream. This port re-cut it onto current master and fixed what upstream had
changed underneath it. It should go upstream as one series with him, crediting
his work.

| # | Change |
|---|---|
| 0001 | vendor packages `sigmastar-sdk`, `sigmastar-lib`, `sigmastar-uboot` (MI stack, drop-indexed) |
| 0002 | Infinity6C board + SoC support (`board/sigmastar`, `soc/sigmastar/infinity6c.mk`) |
| 0003 | `soc-` and `core-sigmastar.fragment` |
| 0004 | ARM GCC 16 toolchain producers (glibc + uClibc) |
| 0005 | reference target `noname_ssc377qe_imx335` |
| 0006 | CI: SigmaStar build workflow + target library check |
| 0007 | `kernels/sigmastar.mk`, the kernel seam: upstream moved kernel selection (#1442) and requires `KERNEL_BRANCH` |
| 0008 | thingino-system SigmaStar utilities, re-laid out as `files/sigmastar/` for upstream's vendor split (#1428) |
| 0009 | `Config.in`: source the SigmaStar packages; `BR2_TARGET_UBOOT` Ingenic-only |
| 0010 | `Config.soc.in`: map all six Maruko parts to `BR2_SOC_FAMILY` (upstream gates options on it) |
| 0012 | re-sync `core-sigmastar.fragment` with `core.fragment` |
| 0013 | drop the removed `ssl-mbedtls` fragment (upstream's SSL virtual package) |
| 0014 | SigmaStar image assembly in upstream's split Makefiles |
| 0015 | export the vendor-drop variables (`SIGMASTAR_DROP/_LIBC/_GCC/_KREL/_SENSOR`) |
| 0016 | build upstream Raptor on SigmaStar against the raptor-hal fork (1.3) |
| 0017 | sigmastar-sdk: alias `iqfile1.bin` to `iqfile0.bin`. libcus3a picks the file by channel *mask*, so without the alias AWB never initialised (green picture) |
| 0018 | sigmastar-sdk: GC8613 4-lane loading (`chmap=1 lane_num=4`) |

#### 1.5.3 New package: thingino-lensd (serial lens/PTZ boards)

PTZ cameras built around a serial lens/PTZ board, like the JL12D2's CAM-YS183
AF head and the N803's Pelco-D manual-focus head.

| # | Adds |
|---|---|
| 0042 | `lensd`: the board's autofocus works only if the SoC streams it two focus values every frame, computed from the ISP's AF statistics with the vendor's AF window and filter. lensd does what stock does, measured on a stock unit. It also takes zoom/focus/PTZ commands from `/run/lensd.cmd`, and drives the head's **IR-cut filter over the same serial frame** (byte 11 = day `0x00` / night `0x01`, following the day/night state ric signals on gpio 80/11) — the physical filter is on the lens head, not a GPIO. Without it the lens never refocuses after a zoom, and daytime is stuck pink |
| 0045 | ONVIF PTZ through `lensctl` (continuous pan/tilt/zoom, presets, home, zoom position) |
| 0054 | web UI PTZ plugin in thingino-motors' layout: joystick overlay, PTZ Settings modal, zoom/focus buttons, presets and home. Backend `/x/json-lensd.cgi` |
| 0056 | a clear "home not set" answer instead of a silent no-op |
| 0058 | speed: the joystick's distance from centre sets the pan/tilt speed; ONVIF velocity maps to stock's speed levels (`floor(10\|v\|)+1`) |
| 0060 | home on board preset 32: the board stores positions in presets 1-32 only and ignores 33 |
| 0074 | `lensd -P` (Pelco-only, no AF feed) for manual-focus heads, plus IR-cut driven over the serial frame — brings up the N803 head |

**How to submit:** the AF feed (0042) uses SigmaStar's MI ISP API. The PTZ,
ONVIF and web UI parts (0045 onward) are protocol-level and would serve any
Pelco-D board. Upstream may want them split along that line.

#### 1.5.4 New package: thingino-nettest (link bandwidth test)

A diagnostic tool, generic to any camera: a **Tools → Bandwidth test** web page
and CGI that run `iperf3` and read the PHY link rate (`miiread`), for chasing
packet loss across a switch or NVR path. Added in 0072.

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
board DTS (same wiring); the MC-A85 and N803 have their own. All are decoded
from the stock device trees.

**Proprietary files:** the profiles reference the OEM sensor tuning files
(`gc8613.bin`, `gc4653.bin`, and the IMX415 tuning for the N803). Those are
vendor files, gitignored, and cannot be submitted.

**All profiles default to the Eastern timezone** (`America/New_York`, 0065) —
the owner's locale, a local default rather than an upstream candidate.

### 1.6 Not for upstream

These are tooling and notes specific to this port, not candidates:

- **Flashing over the stock U-Boot:** the ANJOY888 wrapper
  (`scripts/30_wrap_anjoy888.py`), web-UI flash (`anjoy-flash-thingino.py`), SSH
  flash with rollback (`anjoy-reflash-thingino.py`), and the stock backup tool
  (`anjoy-backup.py`).
- **Build scripts:** `build-{mca85,jl12d2,ymf46d,n803}-fwd.sh` and
  `build-all-fwd.sh`, with in-squashfs checks and a build-ID guard (an image
  built from uncommitted changes is stamped `-dirty`, and each script verifies
  the image's build ID matches the current commit).
- **Bring-up records and bench notes** in this folder.

## 2. What the build adds on top of Thingino (SigmaStar line)

### 2.1 Cameras supported

| Camera | Streams | Highlights |
|---|---|---|
| MC-A85 (fixed 4K) | 3840x2160 + 1280x720 H.264 | OEM tuning, FlickerEx, luma day/night with IR ladder, IR + white lights |
| JL12D2 (PTZ, 20x) | 2592x1944 + 1280x960 (native 4:3) | autofocus, pan/tilt/zoom/presets over ONVIF and web UI, microSD |
| YMF46D (bullet) | 2560x1440 + 960x540 (sub) | correct orientation, mic, IR + white lights, GPIO IR-cut, microSD automount |
| N803 (PTZ, 5x) | 3840x2160 + sub | Pelco-D pan/tilt/zoom/focus, limited autofocus, serial IR-cut, 256 MB DDR |

All five run upstream Raptor with Thingino's own web UI and its Raptor
plugin. They boot under the **stock OEM U-Boot and flash layout**, so a unit
can be flashed from stock and back without opening it.

### 2.2 Features, by area

- **Streaming (Raptor on SigmaStar):** upstream raptor/ipc/common/compy at
  Thingino's pins; only the HAL is specific to this port (1.3). Eight RTSP clients on all
  three profiles, enough for Frigate plus an NVR plus viewers.
- **Day/night:**
  - ric's luma trigger works with PWM-dimmed IR banks, and its IR level
    ladder dims to the scene (raptor 0002-0005).
  - Per-camera IR-cut GPIOs and pulse width.
  - **JL12D2 PTZ:** the IR-cut filter is on the integrated lens head and is
    driven over serial by `lensd` (byte 11 of the AF frame), not a GPIO; it
    follows ric's day/night decision — day colour, night mono + IR (profile
    side in 0063). The GPIO pulse is vestigial on this board.
  - A `light` tool for IR and white banks with brightness.
- **PTZ and lens (thingino-lensd):**
  - Stock-equivalent autofocus.
  - Zoom position read back.
  - ONVIF PTZ that Frigate shows with arrows and zoom.
  - A web UI joystick with speed by distance from the centre.
  - 31 named presets plus home.
- **Interop:**
  - Zosi/Ansjer NVR (Happytime RTSP client) connects (raptor 0007).
  - Frigate/go2rtc always gets the parameter sets, so no 4:3 squish
    (raptor 0008).
  - ONVIF profiles report the real stream sizes (0044).
- **Web UI:**
  - Never shows a stale config or footer: the cache policy plus the uhttpd
    fix (0053).
  - Ch1 previews work with JPEG off the main (0030).
  - No dead day/night link (0031).
  - The PTZ plugin (0054).
- **Encoder and rate control:** JPEG rings sized to the largest frame, the
  SCL→VENC ring depth tuned so the scaler cannot lap the encoder on a cascaded
  sub, explicit VBR caps, and stream frame rates constrained to divide the sensor
  rate.
- **Image Quality page honesty:** the web UI shows only the controls the HAL
  actually applies (rvd's new get-isp-caps) — on these SoCs brightness, contrast,
  saturation, AE compensation, anti-flicker, temporal NR, WDR and defog; the
  no-op sharpness and white-balance controls are gone. Flips save with a
  "restart stream" prompt, since the SoC only applies a flip on restart.
- **Night AE max-shutter cap:** an opt-in, per-profile shutter ceiling (off by
  default) to hold frame rate at night at the cost of gain (raptor-hal 0008).
- **Motion gating:** these HALs have no on-camera motion detection (Frigate does
  it), so the web UI hides the Motion control and the camera refuses to enable it;
  the background motion watcher exits instead of running for nothing.
- **Reliability and diagnostics:** a raptor-watchdog saves fault reports and
  recovers a wedged stack; a **Tools → Bandwidth test** page (thingino-nettest)
  for chasing network loss.
- **Storage:** microSD as modules (SDIO driver, MMC block, exFAT), with
  automount via mdev on the YMF46D and JL12D2.
- **Brick protection:** on the OEM layout the U-Boot env sits on the first
  block of the kernel partition, so `fw_setenv` (S97sysupgrade) used to wipe
  the uImage header. Each profile keeps the env in a file: 0020 (MC-A85),
  0037 (JL12D2), 0047 (YMF46D).

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
- **One shared check library** for the build scripts (each carries its own copy
  of the verify pass today).
- **Upstream submissions (Part 1) and CI.** The "Phase 5" of the forward-port
  plan summarized in the [README](../README.md) — this repository is that step.
