# Thingino on SigmaStar Infinity6C — forward-port

A patch series and design notes that bring **SigmaStar Infinity6C** cameras up on
current [Thingino](https://github.com/themactep/thingino-firmware) master, plus
one Raptor HAL fork. Published to open the discussion with the Thingino
maintainers about what should come upstream and how to split it.

It is a **contribution bundle, not a build tree**: the patches apply onto
upstream `themactep/thingino-firmware`. The streamer, web UI and ONVIF server
stay upstream's, at Thingino's own pins; what this port changes in them is a set
of small patches, listed below.

**Status.** Each of the four camera profiles below has run on its hardware.
Nothing from these two patch series has been submitted upstream yet; this
repository is the starting point for that. Generic fixes found along the way
went to the upstream projects separately, as pull requests opened on
2026-11-11: themactep/thingino-firmware
[#1990](https://github.com/themactep/thingino-firmware/pull/1990) to
[#1997](https://github.com/themactep/thingino-firmware/pull/1997),
themactep/thingino-onvif
[#11](https://github.com/themactep/thingino-onvif/pull/11) and
thingino/ingenic-sdk [#13](https://github.com/thingino/ingenic-sdk/pull/13).

## Legend

- **`[UPSTREAM]`** — Thingino's code, `themactep/thingino-firmware` master and
  the packages it pulls (raptor, onvif, uhttpd). Runs **unmodified** unless noted.
- **`[THIS PORT]`** — what this forward-port adds or changes. The candidate
  material for upstreaming.
- **`[J. CHIA]`** — John Chia's SigmaStar Infinity6C HAL backend, carried verbatim
  inside the one fork (raptor-hal) and credited to him.

## The shape of it

```text
[UPSTREAM]   themactep/thingino-firmware  master  (b9b040f33, 2026-11-11)
   │           + raptor / raptor-ipc / raptor-common / compy  — at upstream pins
   │             (raptor with the package patches listed below)
   │           + thingino web UI + its Raptor plugin           — upstream's
   │
[THIS PORT]  a curated 22-patch series on top, grouped by concern
   │           (regrouped from the development history; byte-identical result)
   │           • the SigmaStar platform, re-cut onto current master
   │           • a handful of generic fixes, intended for upstream
   │           • three new packages (thingino-lensd, thingino-nettest, thingino-ipud)
   │           • 5 camera profiles
   │
   └── one carried fork: thingino-raptor-hal  (onto gtxaspec 9f09664, 2026-10-31)
          [J. CHIA]    src/infinity6c backend + MI 2.x/3.0 ABI headers (verbatim)
          [THIS PORT]  bridge to the current HAL interface + ISP and encoder features
```

### Why this shape

John Chia wrote SigmaStar support on a `sigmastar-6b0-platform` branch that fell
762 commits behind master. Rather than keep chasing it, this port re-cuts the
platform onto current master and runs **upstream Raptor at Thingino's own pins**,
carrying only the one fork that must hold vendor ISP code (`raptor-hal`). That
buys the upstream web UI and its Raptor plugin, drops the inherited Raptor delta
from ~115k lines to ~11k, and puts the work back on Thingino's update path.

## Repository layout

```text
README.md                      this file — the overview and discussion starter
LICENSE, NOTICE.md, LICENSES/  which license covers which part, and the credits
docs/
  WHAT-THIS-PORT-ADDS.md       exhaustive, per-patch breakdown (PR-split detail)
  raptor-hal-FORK.md           the one fork: what is John Chia's, what is new here
  oem-reference/               reverse-engineered OEM lens/PTZ and IR-cut protocols
patches/
  thingino-sigmastar/          22 patches onto themactep/thingino-firmware master
  raptor-hal/                  13 patches onto gtxaspec/raptor-hal
tools/
  onvifcheck/                  an ONVIF conformance and client-compatibility checker
  ipu-extract/                 takes ipud's model out of your own firmware
```

## Cameras this brings up

All five are **`[THIS PORT]`** profiles on top of the **`[UPSTREAM]`** tree. The
four camera profiles boot under the **stock OEM U-Boot and flash layout**, so a
unit flashes from stock to Thingino and back without opening the case.

| Camera (OEM names) | SoC + sensor | Form factor | Streams |
|---|---|---|---|
| UVision MC-A85 / Anpviz IPC-D3B83B-S | SSC378DE + GC8613 | fixed 4K | 2560×1440 + 1280×720 H.264, scaled from the full 4K readout (3840×2160 selectable) |
| Jennov JL12D2 / UVision MCL12D2 | SSC377D + IMX335 | PTZ, ~13.5× optical (sold as 20×) | 2592×1944 + 1280×960 (native 4:3) |
| Anpviz IPC-B8A63WD-S / UVision MC-F46D | SSC377D + GC4653 | bullet | 2560×1440 + 960×540 (sub) |
| N803 | SSC378QE + IMX415 | PTZ, 5× zoom | 3840×2160 + 1280×720; Pelco-D pan/tilt/zoom/focus |
| reference (John Chia's) | SSC377QE + IMX335 | — | board-less reference target |

Sensor tuning files (`gc8613.bin`, `gc4653.bin`, the N803's IMX415 tuning) are
proprietary OEM blobs: not in this repository and not submittable.

## The one fork: thingino-raptor-hal

The rest of the Raptor stack is upstream's. The HAL is the exception (full
detail in [docs/raptor-hal-FORK.md](docs/raptor-hal-FORK.md)).

- **`[J. CHIA]`** `src/infinity6c/` backend and `sigmastar-headers/` (reconstructed
  MI 2.x / 3.0 ABI), carried verbatim with provenance notes. The first two
  patches of the series vendor them, so the series applies to a bare
  `gtxaspec/raptor-hal` checkout.
- **`[THIS PORT]`** a ~70-line **compat shim** bridging his backend (written against his
  own `raptor_hal.h`) to the *current* upstream HAL interface: it detects upstream
  by the absence of `RSS_ISP_AUTO` and republishes six ISP getters with upstream's
  `uint8_t *` signatures.
- **`[THIS PORT]`** small, self-contained features on top:
  - ISP: a 0..255 knob scale map, `ae_luma` reported on the 0..255 scale, a
    FlickerEx anti-flicker lock, and an opt-in AE max-shutter cap;
  - encoder: the SCL→VENC ring depth set per profile (`RSS_SCL_RING_DIV`),
    rate-control extras (QP bounds, per-frame and fixed QP, the I/P QP delta,
    the maximum picture size and super frames), and opt-in encoder statistics.

**Upstreaming:** one series for `gtxaspec/raptor-hal`, with John Chia's work
credited to him, since most of it is his. The compat shim goes away if the
backend moves to the current interface.

## Fixes for upstream (added by this port)

None are SigmaStar-only in effect — each is a general bug or feature hit on
SigmaStar first. Grouped by project, so each can go upstream as an independent
PR. Full list with rationale in [docs/WHAT-THIS-PORT-ADDS.md](docs/WHAT-THIS-PORT-ADDS.md).

- **OpenWrt uhttpd** — `If-None-Match` decides conditional requests when present
  (RFC 9110 §13.2.2); the date was tested first, so a browser reusing an IP got
  another device's cached files.
- **gtxaspec/raptor** — don't hard-code the Ingenic SDK libs in `LDFLAGS_HAL`
  (non-Ingenic HAL backends failed to link); ric `irled_cmd` hook + luma trigger +
  IR level ladder for PWM-dimmed IR banks, with exposure polled on a fixed
  cadence; `/etc/raptor.d` start/stop hooks around the stack; rsd sends each RTSP
  reply in one piece (Happytime/NVR clients stalled); rsd answers DESCRIBE *with*
  SPS/PPS (no 4:3 squish in go2rtc/Frigate); JPEG rings sized for the largest
  JPEG, not the average; `/etc/default/raptor` exported to the daemons;
  `get-isp-caps` reports which ISP controls the HAL has.
- **themactep/thingino-onvif** — emit each zoom default space in schema order, or
  zeep (Frigate's parser) drops the pan/tilt spaces.
- **themactep/thingino-firmware** — don't default the ISP to Ingenic's stack on
  other vendors; really disable submodules when `_GIT_SUBMODULES = NO`; per-vendor
  `lib-serial-mac`; hide the day/night web link without `thingino-daynightd`;
  keep the digital zoom bar off where the streamer cannot zoom.

## New package: thingino-lensd `[THIS PORT]`

For PTZ cameras built around a serial lens/PTZ board (the JL12D2 head; Pelco-D
boards generally).

- Stock-equivalent **autofocus** — feeds the board two ISP-derived focus values
  per frame.
- **ONVIF PTZ** (continuous pan/tilt/zoom, 31 presets + home) that Frigate renders
  with arrows *and* zoom.
- **ONVIF RelativeMove**, which Frigate's autotracking needs: a timed pan and
  tilt move from the head's measured speeds, scaled by the field of view, with a
  move status that cannot stick. The JL12D2 head is measured; a head without
  measurements gets no RelativeMove.
- **ONVIF zoom for autotracking:** AbsoluteMove moves the zoom to a position
  read back from the board (pan and tilt are ignored: the head reports no
  position), and a RelativeMove's zoom term runs after the pan and tilt, one
  zoom-in narrowing the view at most 1.5x. A preset recall holds the move
  status as long as the way back takes. A head without zoom measurements
  offers no AbsoluteMove.
- **Web UI PTZ plugin** — joystick with speed-by-reach, zoom/focus buttons, presets.
- Drives the JL12D2's **IR-cut filter over the same serial frame** (the filter is
  on the lens head, not a GPIO), following ric's day/night decision.
- **Pelco-D** mode (`lensd -P`) for the N803 head.
- One package for every board: a build option picks the mode (off, AF head or
  Pelco-D) and the head; with it off, nothing PTZ-related is installed.

**Upstreaming:** the AF feed uses the MI ISP API (SigmaStar-specific); the PTZ /
ONVIF / web UI parts are protocol-level and would serve any Pelco-D board. These
may want to split along that line.

## New package: thingino-ipud `[THIS PORT]`

On-camera object detection on the Infinity6C IPU, the SoC's neural-network unit.
ipud runs a compiled YOLOv5 model on frames from an SCL output port the streamer
leaves unused, and reports the boxes to a status file (a web UI page and a
preview overlay), a local socket and MQTT. Each off until enabled, it also
raises ONVIF object events, Home Assistant entities and Frigate events for the
classes it reports. Every SigmaStar board ships it, off until enabled. The model is a vendor file and is not
included: ipud reads the model from the image when its build staged one, from a
folder on the SD card, or from a custom path.
[tools/ipu-extract/](tools/ipu-extract/README.md) takes it out of firmware you
already have, for a build or the SD card. No IPU firmware is needed.

**Upstreaming:** it uses the MI IPU and SCL APIs, so it belongs with the
SigmaStar platform.

## Protocol references

The serial lens/PTZ and day/night behaviour was reverse-engineered from the OEM
firmware; these notes explain *why* lensd does what it does, and should help anyone
extending it:

- [JL12D2 PTZ/AF protocol](docs/oem-reference/JL12D2-PTZ-PROTOCOL.md) — the AF head's
  `51 01 04 78` frame, a focus-value feed of one frame per sensor frame, and the
  Pelco-D command set.
- [N803 lens protocol](docs/oem-reference/N803-LENS-PROTOCOL.md) — the N803 head
  is standard Pelco-D; its `51 01 04 78` return stream is *status*, not commands.
- [JL12D2 IR-cut mechanism](docs/oem-reference/JL12D2-IRCUT-MECHANISM-RE.md) — the
  filter is driven over the serial AF frame (byte 11), not a GPIO.
- [N803 pad / GPIO map](docs/oem-reference/N803-PAD-MAP.md) — board pinout for the
  N803 profile.

## Applying the patches

The patches are `git format-patch` output, numbered in apply order. Against
checkouts of the two upstream trees at the commits the series were cut on:

```sh
# SigmaStar platform + camera profiles, onto thingino-firmware master
cd thingino-firmware
git checkout b9b040f33
git am /path/to/patches/thingino-sigmastar/*.patch

# the HAL fork, onto gtxaspec/raptor-hal
cd raptor-hal
git checkout 9f09664
git am /path/to/patches/raptor-hal/*.patch
```

The series fetches the SigmaStar vendor packages, kernel, toolchain and the
raptor-hal fork from local mirrors, so building the patched tree needs those
sources set up first; [patches/README.md](patches/README.md) has the details. See
[docs/WHAT-THIS-PORT-ADDS.md](docs/WHAT-THIS-PORT-ADDS.md) for which patch does
what and which upstream project each belongs to.

## Intent and commitment to Thingino

This exists to feed Thingino, not to live as a permanent parallel fork. The
concrete commitments behind it:

- **Upstream-first.** The generic fixes (uhttpd, raptor, onvif, thingino) and the
  SigmaStar platform are prepared as separate patches so they can land in the
  project, not only ship here. The HAL backend is credited to John Chia and is
  meant for `gtxaspec/raptor-hal` with that credit.
- **Maintained to Thingino's standards, not left to drift.** The layer is kept as
  an additive overlay on `themactep/master` with a small, labelled core patch set,
  so it can track upstream by periodic merge and ride the project's Buildroot and
  kernel security pins on a timely cadence — a sustainable downstream rather than a
  one-off that rots.
- **Scripted checks over manual passes.** Every camera image is checked by
  script before it is staged for a unit (partition fit, rootfs contents,
  `raptor.conf` against the profile's settings, the compiled device tree), and an
  upstream merge lands only after each of the four camera profiles builds and
  passes them.
  The series also carries a SigmaStar build workflow for CI. Per-unit bench work
  stays limited to the irreducible sensor and optics bring-up.
- **Align with official SigmaStar support.** Thingino's tree already carries the
  vendor seams a SigmaStar port builds on (`BR2_SOC_VENDOR_SIGMASTAR`,
  `soc/<vendor>/`, the per-vendor raptor-hal symbol). If and as the project takes
  up first-class SigmaStar support, the aim is to contribute to it — patches, the
  reverse-engineering notes under `docs/`, and test hardware for each of the four
  camera profiles — and to reshape this layer into whatever form the maintainers prefer,
  rather than compete with it.

Scope is set honestly by capacity: a small test fleet with one person behind it.
These are intentions and a best-effort cadence, not guarantees.

## Open questions for the discussion

1. **The HAL backend.** The plan is one series to `gtxaspec/raptor-hal`: John
   Chia's `src/infinity6c`, credited to him, plus the bridge. Should the HAL
   interface gain an op that reports each ISP knob's native range, so the backend
   works in native units and the 0..255 shim retires? Or should the backend land
   with the shim?
2. **PR granularity.** Send the generic fixes (uhttpd, raptor, onvif, thingino) as
   small independent PRs regardless of the platform decision — does that suit?
3. **thingino-lensd split.** One package, or separate the MI-specific AF feed from
   the protocol-level Pelco-D / ONVIF / web UI layer?
4. **Per-family structure.** The tree keeps `soc/sigmastar/<family>.mk`,
   `raptor-hal/src/<family>/`, `sigmastar-headers/<family>/` so 6E/6B0 (and
   HiSilicon) slot in later. Does that match how other SigmaStar families should be
   organized?
5. **Still open** (not blockers): a true 16:9 crop on the i6c backend; speaker
   output, since the HAL has no audio-out ops and the speaker-enable GPIO is
   unmapped on the MC-A85 / YMF46D.

## License and attribution

Each patch keeps the license of the project it modifies, so every project can
take its part without relicensing anything; [NOTICE.md](NOTICE.md) maps each
path to its license, and each patch directory has its own `LICENSE.md`. The
Thingino series is mostly MIT, with GPL-3.0 for the raptor and ONVIF patches it
carries and GPL-2.0 for the kernel and sensor-driver patches. The raptor-hal
series follows the files it patches: GPL-3.0-or-later for the Infinity6C
backend, MIT where a file says MIT, otherwise GPL-3.0. The docs and this README
are under the [MIT License](LICENSE); the GPL texts are in `LICENSES/`.

The SigmaStar Infinity6C HAL backend and the reconstructed MI headers carried in
`patches/raptor-hal/` are John Chia's work, included with attribution; see
[docs/raptor-hal-FORK.md](docs/raptor-hal-FORK.md) and the credits in
[NOTICE.md](NOTICE.md). SigmaStar's MI libraries and sensor-framework headers
(the build fetches them) and the vendors' sensor tuning blobs are not included.
