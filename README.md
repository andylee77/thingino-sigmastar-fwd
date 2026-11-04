# Thingino on SigmaStar Infinity6C — forward-port

A patch series and design notes that bring **SigmaStar Infinity6C** cameras up on
current [Thingino](https://github.com/themactep/thingino-firmware) master, plus
one Raptor HAL fork. Published to open the discussion with the Thingino
maintainers about what should come upstream and how to split it.

It is a **contribution bundle, not a build tree**: the patches apply onto
upstream `themactep/thingino-firmware`. Nothing here is a fork of Thingino — the
streamer, web UI and ONVIF are upstream and unmodified.

**Status.** Everything has run on hardware (five camera models, see below) but
nothing has been submitted upstream yet. This repository is the starting point
for that.

## Legend

- **`[UPSTREAM]`** — Thingino's code, `themactep/thingino-firmware` master and
  the packages it pulls (raptor, onvif, uhttpd). Runs **unmodified** unless noted.
- **`[THIS PORT]`** — what this forward-port adds or changes. The candidate
  material for upstreaming.
- **`[J. CHIA]`** — John Chia's SigmaStar Infinity6C HAL backend, carried verbatim
  inside the one fork (raptor-hal) and credited to him.

## The shape of it

```text
[UPSTREAM]   themactep/thingino-firmware  master  (f083382c1, 2026-10-23)
   │           + raptor / raptor-ipc / raptor-common / compy  — unmodified, at upstream pins
   │           + thingino web UI + its Raptor plugin           — unmodified
   │
[THIS PORT]  a curated 21-patch series on top, grouped by concern
   │           (consolidated from ~87 development commits; byte-identical result)
   │           • the SigmaStar platform, re-cut onto current master
   │           • a handful of generic fixes, intended for upstream
   │           • two new packages (thingino-lensd, thingino-nettest)
   │           • 5 camera profiles
   │
   └── one carried fork: thingino-raptor-hal
          [J. CHIA]    src/infinity6c backend + MI 2.x/3.0 ABI headers (verbatim)
          [THIS PORT]  bridge to the current HAL interface + 4 small ISP features
```

### Why this shape

John Chia wrote SigmaStar support on a `sigmastar-6b0-platform` branch that fell
762 commits behind master. Rather than keep chasing it, this port re-cuts the
platform onto current master and runs **upstream Raptor at Thingino's own pins**,
carrying
only the one fork that must hold vendor ISP code (`raptor-hal`). That buys the
upstream web UI and its Raptor plugin, drops the inherited Raptor delta from
~115k lines to ~11k, and puts the work back on Thingino's update path.

## Repository layout

```text
README.md                      this file — the overview and discussion starter
docs/
  WHAT-THIS-PORT-ADDS.md       exhaustive, per-patch breakdown (PR-split detail)
  raptor-hal-FORK.md           the one fork: what is John Chia's, what is new here
  oem-reference/               reverse-engineered OEM lens/PTZ and IR-cut protocols
patches/
  thingino-sigmastar/          21 patches onto themactep/thingino-firmware master
  raptor-hal/                  8 patches onto gtxaspec/raptor-hal
```

## Cameras this brings up

All five are **`[THIS PORT]`** profiles running on the **`[UPSTREAM]`** platform. They
boot under the **stock OEM U-Boot and flash layout**, so a unit flashes from stock
to Thingino and back without opening the case.

| Camera (OEM names) | SoC + sensor | Form factor | Streams |
|---|---|---|---|
| UVision MC-A85 / Anpviz IPC-D3B83B-S | SSC378DE + GC8613 | fixed 4K | 3840×2160 + 1280×720 H.264 |
| Jennov JL12D2 / UVision MCL12D2 | SSC377D + IMX335 | PTZ, 20× optical zoom | 2592×1944 + 1280×960 (native 4:3) |
| Anpviz IPC-B8A63WD-S / UVision MC-F46D | SSC377D + GC4653 | bullet | 2560×1440 + 640×360 (NVR sub) |
| N803 | SSC378QE + IMX415 | PTZ, 5× zoom | 3840×2160 + sub; Pelco-D pan/tilt/zoom/focus, limited autofocus |
| reference (John Chia's) | SSC377QE + IMX335 | — | board-less reference target |

Sensor tuning files (`gc8613.bin`, `gc4653.bin`) are proprietary OEM blobs —
not in this repository and not submittable.

## The one fork: thingino-raptor-hal

The rest of the Raptor stack is upstream and unmodified. The HAL is the exception
(full detail in [docs/raptor-hal-FORK.md](docs/raptor-hal-FORK.md)).

- **`[J. CHIA]`** `src/infinity6c/` backend and `sigmastar-headers/` (reconstructed
  MI 2.x / 3.0 ABI) — carried verbatim with provenance notes.
- **`[THIS PORT]`** a ~70-line **compat shim** bridging his backend (written against his
  own `raptor_hal.h`) to the *current* upstream HAL interface — it detects upstream
  by the absence of `RSS_ISP_AUTO` and republishes six ISP getters with upstream's
  `uint8_t *` signatures. Plus four small, self-contained ISP features: a 0..255
  knob scale map, `ae_luma` reported on the 0..255 scale, a FlickerEx anti-flicker
  lock, and an opt-in AE max-shutter cap.

**Upstreaming:** one series to land *with John Chia*, since most of it is his. The
shim disappears the day his backend targets the current interface.

## Fixes for upstream (added by this port)

None are SigmaStar-only in effect — each is a general bug or feature hit on
SigmaStar first. Grouped by project, ready to split into independent PRs. Full
list with rationale in [docs/WHAT-THIS-PORT-ADDS.md](docs/WHAT-THIS-PORT-ADDS.md).

- **OpenWrt uhttpd** — `If-None-Match` decides conditional requests when present
  (RFC 9110 §13.2.2); the date was tested first, so a browser reusing an IP got
  another device's cached files.
- **gtxaspec/raptor** — don't hard-code the Ingenic SDK libs in `LDFLAGS_HAL`
  (non-Ingenic HAL backends failed to link); ric `irled_cmd` hook + luma trigger +
  IR level ladder for PWM-dimmed IR banks; `/etc/raptor.d` start/stop hooks around
  the stack; rsd sends each RTSP reply in one piece (Happytime/NVR clients stalled);
  rsd answers DESCRIBE *with* SPS/PPS (no 4:3 squish in go2rtc/Frigate); plus the
  recent streaming/encoder and watchdog work.
- **themactep/thingino-onvif** — emit each zoom default space in schema order, or
  zeep (Frigate's parser) drops the pan/tilt spaces.
- **themactep/thingino-firmware** — don't default the ISP to Ingenic's stack on
  other vendors; really disable submodules when `_GIT_SUBMODULES = NO`; per-vendor
  `lib-serial-mac`; hide the day/night web link without `thingino-daynightd`.

## New package: thingino-lensd `[THIS PORT]`

For PTZ cameras built around a serial lens/PTZ board (the JL12D2 head; Pelco-D
boards generally).

- Stock-equivalent **autofocus** — feeds the board two ISP-derived focus values
  per frame.
- **ONVIF PTZ** (continuous pan/tilt/zoom, 31 presets + home) that Frigate renders
  with arrows *and* zoom.
- **Web UI PTZ plugin** — joystick with speed-by-reach, zoom/focus buttons, presets.
- Drives the JL12D2's **IR-cut filter over the same serial frame** (the filter is
  on the lens head, not a GPIO), following ric's day/night decision.
- **Pelco-D** mode (`lensd -P`) for the N803 head.

**Upstreaming:** the AF feed uses the MI ISP API (SigmaStar-specific); the PTZ /
ONVIF / web UI parts are protocol-level and would serve any Pelco-D board. These
may want to split along that line.

## Protocol references

The serial lens/PTZ and day/night behaviour was reverse-engineered from the OEM
firmware; these notes explain *why* lensd does what it does, and should help anyone
extending it:

- [JL12D2 PTZ/AF protocol](docs/oem-reference/JL12D2-PTZ-PROTOCOL.md) — the AF head's
  `51 01 04 78` frame, the 25 Hz focus-value feed, and the Pelco-D command set.
- [N803 lens protocol](docs/oem-reference/N803-LENS-PROTOCOL.md) — the manual-focus
  head is standard Pelco-D; its `51 01 04 78` return stream is *status*, not commands.
- [JL12D2 IR-cut mechanism](docs/oem-reference/JL12D2-IRCUT-MECHANISM-RE.md) — the
  filter is driven over the serial AF frame (byte 11), not a GPIO.
- [N803 pad / GPIO map](docs/oem-reference/N803-PAD-MAP.md) — board pinout for the
  N803 profile.

## Applying the patches

The patches are `git format-patch` output. Against a checkout of the matching
upstream trees:

```bash
# SigmaStar platform + camera profiles, onto thingino-firmware master
cd thingino-firmware
git am /path/to/patches/thingino-sigmastar/*.patch

# the HAL fork, onto gtxaspec/raptor-hal
cd raptor-hal
git am /path/to/patches/raptor-hal/*.patch
```

They are numbered in apply order. See
[docs/WHAT-THIS-PORT-ADDS.md](docs/WHAT-THIS-PORT-ADDS.md) for which patch does
what and which upstream project each belongs to.

## Intent and commitment to Thingino

This exists to feed Thingino, not to live as a permanent parallel fork. The
concrete commitments behind it:

- **Upstream-first.** The generic fixes (uhttpd, raptor, onvif, thingino) and the
  SigmaStar platform are prepared as PR-ready patches so they can land in the
  project, not only ship here. The HAL backend is credited to John Chia and
  intended to go upstream together with him.
- **Maintained to Thingino's standards, not left to drift.** The layer is kept as
  an additive overlay on `themactep/master` with a small, labelled core patch set,
  so it can track upstream by periodic merge and ride the project's Buildroot and
  kernel security pins on a timely cadence — a sustainable downstream rather than a
  one-off that rots.
- **CI build-tests over manual passes.** A SigmaStar build job plus per-camera
  image checks (partition fit, rootfs contents, `raptor.conf` semantics, and the
  compiled DTB's MIPI wiring) keep regressions out of the tree, so per-unit bench
  work stays limited to the irreducible sensor and optics bring-up.
- **Align with official SigmaStar support.** Thingino's tree already carries the
  vendor seams a SigmaStar port builds on (`BR2_SOC_VENDOR_SIGMASTAR`,
  `soc/<vendor>/`, the per-vendor raptor-hal symbol). If and as the project takes
  up first-class SigmaStar support, the aim is to contribute to it — patches, the
  reverse-engineering notes under `docs/`, and real test hardware across five
  models — and to reshape this layer into whatever form the maintainers prefer,
  rather than compete with it.

Scope is set honestly by capacity: a small owned fleet (five models) with one
person behind it. These are intentions and a best-effort cadence, not guarantees.

## Open questions for the discussion

1. **The HAL backend.** Best path to land John Chia's `src/infinity6c` + the
   bridge — one joint series? Or have his backend move to the current interface
   first (which retires the shim)?
2. **PR granularity.** Send the generic fixes (uhttpd, raptor, onvif, thingino) as
   small independent PRs regardless of the platform decision — does that suit?
3. **thingino-lensd split.** One package, or separate the MI-specific AF feed from
   the protocol-level Pelco-D / ONVIF / web UI layer?
4. **Per-family structure.** The tree keeps `soc/sigmastar/<family>.mk`,
   `raptor-hal/src/<family>/`, `sigmastar-headers/<family>/` so 6E/6B0 (and
   HiSilicon) slot in later. Does that match how other SigmaStar families should be
   organized?
5. **Still open** (not blockers): Frigate autotracking on the JL12D2,
   true 16:9 crop on the i6c backend, the unmapped speaker-enable GPIO on the
   MC-A85 / YMF46D.

## License and attribution

The patches modify MIT-licensed Thingino and MIT/BSD-style upstream code; this
repository is released under the [MIT License](LICENSE). The SigmaStar Infinity6C
HAL backend carried in `patches/raptor-hal/` is John Chia's work, included with
attribution; see [docs/raptor-hal-FORK.md](docs/raptor-hal-FORK.md). Vendor sensor
tuning blobs are proprietary and are not included.
