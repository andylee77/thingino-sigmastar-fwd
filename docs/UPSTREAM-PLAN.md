# SigmaStar Infinity6C in Thingino: upstream plan

A working plan for landing the SigmaStar Infinity6C port in upstream Thingino
as a series of small, reviewable pull requests. It is a proposal: the order,
the names and the layout are open to change, and the questions at the end are
the ones that most need an answer from the maintainers.

Maintained by andylee77. The port builds on John Chia's SigmaStar work: the
vendor seams already in upstream are his, and so are the layer this series
re-cuts and the Infinity6C backend for raptor-hal.

Last updated 2026-11-17.

## Where things stand

| Piece | PR | State |
|---|---|---|
| The ISP choice is Ingenic's | [#2063](https://github.com/themactep/thingino-firmware/pull/2063) | merged |
| The vendor follows from the SoC model | [#2068](https://github.com/themactep/thingino-firmware/pull/2068) | merged |
| `lib-serial-mac` goes with the Ingenic files | [#2069](https://github.com/themactep/thingino-firmware/pull/2069) | merged |
| The JZ MAC select moves to the Ingenic block | [#2070](https://github.com/themactep/thingino-firmware/pull/2070) | merged |
| The JZ options are Ingenic's (follow-ups to #2070) | [#2082](https://github.com/themactep/thingino-firmware/pull/2082) | merged |
| The Infinity6C family (FW-1 below) | [#2083](https://github.com/themactep/thingino-firmware/pull/2083) | merged |

## What upstream already has

The vendor seams, from John Chia's PRs of August to October 2026:

| PR | What it gave |
|---|---|
| #1391, #1404, #1443 | a SigmaStar vendor and its model symbol, read by `thingino.mk` |
| #1397, #1398 | one Kconfig block per vendor (`Config.<vendor>.in`), and the HAL package owning the vendor selects |
| #1426 | one file per SoC family under `soc/<vendor>/` |
| #1427, #1428 | `ingenic-sdk` gated on its vendor; a file per vendor in `thingino-system` |
| #1442 | one kernel map per vendor, `kernels/<vendor>.mk` |

What it does not have: any SigmaStar family file, kernel map, board directory,
package or camera profile. His platform PR for Infinity6E (#1424) and the
bootloader-dispatch PR (#1392) were withdrawn.

## What the port is

Six Infinity6C parts (`ssc377`, `ssc377d`, `ssc377de`, `ssc377qe`, `ssc378de`,
`ssc378qe`), kernel 5.10, SigmaStar's MI 3.0 libraries, raptor as the
streamer through a raptor-hal backend. Profiles exist for five camera models
(the Jennov JL12D2, the YMF46D, the MC-A85, the Anpviz N803 and the TP-Link
Tapo C120) and for John Chia's reference board.

Grouped by what each part is:

| Group | Contents | Size |
|---|---|---|
| SoC family | `soc/sigmastar/infinity6c.mk`, the SoC fragment | about 30 lines |
| Toolchain | an ARM uClibc toolchain defconfig for CI, a README | about 200 |
| Vendor packages | `sigmastar-lib`, `sigmastar-sdk`, `sigmastar-sensor-headers`, `sigmastar-uboot` | about 1,000 |
| `thingino-system` | `Config.sigmastar.in`, `files/sigmastar/` (`soc`, `sensor`, `usb-role`, `S03mac`, `lib-serial-mac`) | about 400 |
| Kernel | `kernels/sigmastar.mk`, the 5.10 kernel config | about 3,000, nearly all config |
| Image | `board/sigmastar/post-image.sh`, a core fragment, the make arms that assemble the image | about 500 |
| HAL wiring | the SigmaStar backend symbol and its build block | about 40 |
| Profiles | one directory per camera, each with a board DTS patch | about 1,600 for six |
| Features | `sigmastar-light` (IR and white light banks), `thingino-lensd` (motorised lens and PTZ) | about 3,700 |
| raptor-hal | the Infinity6C backend and its MI headers | about 15,000 |

## The series

Each PR is small enough to review by itself, states what it was tested
against, and leaves every existing board unchanged.

### Stage 0: vendor guards (done)

Places in shared files that assumed Ingenic silicon whatever the vendor.
PRs #2063, #2068, #2069, #2070 and #2082 are merged.

### Stage 1: the HAL backend, in gtxaspec/raptor-hal

The long pole. It does not depend on the firmware PRs, and FW-7 and
everything after it wait for it.

| PR | Contents | Depends on |
|---|---|---|
| HAL-1 | the vendor seam with no backend: the vendor axis, the build hooks, the Infinity6C capability block | |
| HAL-2 | the MI ABI headers for Infinity6C | HAL-1 |
| HAL-3 | the backend, `src/infinity6c/`, as it runs today | HAL-1, HAL-2 |
| HAL-4 | options, one PR each: ring depth, the AE shutter cap, the encoder rate-control ops, encoder statistics | HAL-3 |
| RAP-1 | raptor: `libimp` and `libalog` linked on Ingenic only | |
| RAP-2 | raptor: day and night for PWM IR banks, start-up hooks, an environment file, ISP capability reporting | |

### Stage 2: the platform, in thingino-firmware

FW-1 to FW-6 can be reviewed while Stage 1 is in progress: none of them makes
a SigmaStar image, and none changes an Ingenic configuration.

| PR | Contents | Depends on |
|---|---|---|
| FW-1 | the family's facts: `soc/sigmastar/infinity6c.mk`, the six models, the SoC fragment ([#2083](https://github.com/themactep/thingino-firmware/pull/2083), merged) | |
| FW-2 | the ARM toolchain: a CI defconfig, the asset name in the toolchain workflows | |
| FW-3 | the vendor packages | FW-1 |
| FW-4 | `thingino-system`'s SigmaStar half | FW-3 |
| FW-5 | the kernel: `kernels/sigmastar.mk` and the 5.10 config | FW-1 |
| FW-6 | the image: the post-image script, the core fragment, the make arms | FW-3, FW-5 |
| FW-7 | the HAL wiring | HAL-3 merged and Thingino's raptor pins moved past it; RAP-1 |

### Stage 3: a first profile, then features and cameras

| PR | Contents | Depends on |
|---|---|---|
| FW-8 | the first camera profile | FW-1 to FW-7, and the toolchain on a public release |
| FW-9 | `sigmastar-light` | FW-4 |
| FW-10 | `thingino-lensd` | FW-8 |
| FW-11 | the cameras, one PR per model | FW-8, FW-9 |
| FW-12 | raptor's SigmaStar side: stream choices, a watchdog, the day and night keys | HAL-4, RAP-2 |

## How each PR is checked

- **Existing boards.** `make CAMERA=<profile> defconfig` for every profile in
  `configs/cameras`, `cameras-exp`, `cameras-testing` and `configs/github`
  (285 on 2026-11-17), on master and with the one branch applied, compared
  byte for byte. A PR that has to change a line says which, in every
  configuration.
- **The other vendor.** A SigmaStar configuration resolved on master and with
  the branch, to show the fault and its absence. Before FW-1 merged that
  configuration was a scratch one; since it, a three-line profile resolves
  for real.
- **Alternatives.** The other ways to write the change are tried, and the PR
  text says which were and why one was kept.
- Each PR text says what was not tested. Nothing is called built or run on a
  camera unless it was.

## What has to be public before a SigmaStar profile can build upstream

| Source | Where it is today | Plan |
|---|---|---|
| The raptor-hal backend | on the maintainer's machine; the public fork has only `main` | pushed as a branch of `andylee77/raptor-hal` for the HAL PRs |
| The kernel | `johnchia/linux` | keep, or mirror wherever upstream prefers |
| `sigmastar-lib`, `sigmastar-sdk` (SigmaStar's MI libraries and kernel modules) | `johnchia/sigmastar-lib`, `johnchia/sigmastar-sdk` | keep, or mirror under `andylee77`; upstream's call |
| Sensor headers, U-Boot | `OpenIPC/sensors`, `OpenIPC/u-boot-sigmastar` | keep |
| The ARM toolchain | an asset of `johnchia/thingino-firmware`'s toolchain release | built by upstream's toolchain workflow once FW-2 is in |
| Sensor tuning files of three cameras | taken from each camera's own firmware, not redistributed | those three profiles follow later, with an extraction step or without the file |

Upstream's CI builds every profile in `configs/cameras`, so no SigmaStar
profile goes there until it builds from public sources.

## Other vendors in flight

gtxaspec's `novatek-nt98529` branch adds a Novatek NA51055 family on the same
seams. Where it meets this series: it adds Novatek to the vendor choice
that PR #2068 removed (a model symbol and one derived vendor symbol replace
it); it
carries the `lib-serial-mac` move that #2069 merged; and both add lines to the
same places in `Config.soc.in`. It names its SoC fragment for the family
(`soc-na51055`), and FW-1 follows that with `soc-infinity6c`.

## Questions for the maintainers

For themactep:

1. Platform PRs with no profile first, as #1424 intended, or a profile in
   `cameras-exp` from the start?
2. Where should per-vendor image assembly live: a `board/<vendor>/vendor.mk`,
   or arms in `Makefile.utils` (#1392's question)?
3. How much of a vendor's core fragment should become Kconfig?
4. Where should the kernel, the two SigmaStar binary repositories and the ARM
   toolchain live, and should upstream's toolchain workflow build the ARM one?
5. Should `ssc30kq` and `infinity6e` stay in `Config.soc.in` with no family
   file behind them?
6. A SigmaStar camera that keeps its vendor bootloader cannot use `sysupgrade`
   as it is. Is a fence on it, or a separate updater, wanted upstream?

For gtxaspec:

1. The backend's path into raptor-hal: seam first, then headers, then the
   backend; or one PR?
2. The MI headers: vendored, or a submodule as `ingenic-headers` is?
3. HAL options as environment variables, or as `raptor.conf` keys?
4. Can the two raptor changes a second vendor needs (RAP-1, RAP-2) go ahead of
   the rest of the raptor queue?
5. Should the HAL report each ISP control's native range, so a backend need
   not map a 0 to 255 scale onto its own units?
