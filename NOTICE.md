# Notice: licenses and credits

This repository holds patches and documentation for SigmaStar Infinity6C
support in [Thingino](https://github.com/themactep/thingino-firmware). Most of
it modifies other people's projects, and each patch keeps the license of the
project it modifies, so that each project can take its part without
relicensing anything. `LICENSE` (MIT) covers everything not assigned
elsewhere below.

## What is under which license

| Path | License | Why |
|---|---|---|
| `patches/thingino-sigmastar/` | per path inside each patch; see its [`LICENSE.md`](patches/thingino-sigmastar/LICENSE.md). Mostly MIT; the embedded raptor and ONVIF patches GPL-3.0; the kernel and sensor-driver patches GPL-2.0 | they patch Thingino (MIT), and through it raptor, thingino-onvif, uhttpd, Linux and U-Boot |
| `patches/raptor-hal/` | per file patched; see its [`LICENSE.md`](patches/raptor-hal/LICENSE.md). GPL-3.0-or-later for the Infinity6C backend, MIT where a file says MIT, otherwise GPL-3.0 | they patch gtxaspec/raptor-hal (GPL-3.0) |
| `docs/`, `tools/`, `README.md`, `NOTICE.md` | MIT (`LICENSE`) | written for this repository |
| `LICENSES/` | the license texts themselves | GPL-2.0 and GPL-3.0, for the patches above |

Each source file's own license statement wins over this table.

## Credits

This port stands on other people's work:

- **John Chia** ([johnchia](https://github.com/johnchia)) wrote SigmaStar
  support for Thingino: the vendor seams upstream carries, the SigmaStar
  packages (`sigmastar-sdk`, `sigmastar-lib`, `sigmastar-uboot`), the
  Infinity6C kernel and SoC layer, the Raptor HAL backend for Infinity6C
  (`src/infinity6c/`, GPL-3.0-or-later), the reconstructed MI ABI headers
  (`sigmastar-headers`), the kernel fork and the toolchain this port builds
  with. His backend and headers are carried verbatim and credited in the
  raptor-hal series. Most of what makes these cameras work is his.
- **Paul Philippov** ([themactep](https://github.com/themactep)) and the
  Thingino contributors: [Thingino](https://github.com/themactep/thingino-firmware)
  itself (MIT), its web UI, agent and packaging.
- **gtxaspec** ([gtxaspec](https://github.com/gtxaspec)): the
  [Raptor](https://github.com/gtxaspec/raptor) streamer and its libraries
  (raptor-hal, raptor-common, raptor-ipc: GPL-3.0; compy: MIT), and much of
  Thingino.
- **OpenIPC**: [divinus](https://github.com/OpenIPC/divinus) (MIT, Copyright
  (c) 2024 OpenIPC), whose SigmaStar MI header layouts the reconstructed
  headers vendor and keep the notice of; the
  [OpenIPC Linux](https://github.com/OpenIPC/linux) tree the kernel fork is
  based on (GPL-2.0); and the sensor-driver collection the SDK's drivers come
  from. Two headers that the `thingino-ipud` package adds in
  `patches/thingino-sigmastar/` follow divinus's layouts as well, and say so
  in their comments: `mi_ipu.h` (from divinus's `src/hal/star/i6c_ipu.h`) and
  `mi_scl_sys.h` (through the reconstructed headers). For those two, this is
  divinus's notice: Copyright (c) 2024 OpenIPC, under the MIT permission
  notice that `LICENSE` carries.
- **Buildroot** (GPL-2.0-or-later), which Thingino is built on, and the
  authors of every package in the images.

## Not in this repository

- **SigmaStar's MI libraries, kernel modules, encoder firmware and ISP files**
  are proprietary and come with no license. The build fetches them from John
  Chia's `sigmastar-lib` and `sigmastar-sdk` repositories; this repository does
  not carry them. Two of those libraries contain code under permissive
  third-party notices (Takuya Ooura's FFT; the WebRTC project, BSD-3-Clause),
  which ship beside them in `sigmastar-lib`.
- **SigmaStar's sensor-driver sources and their framework headers** are
  marked confidential by SigmaStar and carry no license from this repository.
  The build fetches the headers from `openipc/sensors` at a pinned commit; no
  patch here carries them. The GC8613 driver added by one patch is new code
  under GPL-2.0; it was written against SigmaStar's sensor framework and
  started from one of its drivers.
- **OEM sensor tunings** (the per-sensor `.bin` files) are the camera vendors'
  and are never included.
- **The detection model** that `thingino-ipud` runs is a camera vendor's,
  comes with no license to redistribute it, and is never included.
  `tools/ipu-extract/` takes it out of firmware the user already has.
