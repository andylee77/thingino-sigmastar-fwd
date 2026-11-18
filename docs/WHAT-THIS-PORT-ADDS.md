# What this forward-port adds to Thingino

This firmware is upstream Thingino plus a SigmaStar Infinity6C layer. It ships
as three patch series: 22 patches onto `themactep/thingino-firmware` master
(`b8bcd6740`, 2026-11-17) and 13 onto `gtxaspec/raptor-hal` main (`9f09664`,
2026-10-31), and 2 generic patches on top of the first series (part 4).
Together they bring up four camera models and a board-less
reference target, add three feature packages (`thingino-lensd`,
`thingino-nettest`, `thingino-ipud`), and carry a set of general fixes meant to
go back upstream.

This page describes **what** the port adds and **where** each change belongs,
at a product level rather than as a commit log. Each item is tagged with its
patch: `[0010]` is patch 0010 of
[`patches/thingino-sigmastar/`](../patches/thingino-sigmastar/), and
`[raptor-hal 0008]` is patch 0008 of [`patches/raptor-hal/`](../patches/raptor-hal/).
The raptor patch numbers 0101 to 0113 name the files that patches 0010 to 0012
add to `package/thingino-raptor/`. The **Patch map** below is the index. The
overview, the apply steps and the questions for the maintainers are in the
[README](../README.md); the bases and the known limits of the two series are in
[patches/README.md](../patches/README.md); licenses and credits are in
[NOTICE.md](../NOTICE.md).

- **Part 1:** fixes and features for the projects this port builds on, grouped
  by upstream project.
- **Part 2:** what the build adds on top of Thingino for SigmaStar cameras.
- **Part 3:** what is still open.
- **Part 4:** the generic series: work that does not depend on SigmaStar and
  is not upstream yet.

The platform has started going upstream as small pull requests. Upstream merged
three of this port's vendor guards
([#2063](https://github.com/themactep/thingino-firmware/pull/2063),
[#2069](https://github.com/themactep/thingino-firmware/pull/2069),
[#2070](https://github.com/themactep/thingino-firmware/pull/2070)) and replaced
the vendor choice by symbols derived from the SoC model
([#2068](https://github.com/themactep/thingino-firmware/pull/2068)), and
merged the first piece of the platform itself, the Infinity6C family file
([#2083](https://github.com/themactep/thingino-firmware/pull/2083)). The
series is cut on a master that has all of these, so it carries none of them:
the profiles name upstream's `soc-infinity6c` fragment, and patch 0002 adds to
upstream's family file only what it does not hold yet.
[UPSTREAM-PLAN.md](UPSTREAM-PLAN.md) has the planned series and where each piece
stands. Generic fixes found along the way go upstream separately, as the pull
requests the [README](../README.md) lists. A *Verified* note names the camera
model a change was checked on.

**Since the cut of 2026-11-11** (on `b9b040f33`): the three merged guards left
patches 0005 and 0009, and the merged family file left 0002 and 0003; patch 0007 gained the page stamp, the CGI cap for small
boards and a single `Cache-Control` header beside upstream's new cache
switches; patch 0012 gained raptor patches 0112 and 0113; patch 0013 gained the
watchdog's restart of a vanished `rvd`, a cheaper poll and the agent listener's
request cap; and `thingino-ipud` runs without an IPU firmware file. Both series
keep their counts.

## At a glance

| Upstream project | What this port carries | Submit as |
|---|---|---|
| OpenWrt [uhttpd](https://git.openwrt.org/project/uhttpd.git) | a conditional-request fix | one patch |
| [gtxaspec/raptor](https://github.com/gtxaspec/raptor) (Thingino's streamer) | 13 package patches: a non-Ingenic link fix, day/night for PWM-dimmed IR banks, hooks around the stack, RTSP delivery, JPEG ring sizing, an environment file for the daemons, ISP capability reporting, two OSD fixes for the detection overlay | small independent PRs |
| [gtxaspec/raptor-hal](https://github.com/gtxaspec/raptor-hal) | the one fork: John Chia's Infinity6C backend and MI headers, a bridge to the current HAL interface, ISP and encoder features (13 patches) | one series, with John Chia's work credited to him |
| [themactep/thingino-onvif](https://github.com/themactep/thingino-onvif) | a PTZ schema-order fix (Frigate) | one patch |
| [themactep/thingino-firmware](https://github.com/themactep/thingino-firmware) | generic platform-enabling fixes and web UI platform flags; the SigmaStar platform (John Chia's, re-cut onto current master); three new packages (`thingino-lensd`, `thingino-nettest`, `thingino-ipud`); five camera profiles | separate PRs per group |

## Patch map

The 22 patches onto `themactep/thingino-firmware` master `b8bcd6740`, in
[`patches/thingino-sigmastar/`](../patches/thingino-sigmastar/). The last
column says whether a patch only matters to SigmaStar builds or is generic
(useful on Ingenic too).

| # | Patch | Mainly for | Scope |
|---|---|---|---|
| 0001 | sigmastar: vendor packages (sdk, lib, u-boot, sensor headers) | SigmaStar platform | SigmaStar-only |
| 0002 | sigmastar: Infinity6C board, SoC and kernel support | SigmaStar platform | SigmaStar-only |
| 0003 | sigmastar: config fragments and Config/Makefile wiring | SigmaStar platform | SigmaStar-only, in shared files |
| 0004 | sigmastar: ARM GCC 16 toolchain producers and CI build | SigmaStar platform | SigmaStar-only, in shared workflows |
| 0005 | sigmastar: platform utilities, the PWM light tool, SigmaStar's lib-serial-mac | SigmaStar platform | SigmaStar-only |
| 0006 | sigmastar: build Raptor against the raptor-hal fork; reference target | SigmaStar platform | SigmaStar-only; one generic fix |
| 0007 | thingino-uhttpd: honor If-None-Match over If-Modified-Since; cache policy | OpenWrt uhttpd; Thingino | generic |
| 0008 | thingino-onvif: emit each zoom default space in schema order | thingino-onvif | generic |
| 0009 | thingino: platform-enabling fixes and web UI platform flags | Thingino | generic; the flags default to the old behaviour |
| 0010 | thingino-raptor: non-Ingenic link fix and day/night for PWM IR banks (ric) | raptor 0101 to 0105; Thingino | generic; the SigmaStar installs are gated on the vendor |
| 0011 | thingino-raptor: RTSP/ONVIF delivery and Ch1 preview fallback (rsd, onvif) | raptor 0106 to 0108; Thingino | generic |
| 0012 | thingino-raptor: streaming and encoder rate-control, Image Quality, motion gating | raptor 0109 to 0113; Thingino | generic; the SigmaStar flag values ride along |
| 0013 | thingino-raptor: raptor-watchdog fault reports and recovery | SigmaStar platform; Thingino | the watchdog SigmaStar-only; the agent cap generic |
| 0014 | thingino-nettest: Tools Bandwidth test (iperf3 + link rate) | Thingino (new package) | generic |
| 0015 | thingino-lensd: AF feed, ONVIF PTZ, serial IR-cut, Pelco-D (lensd -P) | Thingino (new package) | builds on SigmaStar; the AF feed SigmaStar-only, the PTZ layer protocol-level |
| 0016 | thingino-lensd: web UI PTZ plugin (joystick, presets, zoom/focus) | Thingino (new package) | protocol-level |
| 0017 | thingino-sysupgrade: ship thingino-update, fence sysupgrade; dirty build-id | units on the OEM layout; Thingino | OEM-layout units; one generic fix |
| 0018 | cameras: UVision MC-A85 / Anpviz IPC-D3B83B-S (`yma85_ssc378_gc8613`, 4K) | SigmaStar platform | SigmaStar-only |
| 0019 | cameras: Jennov JL12D2 / UVision MCL12D2 (`mcl12d2_ssc377d_imx335`, PTZ) | SigmaStar platform | SigmaStar-only |
| 0020 | cameras: Anpviz IPC-B8A63WD-S / UVision MC-F46D (`ymf46d_ssc377d_gc4653`) | SigmaStar platform | SigmaStar-only |
| 0021 | cameras: N803 PTZ (`n803_ssc378qe_imx415`, Pelco-D head) | SigmaStar platform | SigmaStar-only |
| 0022 | thingino-ipud: on-camera object detection on the Infinity6C IPU | SigmaStar platform (new package) | SigmaStar-only |

The 13 patches onto `gtxaspec/raptor-hal` main `9f09664`, in
[`patches/raptor-hal/`](../patches/raptor-hal/), all for the Infinity6C
backend:

| # | Patch | From |
|---|---|---|
| 0001 | sigmastar-headers: vendor John Chia's SigmaStar MI ABI headers @ 6fb6eec | John Chia, verbatim |
| 0002 | infinity6c: import John Chia's backend and SigmaStar glue @ 672f8b3 | John Chia, verbatim |
| 0003 | build: vendor hooks for the SigmaStar backend | John Chia's hook diff |
| 0004 | infinity6c: build against the upstream HAL interface | this port |
| 0005 | infinity6c: anti-flicker via FlickerEx manual lock | this port |
| 0006 | infinity6c: map upstream raptor's 0..255 image knobs onto native units | this port |
| 0007 | FORK.md: what this fork is, where each part came from, how to maintain it | this port |
| 0008 | infinity6c: report ae_luma on the 0..255 scale | this port |
| 0009 | infinity6c: SCL->VENC ring depth from RSS_SCL_RING_DIV | this port |
| 0010 | infinity6c: opt-in AE max-shutter cap from RSS_AE_MAX_SHUTTER_US | this port |
| 0011 | infinity6c: drop the dead H.265 rate-mode substitution | this port |
| 0012 | infinity6c: encoder I-frame cap, I/P QP bounds and delta, super frames | this port |
| 0013 | infinity6c: opt-in encoder statistics from RSS_VENC_STATS | this port |

The first two patches vendor John Chia's code, so the series applies to a bare
`gtxaspec/raptor-hal` checkout. [raptor-hal-FORK.md](raptor-hal-FORK.md) says
where each part came from and how the fork is maintained.

## 1. Fixes and features for upstream

### 1.1 OpenWrt uhttpd

Conditional requests: `If-None-Match` decides when it is present, and
`If-Modified-Since` is ignored then (RFC 9110, section 13.2.2). uhttpd tested
the date first, so a newer date answered 304 even when the ETag did not match,
and a browser that last saw another device at the same address kept that
device's files. In Thingino it is a package patch meanwhile,
`package/thingino-uhttpd/0007-file-if-none-match-overrides-if-modified-since.patch`,
which shares its number with Thingino's own `0007-proc-pass-range-to-cgi.patch`;
both apply. *Verified on the MC-A85 (a curl matrix).* `[0007]`

### 1.2 Raptor (gtxaspec/raptor)

Thirteen patches in `package/thingino-raptor/`, numbered from 0101 so that the
patches Thingino itself numbers from 0001 (at this base, its backport of
[gtxaspec/raptor#87](https://github.com/gtxaspec/raptor/pull/87)) apply first.
None is SigmaStar-only in effect: each fixes a general bug or adds a general
feature, found on SigmaStar first, and each can go to raptor as a small
independent PR. Their package side (the `RAPTOR_*` keys and build options)
goes to Thingino with them.

- **0101, non-Ingenic link fix.** `LDFLAGS_HAL` stops hard-coding the Ingenic
  SDK libraries, so a non-Ingenic HAL backend links instead of failing on
  `cannot find -limp`. `[0010]`
- **0102 to 0105, day/night for PWM-dimmed IR banks (ric).** An
  `[ircut] irled_cmd` hook runs `<cmd> on` or `<cmd> off` for an 850 nm bank
  that is not on a GPIO. The luma trigger counts such a bank as IR, so the day
  test no longer runs on IR-inflated luma; a luma day also needs low gain, and
  a day the night test soon takes back arms the backoff lockout, so days stick.
  An IR level ladder (`ir_levels`, `ir_step_gain`) steps dimmable IR by night
  gain, since one fixed level floods near walls or under-lights far fields.
  Exposure is polled on a fixed cadence: every control request woke the loop
  early, and the debounce shrank from 4.9 s to 0.3 s. Thingino's
  `thingino-raptor-config` gains the three `RAPTOR_IRCUT_*` keys (`Kconfig`
  and `conf-map`). *Verified on the MC-A85 and YMF46D, whose IR banks never
  lit at night before.* `[0010]`
- **0106, hooks around the stack.** `S31raptor` runs each `/etc/raptor.d/*`
  with `stop` before the daemons go down and `start` after they are up. A
  process outside the stack that calls the ISP, such as a lens daemon, must
  stop first, or the vendor MI module oopses and the next `rvd` hangs; the
  detector of 1.5.6 uses the same hooks. Cut for raptor `101fb35`, the pin of
  this base, whose `S31raptor` runs under
  `flock` ([gtxaspec/raptor#83](https://github.com/gtxaspec/raptor/pull/83)).
  *Verified on the JL12D2.* `[0011]`
- **0107, each RTSP reply in one piece.** `TCP_CORK` around each request's
  dispatch. `rsd` sent a reply in about 20 TCP segments; the Happytime RTSP
  client of a Zosi (Ansjer) NVR stalled on them, reset every session after
  about 1.3 s and showed "unconnected". *Verified with that NVR.* The fix is
  generic for any client that stalls on split replies. `[0011]`
- **0108, DESCRIBE with the parameter sets.** DESCRIBE asks for an IDR and
  waits up to 2 s for SPS and PPS (about 80 ms in practice). Answered without
  them, between ring creation and the first keyframe (at boot, after an
  `S31raptor` restart), go2rtc in Frigate 0.17.2 built the browser's MSE init
  segment from a 128x96 placeholder SPS and kept it while that producer lived,
  so Frigate drew a 16:9 stream at 4:3. *Verified with Frigate.* `[0011]`
- **0109, JPEG rings sized for the largest JPEG.** 2.7 bits a pixel at quality
  70 to 89, with a 32 KB floor, instead of the average: a detailed scene's sub
  JPEG overflowed the ring (`ENOSPC`), frames dropped and the MJPEG preview
  stalled on a YMF46D. `[0012]`
- **0110, an environment file for the daemons.** `S31raptor` exports
  `/etc/default/raptor` to them; the Infinity6C HAL reads its ring depth,
  shutter cap and encoder statistics settings (`RSS_*`) from there. Cut for
  raptor `101fb35`, like 0106. `[0012]`
- **0111, ISP capability reporting.** `rvd get-isp-caps` answers one boolean
  per `set-` op, plus `ivs`, so a web UI can offer only the knobs the HAL
  applies. On the Infinity6C the web UI offered sharpness and white balance,
  which did nothing, and hid controls that worked. `[0012]`
- **0112, a full-frame OSD region kept inside the frame.** `rvd` holds every
  OSD region a margin off the frame's edges. A region as large as the frame,
  such as the overlay `rod` adds for detections, was still pushed to the
  margin: created at (10,10), it reached past the right and bottom edges and
  was drawn sheared, green dashes across the sub stream in place of the boxes
  (seen on an Ingenic T31). A region too large for the margin on an axis now
  gets none on that axis; regions that fit are placed as before. New in this
  cut. `[0012]`
- **0113, the OSD pool sized for the detection overlay.** The pool is sized
  from the `[osd.*]` sections of `raptor.conf`. With `[motion]` enabled `rod`
  adds a full-frame overlay over each sub stream by itself, and nothing
  counted it: the pool stayed at 448 KB while a 640x360 overlay needs 900 KB,
  so no detection box was ever drawn into the stream. The pool now counts
  that overlay when `raptor.conf` declares none of its own. New in this cut.
  `[0012]`

### 1.3 raptor-hal (gtxaspec/raptor-hal)

The one carried fork: 13 patches on gtxaspec main `9f09664`. The rest of the
Raptor stack stays upstream's, at Thingino's pins (raptor with the patches of
1.2). Thingino builds SigmaStar against the fork `[0006]`; every other vendor
builds upstream raptor-hal.

- **John Chia's headers and backend, verbatim.** The reconstructed MI 2.x and
  MI 3.0 ABI headers (johnchia/sigmastar-headers `6fb6eec`), vendored as a
  plain directory so the build needs nothing online, and the Infinity6C
  backend `src/infinity6c/` with its SigmaStar glue (johnchia/raptor-hal
  `672f8b3`), which reaches MI through `dlopen`. `[raptor-hal 0001, 0002]`
- **His build hooks**, applied to upstream: the vendor fragment, vendor-keyed
  source lists and the non-Ingenic arms of the platform chains.
  `[raptor-hal 0003]`
- **The bridge.** His backend was written against his own fork's HAL
  interface. A compat shim detects upstream by the absence of `RSS_ISP_AUTO`
  and adapts: six ISP getters are published with upstream's `uint8_t *`
  signature, the knob-caps op and the green WB gain are left out, and the
  sensor mode is forced to auto. If upstream ever defines `RSS_ISP_AUTO` the
  shim switches off, so the two interfaces must be checked against each other
  then. It goes away if the backend moves to the current interface.
  `[raptor-hal 0004]`
- **FlickerEx anti-flicker.** Upstream's legacy `MI_ISP_AE_SetFlicker` is
  ignored by the GC8613 tuning, so the backend sets `MI_ISP_AE_SetFlickerEx`
  with a manual lock at the mains frequency, deferred to the first frame (an
  earlier call oopses the kernel on a cold ISP). Banding at a forced 12 ms
  shutter fell from 3.8 to 0.03 DN. *Verified on the MC-A85.*
  `[raptor-hal 0005]`
- **The knob scale map.** Upstream `rvd`, `raptorctl` and the web UI speak
  0..255 for every image knob, with 128 as the default, and `rvd` pushes 128
  at start; the backend speaks each module's native units. Unmapped, the
  start-up 128 was refused by the colour, temporal-NR and AE-compensation
  knobs, and pinned DRC and defog to half strength over the tuning on every
  boot. The map leaves the tuning alone at 128, inverts on read-back, and has
  a host test. `[raptor-hal 0006]`
- **The fork's record**, [raptor-hal-FORK.md](raptor-hal-FORK.md), which also
  records both host tests passing on the rebased fork. `[raptor-hal 0007]`
- **`ae_luma` on the 0..255 scale.** CUS3A's 10-bit average luma was passed
  through, so every ric luma comparison ran four times too bright; it is
  shifted to 8 bits. `[raptor-hal 0008]`
- **SCL-to-VENC ring depth** from `RSS_SCL_RING_DIV`: a quarter frame (the
  default), a half or a whole one, logged at start. With a quarter frame the
  scaler lapped the main encoder on a YMF46D with a 720p sub: the main turned
  to all IDRs and the sub fell to 13 fps; a half or a whole frame fixed it.
  Each step costs video memory. Thingino sets it per profile through
  `BR2_PACKAGE_THINGINO_RAPTOR_SCL_RING_DIV` `[0010]`. `[raptor-hal 0009]`
- **An opt-in AE max-shutter cap** from `RSS_AE_MAX_SHUTTER_US`: it lowers the
  tuning's ceiling (about 100 ms, which slows the sensor at night), never
  below the tuning's minimum, after the first frame and every tuning reload.
  On a YMF46D at night a 33.3 ms cap held 25 fps instead of about 20, at about
  50 % more gain. Off on every profile
  (`BR2_PACKAGE_THINGINO_RAPTOR_AE_MAX_SHUTTER_US` is empty). `[raptor-hal 0010]`
- **Dead code removed:** the H.265 rate-mode substitution, which could no
  longer fire; no behaviour change. `[raptor-hal 0011]`
- **Rate-control extras.** Keyframes took nearly a second's budget at a 1 s
  GOP, and `raptorctl`'s QP-bound, per-frame QP, I/P delta, fixed QP,
  maximum-picture-size and super-frame commands all answered "not supported".
  The backend now has those ops, on a local ABI header checked against the
  shipped MI 3.0 libraries and a pure, host-tested builder; the six MI calls
  bind optionally, so a library without them still encodes. *Verified on an
  SSC377D at night (VBR):* the I-frame QP bounds and the I/P delta work (a
  delta of -6 cut keyframes from 228 to 57 KB), the maximum I-frame size is a
  soft cap, and MI refuses super-frame re-encode but accepts discard.
  `[raptor-hal 0012]`
- **Encoder statistics**, opt-in (`RSS_VENC_STATS=<seconds>`): per channel,
  the keyframes' share of the bytes, sizes and QP per frame type, and the
  rate-control parameters read back. Unset, it costs one branch per frame.
  `[raptor-hal 0013]`

Meant for `gtxaspec/raptor-hal` as one series, with John Chia's work credited
to him, since most of the code is his; [UPSTREAM-PLAN.md](UPSTREAM-PLAN.md)
proposes the order of its pull requests. Everything is keyed by vendor and
family (`mk/<vendor>.mk`, one backend directory and one header directory per
family), so Infinity6E and 6B0 can slot in later; only Infinity6C builds
today, since the MI 2.x backend those families need is not carried. Whether
the HAL interface should report each knob's native range, so that the 0..255
map can retire, is one of the
[open questions](../README.md#open-questions-for-the-discussion).

### 1.4 thingino-onvif (themactep/thingino-onvif)

Each zoom default space is emitted in its schema-sequence position. Out of
`xs:sequence` order, zeep (Frigate's ONVIF parser) dropped the pan/tilt spaces,
so Frigate showed the zoom buttons but no arrows. In Thingino it is a package
patch,
`package/thingino-onvif/0001-ptz-emit-each-zoom-default-space-in-schema-order.patch`,
written on Thingino's thingino-onvif pin. *Verified on the JL12D2 with
Frigate.* `[0008]`

### 1.5 Thingino (themactep/thingino-firmware)

#### 1.5.1 Generic fixes

Small and independent; each is useful on Ingenic too.

- Submodules really off: Buildroot fetches submodules for any non-empty
  `_GIT_SUBMODULES`, `NO` included, so off is empty (the SigmaStar HAL build
  still cloned `ingenic-headers`). `[0006]`
- The "Photosensing Config" link appears only with `thingino-daynightd`; under
  raptor alone it 404s. `[0009]`
- ONVIF profiles carry the streams' real sizes from `raptor.conf`;
  `S96onvif_discovery` left `onvif.json`'s 1920x1080 and 640x360 defaults.
  `[0011]`
- Ch1 previews fall back to JPEG channel 0. `rvd` numbers JPEG channels over
  the streams that have one, so with the main's JPEG off the sub's is channel
  0, and the Ch1 snapshot and MJPEG answered 503. `[0011, 0012]`
- A cache policy, with the uhttpd fix of 1.1
  (`uhttpd -H /etc/uhttpd-cache.json`): `runtime-config.js` and the `/x/` CGIs
  are `no-store`, `/a/` scripts and styles are cached far-future (`immutable`)
  at addresses that carry a `?ts=` stamp only, which stops a 304 storm on
  every navigation, and the rest is revalidated. A camera at an address
  another device used before no longer shows that device's footer and config.
  Upstream has since gained uhttpd's `-M` and `-F` switches
  ([#2065](https://github.com/themactep/thingino-firmware/pull/2065):
  `max-age` for `/a/`, `no-cache` for the rest); they are left unset in this
  series, so that a response carries one `Cache-Control` header. What the
  handler adds to upstream's policy is the two `no-store` rules. `[0007]`
- The page stamp. `thingino-webui` stamps every page once all packages have
  installed theirs (`THINGINO_WEBUI_STAMP_PAGES`), with a hash of every `/a/`
  script and stylesheet in the image, so an asset's address changes exactly
  when an asset does. The install step's stamp never reaches the pages raptor
  and the plugins install: 14 of 47 pages asked for bare `/a/` addresses,
  which the far-future rule of the previous cut kept for a year, so after an
  update a browser ran the old scripts until a hard reload. Upstream has since
  added a final asset tag of its own (the same PR #2065), which stamps the
  image's copy of every page again; with it, this hook is what stamps the
  build's target tree, and may no longer be needed upstream. *Tested on
  an N803 without a reflash:* a changed script reached the browser on the
  first load with no hard reload, and warm loads still take every versioned
  script and stylesheet from cache. `[0007]`
- Small boards under memory pressure. The web UI's parallel requests ran a
  64 MB camera out of memory, and the kernel killed `rvd`. On a board with
  less than 48 MB of RAM uhttpd now runs 6 CGI scripts at once in place of 20
  `[0007]`; the agent listener answers at most 3 requests at once
  (`AGENT_MAX_REQUESTS`) `[0013]`; and uhttpd, the agent and what they start
  get an `oom_score_adj` of 800, so the kernel takes them before the video
  daemons. `[0007, 0013]`
- An image built from a tree with uncommitted changes stamps `BUILD_ID` and
  `COMMIT_ID` with `-dirty`, so a development image never reads as the commit
  before it. Generic by content; not proposed yet. `[0017]`

Merged upstream since the previous cut, and no longer in the series:

- `thingino-isp` pulls no Ingenic ISP stack on other vendors: the ISP choice
  pulled the Ingenic SDK, its libraries and `libimp` into a SigmaStar config.
  Merged as PR #2063; it left patch 0009.
- `thingino-ethernet` selects the JZ MAC kernel options on Ingenic only; the
  select altered a SigmaStar kernel config. Merged as PR #2070, which moves
  the select into the Ingenic block; it left patch 0009.
- The Ingenic `lib-serial-mac` is installed with the Ingenic files: the
  global copy reads Ingenic serial registers, so on other vendors the
  hostname suffix came out empty. Merged as PR #2069; the move left patch
  0005, which keeps the SigmaStar copy (1.5.3).
- The vendor choice the profiles answered is gone: upstream derives the
  vendor from the SoC model (PR #2068), and the profiles of this series no
  longer set it.
- The Infinity6C family: `soc/sigmastar/infinity6c.mk` with the six models
  and their RAM sizes, the models' `BR2_SOC_FAMILY` line in `Config.soc.in`,
  and the SoC fragment `soc-infinity6c` (cortex-a7, neon-vfpv4, Thumb-2, to
  match the vendor's ARMv7 modules and libraries). Merged as PR #2083; it
  left patches 0002 and 0003, and the series' own SoC fragment, which took
  the core and FPU from the family file through two substitutions in the
  `Makefile`, is gone with it.

#### 1.5.2 Web UI platform flags and the pages that follow the HAL

Feature flags in a streamer plugin's web UI manifest, each defaulting to the
old behaviour. The mechanism belongs in Thingino; the SigmaStar values, set in
`raptor-sigmastar.webui.json` `[0012]`, stay with the platform.

- `motion: false`: no on-camera motion controls where the HAL has no IVS, and
  the camera refuses to enable motion (`S32raptor-motion`,
  `raptor-motion-watch`); Frigate detects motion for these cameras.
  `[0009, 0012]`
- `audio_out: false`: the speaker control is locked where no speaker-enable is
  wired; on the MC-A85 and YMF46D that GPIO is unmapped. Without the flag the
  speaker stays usable. `[0009, 0012]`
- `osd_restart_applies: true`: the OSD page offers a stream restart instead of
  a reboot. A restart applied the OSD on the Infinity6C and on the Ingenic
  T41; upstream's reboot advice is a T20 workaround. `[0009]`

The pages:

- **Image Quality** shows only the controls the HAL applies (`get-isp-caps`,
  raptor 0111): on the Infinity6C brightness, contrast, saturation, AE
  compensation, anti-flicker, temporal NR, WDR and defog. Before, it saved, and
  reported success for, settings the HAL refused (sharpness, white balance, a
  live flip). A flip now saves with a "restart stream" prompt, since the SoC
  applies a flip only on restart, and the agent treats an error reply as a
  failure. The noise-reduction knobs use upstream's names from
  [#1834](https://github.com/themactep/thingino-firmware/pull/1834)
  (`noise_reduction`, `temporal_noise_reduction`); the spatial one is hidden
  where the HAL reports none, as on the Infinity6C. `[0012]`
- **Streamer pages** apply a stream as one change, from per-camera menus
  (`BR2_PACKAGE_THINGINO_RAPTOR_UI_*`: resolutions, rates, bitrates, codecs,
  profiles, RC modes, GOP, JPEG qualities, the video memory kept free). Saved
  field by field, one resolution change rebuilt the pipeline twice. The main
  stream's rate is the sensor's, and a sub's rate must divide it, or frames
  drop unevenly; VBR caps are explicit; each stream reports its video-memory
  (MMA) cost, and a change that would not fit is refused before it is written.
  `[0010, 0012]`
- **Sensor IQ** finds the sensor and its IQ file on SigmaStar
  (`/etc/sensor/model`; `sensor-iq-name` gives `<sensor>.bin` for the
  `infinity*` SoCs). The page showed no model and an empty md5; upstream's
  sensor-IQ rework
  ([#1966](https://github.com/themactep/thingino-firmware/pull/1966),
  [#1795](https://github.com/themactep/thingino-firmware/pull/1795)) did not
  cover SigmaStar. `[0009]`
- **Digital zoom bar.** Its probe (`zoom.cgi?info=1`) asks `rvd` for a
  non-zero crop window. Without `/proc/jz/sensor`, as on SigmaStar, `rvd`
  answers `get-zoom` with a zero window and refuses `set-zoom`, and the probe
  took that for support, so the bar would show and fail on a click; now it
  stays off. Tested on the host with a stand-in `raptorctl`, not yet on a
  camera. `[0009]`

#### 1.5.3 The SigmaStar Infinity6C platform

This port re-cut John Chia's SigmaStar support onto current master as an
additive layer of new files ([the README says why](../README.md#why-this-shape))
and fixed what upstream had changed underneath it. It is going upstream as a
series of small pull requests, crediting his work;
[UPSTREAM-PLAN.md](UPSTREAM-PLAN.md) has the order.

- **Vendor packages:** `sigmastar-sdk` (kernel modules, sensor drivers, IQ
  files and the MI load script, indexed by vendor drop), `sigmastar-lib` (the
  vendor's binary MI userspace libraries), `sigmastar-uboot`, and
  `sigmastar-sensor-headers`, which fetches the 1230 drop's sensor-framework
  headers from `openipc/sensors` at a pinned commit, since the drivers must
  build against the headers that match the drop's `mi.ko`; the SDK's own
  patch adds only the GC8613 driver. Two SDK fixes: `iqfile1.bin` aliased to
  `iqfile0.bin` (libcus3a picks the IQ file by channel mask, and without the
  alias AWB never initialised: a green picture), and the GC8613 on four
  lanes, its driver built from source. Each package's license label follows
  its sources: the SDK is labelled proprietary for the MI modules and
  SigmaStar's sensor drivers and GPL for the two sensor sources that say so,
  and `sigmastar-light`, `thingino-lensd` and `thingino-nettest` are MIT
  ([NOTICE.md](../NOTICE.md)). `[0001]`
- **Board, SoC and kernel:** `board/sigmastar` (the Infinity6C kernel config,
  the board DTS patch directory, the post-image script, toolchain notes, a
  vendor overlay), what upstream's `soc/sigmastar/infinity6c.mk` does not
  hold yet (the bootloader image name, the vendor-drop variables, exported,
  and the sensor-source switch), and `kernels/sigmastar.mk`: one `johnchia/linux` branch
  per family, pinned by hash, since upstream moved kernel selection
  ([#1442](https://github.com/themactep/thingino-firmware/pull/1442)) and
  requires `KERNEL_BRANCH`. `[0002]`
- **Config and wiring:** the `core-sigmastar` fragment, re-synced with
  `core.fragment` (the SoC fragment is upstream's `soc-infinity6c`);
  `Config.in` sources the SigmaStar packages and the three new ones, with
  `BR2_TARGET_UBOOT` kept Ingenic-only; `Config.soc.in` gains the
  sensor-source option; image assembly in the split Makefiles. One package set on every SigmaStar board (the PWM light tool,
  `lensd`, the block-device automount, the sensor sources, and `ipud`, off
  until enabled); what a board has is config in its defconfig: the light
  channels, the lensd mode, the microSD modules. `[0003]`
- **Toolchains and CI:** ARM GCC 16 toolchain producers (glibc and uClibc) in
  upstream's two toolchain workflows, a SigmaStar build workflow, and
  `scripts/check-target-libs.sh`, which checks that every `DT_NEEDED` in the
  target resolves. No run of the build workflow in CI is on record. `[0004]`
- **Platform utilities:** the SigmaStar `soc`, `sensor`, `usb-role` and
  `S03mac` under `thingino-system`'s `files/sigmastar/`, in upstream's
  per-vendor layout
  ([#1428](https://github.com/themactep/thingino-firmware/pull/1428)), with a
  `lib-serial-mac` of their own, installed with them, since upstream's reads
  Ingenic serial registers; and `sigmastar-light`, one light command for
  PWM-dimmed IR and white banks with brightness, on the command line of
  Thingino's GPIO light script, each board's channels from its defconfig and
  written to `/etc/default/light`. `[0005]`
- **Raptor on SigmaStar:** SigmaStar builds raptor-hal from the fork (1.3),
  set as a late override at the bottom of `thingino-raptor-hal.mk`, so an
  upstream pin bump never conflicts; every other vendor keeps upstream's pin.
  The HAL reaches the MI libraries through `dlopen`, so its SigmaStar symbol
  selects `sigmastar-lib` for the build order. Once the backend is in
  gtxaspec/raptor-hal this becomes a plain pin bump. `[0006]` The package
  side of the raptor patches sits in `thingino-raptor`'s `Config.in` and
  `.mk`: the Streamer menu options, the ring depth and shutter-cap options,
  and the SigmaStar installs (the web UI flags and the watchdog). `[0010]`
- **raptor-watchdog**, on SigmaStar builds only. Every 5 s, a new `[MI ERR]`
  line saves a gzipped fault report (the newest 5 kept, reboot reports apart);
  a stalled encoder port, or `rvd` stuck in the driver, gets a report and a
  raptor restart, then a reboot, at most 3 an hour, and `rvd` stuck in
  teardown a reboot at once. The Infinity6C encoder can wedge while the camera
  stays up, and the kernel ring that holds the cause wraps within minutes.
  New in this cut: `rvd` gone for 15 s while `rsd` still runs also gets a
  report and a raptor restart, once per disappearance, because on a 64 MB
  board the kernel killed `rvd` for memory and nothing restarted it; and a
  poll that finds nothing wrong starts two processes (the sleep and one
  `awk`) where it started about 25, which had been most of the processes an
  idle camera started, about 300 a minute. It reads MI logs and tables, so it
  stays with the platform. `[0013]`
- **The stock flash layout.** The vendor overlay points `fw_setenv` at a
  scratch file on every board: on the OEM layout U-Boot's saved env sits on
  the kernel partition's first block, and the first-boot `fw_setenv` once
  erased a uImage header `[0002]`. `thingino-update` updates and reverts units
  that keep the OEM U-Boot: it writes the kernel and rootfs only, never the
  boot partition or the overlay, with a model and SoC guard, and takes the
  `.bin` the stock web uploader takes. `sysupgrade -f` and `-b` are fenced on
  units with no env, all or upgrade partition, where a full image and an env
  reset could leave a unit that does not boot. Whether upstream wants an
  updater for OEM layouts, or the fence, is open. `[0017]`
- **Command replay.** A `/etc/raptor.d/replay` hook runs each line of
  `/etc/raptor-replay.conf` (shipped as commented examples) as a `raptorctl`
  command after every start of the stack, for settings `rvd` keeps only while
  it runs, such as the encoder rate-control extras. Boot, the web UI's restart
  and the watchdog's recovery all go through it. The mechanism is generic, but
  it is an interim (part 3) and is not proposed by itself. `[0002]`

#### 1.5.4 New package: thingino-lensd (serial lens/PTZ boards)

For PTZ cameras built around a serial lens/PTZ board: the JL12D2's autofocus
head and the N803's Pelco-D head. The head protocols are in
[oem-reference/JL12D2-PTZ-PROTOCOL.md](oem-reference/JL12D2-PTZ-PROTOCOL.md) and
[oem-reference/N803-LENS-PROTOCOL.md](oem-reference/N803-LENS-PROTOCOL.md).

- **Autofocus feed:** two focus values a frame from the ISP's AF statistics,
  with the vendor's AF window and filter, as the stock firmware does (measured
  on a stock unit). Without it the lens never refocuses after a zoom. `[0015]`
- **ONVIF PTZ** through `lensctl`: continuous pan/tilt/zoom, presets, home and
  the zoom position, which Frigate shows with arrows and zoom. 31 named
  presets (board presets 1 to 31) plus home on board preset 32, the last one
  the board stores, and a clear "home not set" answer. A velocity maps to a
  Pelco-D level as stock maps it, `floor(10 * abs(v)) + 1`; the ONVIF server
  sends its maximum step by the velocity's sign, so ContinuousMove always runs
  at level 10 (one reading on a second unit disagreed and is not resolved).
  `[0015, 0016]`
- **ONVIF RelativeMove**, which Frigate's autotracking needs. The heads report
  no pan or tilt position, so a move is timed from the head's measured top
  speed, dead time and ramp at each Pelco-D level (`heads/<head>.conf`),
  scaled by the field of view at the zoom: the pan leg, a full stop, then the
  tilt leg, since the head latches an axis. `lensd` holds the move status at
  "moving" through the move, a settle time and a preset recall, so it never
  sticks. A head without measurements gets no RelativeMove. *Measured on the
  JL12D2.* `[0015]`
- **Zoom for autotracking:** ONVIF AbsoluteMove moves the zoom to a position
  read back from the board (`lensctl zoom_to`; pan and tilt are ignored), a
  RelativeMove's zoom term runs after its pan and tilt legs, no relative move
  runs during a preset recall, and a no-op zoom is dropped. Before, ONVIF zoom
  worked through ContinuousMove only, while Frigate's `zooming: absolute`
  tracking zooms through AbsoluteMove. Two deliberate departures from
  executing Frigate's moves literally: one zoom-in narrows the view at most
  1.5x (Frigate asks for most of the range as soon as its area test passes,
  and one such move lost the tracked object), and a preset recall holds the
  move status for as long as the way back takes. The settle time, 650 ms,
  covers Frigate's frame lag. A head without zoom measurements offers no
  AbsoluteMove. *Measured on the JL12D2.* `[0015]`
- **IR-cut over the serial frame.** On the JL12D2 the IR-cut filter sits on
  the lens head, so `lensd` switches it in byte 11 of the AF frame (day
  `0x00`, night `0x01`), following ric's day/night pins as read from
  `raptor.conf`; night is mono plus IR. `lensd -m day` or `-m night` starts in
  ric's current state, which `S33lensd` asks for, since ric pulses its pin
  only on a change and a lensd started after dark kept the filter in. See
  [oem-reference/JL12D2-IRCUT-MECHANISM-RE.md](oem-reference/JL12D2-IRCUT-MECHANISM-RE.md).
  `[0015, 0019]`
- **Pelco-D mode** (`lensd -P`, no AF feed) for heads that speak plain
  Pelco-D, used by the N803. `[0015]`
- **One package for every board:** `BR2_PACKAGE_THINGINO_LENSD_MODE` (`off`,
  `af`, `pelco`) and the head's name (`BR2_PACKAGE_THINGINO_LENSD_HEAD`) go to
  `/etc/default/lensd`; in `off` lensd does not run, and the ONVIF PTZ files,
  the head files and the web UI plugin are not installed. `[0015]`
- **Web UI PTZ plugin**, in `thingino-motors`' layout: a joystick overlay with
  speed by reach, a PTZ Settings modal, zoom and focus buttons, presets and
  home, backed by `/x/json-lensd.cgi`. Its `motors` script turns PTZ on in the
  ONVIF server. `[0016]`

The AF feed uses SigmaStar's MI ISP API; the PTZ, ONVIF and web UI parts are
protocol-level and would serve any Pelco-D board, so upstream may want them
split along that line.

#### 1.5.5 New package: thingino-nettest

A diagnostic tool, generic to any camera: a **Tools > Bandwidth test** page
and CGI that run `iperf3` and read the PHY link rate (`miiread`), for chasing
packet loss across a switch or NVR path. `[0014]`

#### 1.5.6 New package: thingino-ipud (on-camera object detection)

YOLOv5 detection on the Infinity6C IPU, the SoC's neural-network unit. It uses
SigmaStar's MI IPU and SCL APIs, so it belongs with the SigmaStar platform
series. `[0022]`

- **Frames** come from an SCL output port raptor left unused, at the model's
  input size, into the IPU's input tensor without a copy where the frame
  layout allows; on the first frame ipud runs both paths and keeps zero copy
  only if the outputs are byte-identical.
- **Inference** runs through the drop's `libmi_ipu`, with the input flushed
  from the CPU cache before each invoke (otherwise the IPU reads part of the
  previous frame), then YOLOv5 decode and per-class NMS.
- **Memory:** once zero copy passes, the IPU channel is re-created with no
  input buffer, and the SCL port holds one frame at 12 a second or less (two
  at full rate), so ipud takes 4.27 MB of video memory instead of 5.42 at the
  default 10 a second. *Measured on the SSC378DE, SSC378QE and SSC377D.*
- **Outputs:** a status file (read by the web UI page and the preview
  overlay), a local socket (`/run/ipud.sock`, read with `ipucat`) and MQTT;
  and, each off by default, ONVIF events on the PeopleDetect, VehicleDetect
  and DogCatDetect topics, Home Assistant discovery on the camera's own device
  through `thingino-ha`, and a Frigate manual event while a class is present.
  Frigate files a manual event as an alert, so a camera can alert on a class
  left out of its Frigate alert labels. *The Frigate output has run on a
  JL12D2.*
- **Web UI:** Settings > Object detection, and a preview overlay that is
  pushed and off until turned on. A Detections button opens one server-sent
  event per inference, closed while the tab is hidden; it replaced a poll
  twice a second. *Measured on an N803:* one stream at about 0.3 % CPU, where
  the poll took about 16 %.
- **Start and stop:** `S35ipud` starts it from the `ipud` block of
  `/etc/thingino.json`, with the package's defaults for missing keys, and a
  `/etc/raptor.d` hook (raptor 0106) stops it before `rvd` tears the pipeline
  down and starts it again after. A report class the model lacks is skipped
  with a warning (a model with other class names used to stop ipud silently),
  and start-up failures go to the status file.
- **On every SigmaStar board, off until enabled.** `[0003]`
- **The model is not included:** it is a camera vendor's file. ipud reads it
  from the image (when a build staged one into the package's git-ignored
  `vendor/` folder), from a folder on the SD card, or from a custom path; the
  class names come from a `.labels` file beside it, by default the six COCO
  classes of the model in the JL12D2's stock firmware (person, bicycle, car,
  motorcycle, bus, truck), and the overlay colours each.
  [ipu-extract](../tools/ipu-extract/README.md) takes the model out of
  firmware a user already has.
- **No IPU firmware file is needed.** The drop's runtime never reads the file
  the IPU is opened with: an empty and an all-zero file ran the model on an
  SSC378DE camera, and ipud ran with no file at all on an N803 and a JL12D2.
  So `-f` is optional, `S35ipud` passes a file only when one is there, the
  package installs none and the web page no longer checks for one. New in
  this cut.

#### 1.5.7 Camera profiles

| Camera | Profile | Patch |
|---|---|---|
| reference target (John Chia's): SSC377QE + IMX335, board-less | `noname_ssc377qe_imx335` | 0006 |
| UVision MC-A85 / Anpviz IPC-D3B83B-S | `yma85_ssc378_gc8613` | 0018 |
| Jennov JL12D2 / UVision MCL12D2 | `mcl12d2_ssc377d_imx335` | 0019 |
| Anpviz IPC-B8A63WD-S / UVision MC-F46D | `ymf46d_ssc377d_gc4653` | 0020 |
| N803 | `n803_ssc378qe_imx415` | 0021 |

Each profile is `configs/cameras/<profile>/` (defconfig, kernel `.config`
fragment, overlay, and a `raptor.config` with the `RAPTOR_*` keys) plus a board
device-tree patch under `board/sigmastar/infinity6c/patches/linux/`. The JL12D2
and YMF46D share their wiring in one include,
`infinity6c-ssc377d-anjvision.dtsi`, and each has its own `.dts` with its model
string and lights, so a JL12D2 board change does not reach the YMF46D; the
MC-A85 and N803 have their own. All are decoded from the stock device trees.
The four camera profiles boot under the stock OEM U-Boot and flash layout, and
each has run on its hardware; the reference target is a CI build target, never
a flash target. On 2026-11-06, at an earlier base, all four camera profiles
were built from empty output directories and each image's `raptor.conf` matched
its `raptor.config` key by key. All five go upstream with the SigmaStar series.
What each camera gets is in section 2.1.

### 1.6 Not for upstream

- **A local timezone default.** The vendor overlay carries a fixed
  `/etc/timezone`: a local default, not an upstream candidate. `[0002]`
- **Eight RTSP clients** (`RAPTOR_RTSP_MAX_CLIENTS="8"`) on the four camera
  profiles, enough for Frigate plus viewers: profile values.
  `[0018, 0019, 0020, 0021]`
- **OEM sensor tunings.** The profiles reference the OEM tuning files
  (`gc8613.bin`, `gc4653.bin`, the N803's IMX415 tuning). They are vendor
  files, in no patch, and cannot be submitted; the JL12D2 uses the SDK's
  IMX335 tuning.
- **Firmware images.** None are published: this repository carries source
  and build instructions.
- **Tooling.** This port's flash, build and verify scripts are not in these
  patches. Two standalone tools ship in this repository:
  [onvifcheck](../tools/onvifcheck/README.md), an ONVIF conformance and
  client-compatibility checker, and
  [ipu-extract](../tools/ipu-extract/README.md), for ipud's model.

## 2. What the build adds on top of Thingino (SigmaStar line)

### 2.1 Cameras supported

The SoC, sensor and default streams of each are in the README's
[camera table](../README.md#cameras-this-brings-up). What each profile sets up:

| Camera | Highlights | Patch |
|---|---|---|
| MC-A85 (fixed 4K) | its own board DTS; the GC8613 on four lanes, its driver built from source; FlickerEx anti-flicker; luma day/night with the IR ladder; PWM-dimmed IR and white banks; the mic; the main stream at 2560x1440, scaled from the full 4K readout, which leaves far more video memory free than a 4K main (3840x2160 stays a choice) | 0018 |
| JL12D2 (PTZ) | autofocus; pan, tilt, zoom, presets and home over ONVIF and the web UI, with RelativeMove and AbsoluteMove zoom (head measured); IR-cut through the lens head; 128 MB DDR with the OEM's MMA heap; the sensor MIPI settings of the OEM device tree; microSD; native 4:3 streams | 0019 |
| YMF46D (bullet) | its own `.dts` on the shared include; orientation; the mic; IR and white lights; GPIO IR-cut; microSD automount; a 960x540 sub, because a 1280x720 sub wedges the encoder (its dynamic SRAM allocation fails) | 0020 |
| N803 (PTZ, 5x zoom) | its own board DTS; the Pelco-D head through `lensd -P` (pan, tilt, zoom and focus); 256 MB DDR; microSD on its SDIO port, with the slot's power pad; a 5-partition flash with its own env partition; the unit's MAC read from the overlay by `S04oemmac`, since the die-ID derivation fails on this SSC378QE, and none baked into the image | 0021 |
| reference | board-less; the CI default, never a flash target | 0006 |

### 2.2 Features, by area

- **Streaming:** upstream raptor, raptor-ipc, raptor-common and compy at
  Thingino's pins, with the 13 raptor patches of 1.2; only the HAL is forked
  (1.3). Eight RTSP clients per camera. `[0006, 0010 to 0012, 0018 to 0021]`
- **Day/night:** ric's luma trigger works with PWM-dimmed IR banks and its IR
  ladder dims the IR to the scene, on an `ae_luma` that matches ric's scale;
  the light tool drives IR and white banks with brightness; on the JL12D2,
  `lensd` drives the head's IR-cut filter over serial, following ric (day in
  colour, night mono plus IR). `[0005, 0010, 0015; raptor-hal 0008]`
- **PTZ and lens:** stock-equivalent autofocus, the zoom position read back,
  ONVIF PTZ that Frigate shows with arrows and zoom, RelativeMove and
  AbsoluteMove zoom for Frigate's autotracking, 31 named presets plus home,
  and a web UI joystick with speed by reach. `[0015, 0016]`
- **On-camera detection:** ipud on the IPU, with MQTT, ONVIF, Home Assistant
  and Frigate outputs and a live overlay, off until enabled, with no IPU
  firmware file. `[0003, 0022]`
- **Encoder and rate control:** JPEG rings sized for the largest frame; the
  SCL-to-VENC ring depth set per profile (JL12D2 a quarter frame, MC-A85 and
  N803 a half, YMF46D a whole frame); explicit VBR caps; sub rates that divide
  the main's; a video-memory check before a stream change; QP bounds, the I/P
  QP delta and a soft keyframe cap, replayed after every restart; opt-in
  encoder statistics.
  `[0002, 0012, 0018 to 0021; raptor-hal 0009, 0012, 0013]`
- **Image:** the tuning stays in charge at the web UI's default values (the
  knob map), FlickerEx anti-flicker, and an opt-in night shutter cap, off by
  default, that holds frame rate at the cost of gain.
  `[raptor-hal 0005, 0006, 0010]`
- **Honest controls:** the Image Quality page shows only what the HAL applies;
  no motion controls where the camera cannot detect motion (Frigate does it);
  the speaker locked where it is not wired; the OSD page offers a stream
  restart. `[0009, 0012]`
- **Interop:** Frigate's go2rtc always gets the parameter sets (no 4:3
  squish); ONVIF reports the real stream sizes and the zoom spaces in schema
  order (Frigate shows arrows); RTSP clients that stall on split replies
  connect. `[0008, 0011]`
- **Web UI:** never another device's cached config or footer (the cache policy
  and the uhttpd fix); after an update, the new scripts on the first load (the
  page stamp); Ch1 previews with the main's JPEG off; no dead day/night link;
  the Sensor IQ page on SigmaStar; no digital-zoom bar where `rvd` cannot
  zoom; the PTZ plugin; a bandwidth test.
  `[0007, 0009, 0011, 0014, 0016]`
- **Storage:** microSD as modules (SDIO, MMC block, exFAT) with mdev
  automount on the JL12D2, YMF46D and N803; the block-device automount on
  every board. `[0003, 0019, 0020, 0021]`
- **The stock flash layout:** the four cameras keep the OEM U-Boot, so a unit
  goes from stock to Thingino and back without opening it; `fw_setenv` writes a
  file and cannot erase the kernel; `thingino-update` updates and reverts in
  that layout, and `sysupgrade`'s full-image and env-reset modes are fenced
  there. `[0002, 0017]`
- **Fault recovery:** fault reports that outlive the kernel ring; a wedged
  encoder recovered by a raptor restart, then a reboot; an `rvd` the kernel
  killed for memory restarted; and on boards with little memory the web UI's
  helpers are capped and go before the video daemons when memory runs out.
  `[0007, 0013]`
- **Build checks:** every `DT_NEEDED` resolved, and `-dirty` stamps on images
  from uncommitted trees. `[0004, 0017]`

## 3. Still open

- **The N803 head.** Its speeds and field of view are not measured yet, so it
  offers no RelativeMove, and `lensd -P` does not read its zoom encoder yet,
  so no AbsoluteMove either. `[0015, 0021]`
- **16:9 on the JL12D2.** The Infinity6C backend scales the whole frame and
  cannot crop yet; this is raptor-hal work.
- **Speakers (MC-A85, YMF46D).** The speaker-enable GPIO is unmapped, and the
  control stays locked until it is mapped. `[0009, 0012]`
- **Settings that live only in `rvd`.** The command replay is an interim; a
  raptor change that keeps the encoder rate-control extras in `raptor.conf`
  would replace it. `[0002]`
- **ContinuousMove speed.** The ONVIF server passes its maximum step whatever
  the velocity, so ONVIF arrows run the head at its top Pelco-D level; one
  reading that disagrees is unresolved. `[0015]`
- **The digital zoom probe** has a host test only; it has not run on a
  camera. `[0009]`
- **CI.** The series adds a SigmaStar build workflow, but no run of it is on
  record. `[0004]`
- **OEM-layout updates.** Whether upstream wants `thingino-update`, or the
  fence on `sysupgrade`, is not known. `[0017]`
- **Building from the series alone.** The vendor packages, kernel, toolchain,
  sensor headers and the raptor-hal fork are fetched from local mirrors, so
  the patched tree cannot be built from this repository as it stands; see
  [patches/README.md](../patches/README.md#known-limits).
  [UPSTREAM-PLAN.md](UPSTREAM-PLAN.md) lists what has to be public first.
- **Upstream submission.** The vendor guards and the family file are merged;
  the rest of the platform, the raptor patches and the HAL backend are
  still to be sent. How they should land, and in what shape, is what this
  repository is published to discuss: the plan is in
  [UPSTREAM-PLAN.md](UPSTREAM-PLAN.md) and the questions are in the
  [README](../README.md#open-questions-for-the-discussion).

## 4. The generic series

[`patches/thingino-generic/`](../patches/thingino-generic/) holds work that does
not depend on the SigmaStar platform and is meant for upstream pull requests of
its own. It is published here so that it can be read before those are opened.
Its two patches apply on top of the 22 of the Thingino series, and every file
they change is Thingino's own (MIT). What an image needs to run them, how to
apply them to upstream for an Ingenic camera and what was tested are in
[DETECTION-GUIDE.md](DETECTION-GUIDE.md).

| # | Patch | Mainly for | Scope |
|---|---|---|---|
| G0001 | raptor agent: config reads without a process per field; detection settings | Thingino (the raptor agent adapter, `agent-lib`) | generic |
| G0002 | raptor: a detection settings page and a labelled preview overlay | Thingino (raptor's web UI) | generic; `thingino-ipud`'s overlay shares the drawing code |

### 4.1 The agent adapter `[G0001]`

The raptor agent adapter and `agent-lib` as the port's development tree runs
them.

- **Reads without a process per field.** `GET /config`, the stream blocks and
  the image block are printed through helpers that hand their result back in
  a variable, from sections read once and an ISP state parsed once. Printed
  field by field through command substitutions, one config read started
  about 390 processes; `agent-lib` also quotes a string that has nothing to
  escape without `awk`.
- **Detection settings**, for raptor's own detector (rvd's IVS):
  `settings/motion/algorithm`, `model`, `num-classes`, `conf-threshold` and
  `nms-threshold`, beside the sensitivity and cooldown settings the agent
  already had. rvd reads them at its start, so each answers that a stream
  restart applies it. `settings/motion/draw-boxes` switches the boxes rod
  draws into the sub stream, at once; `settings/motion/labels` gives the class
  names (a `<model>.txt` beside the model, else the public models' names).
- **Capabilities and the current detections.** The capabilities list the
  detection methods whose libraries the image has and the model files; the
  runtime read `detections` gives rvd's current boxes with the sub stream's
  size.

On the host the adapter's answers match ones saved from two Infinity6C
cameras, which have no IVS, and its detection answers pass a test against a
stand-in `raptorctl`.

### 4.2 The detection page and the preview overlay `[G0002]`

raptor's detection could be set in `raptor.conf` alone, and what it found
showed only as rod's unlabelled boxes in the sub stream.

- **Settings > Detection** (`config-detect.html`), installed with raptor's IVS
  build option: on and off, the method, sensitivity and cooldown, and for a
  model its file, class count, confidence and overlap. A save writes only
  what changed; when the camera stages a setting for a restart, the page
  offers it; with no model on the camera it says so.
- **A Detections button on the preview**: boxes with the class name and score
  over the picture, for the viewer alone. `json-detect.cgi` feeds it as one
  server-sent event stream, an event when the detections change and one every
  few seconds otherwise, at one `raptorctl` call a tick; no boxes are drawn
  over a player without a picture.
- **One overlay for both detectors.** `detect-overlay.js` draws for raptor's
  detector and for `thingino-ipud` (1.5.6), whose overlay was the same code:
  `preview-ipud.js` now only feeds it from its own event stream. Same button,
  same remembered choice.

*The overlay and its feed have run on an Ingenic T31 camera with detection on,
the boxes following at a median of 360 ms.* The page scripts pass a host test
of 46 checks. The two raptor patches that let rod's boxes reach the sub stream
at all are 0112 and 0113 `[0012]`.

### 4.3 What the generic series does not hold

Other generic work of this port is not in this repository: it goes upstream as
pull requests of its own, some of them open or merged already (the
[README](../README.md) lists them).
