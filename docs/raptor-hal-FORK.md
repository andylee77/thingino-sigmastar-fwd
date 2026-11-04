# raptor-hal, the SigmaStar HAL fork

Upstream [gtxaspec/raptor-hal](https://github.com/gtxaspec/raptor-hal) plus a
SigmaStar Infinity6C backend, for this forward-port of Thingino to SigmaStar. It
is on branch `sigmastar`. The forward-port it belongs to is summarized in the
[README](../README.md).

The rest of the Raptor stack (raptor, raptor-ipc, raptor-common, compy) runs
**unmodified upstream at upstream Thingino's pins**. This is the one fork carried
here.

## What is here, and where it came from

| Commit | Content | Source |
|---|---|---|
| base `8897102` | gtxaspec main, = upstream Thingino's `thingino-raptor-hal` pin | upstream |
| `sigmastar-headers: vendor …` | `sigmastar-headers/` — reconstructed MI 2.x and MI 3.0 ABI headers, plain directory (no submodule) | johnchia/sigmastar-headers `6fb6eec`, verbatim (see `sigmastar-headers/VENDORED.md`, `*/DERIVED.md`) |
| `infinity6c: import …` | `src/infinity6c/`, `src/hal_symbols.h`, `src/caps_sigmastar.inc`, `src/hal_internal_sigmastar.h`, `mk/sigmastar.mk`; `src/hal_internal_hisilicon.h` is a `#error` stub | johnchia/raptor-hal `672f8b3` (branch `sigmastar`), verbatim |
| `build: vendor hooks …` | `Makefile`, `src/hal_caps.c`, `src/hal_internal.h` (+87/−9) | John's hook diff, applied to upstream |
| `infinity6c: build against the upstream HAL interface` | the compat shim | this port |
| `infinity6c: anti-flicker via FlickerEx manual lock` | `MI_ISP_AE_SetFlickerEx` manual lock, deferred to the first frame | this port (MC-A85 / GC8613) |
| `infinity6c: map upstream raptor's 0..255 image knobs …` | the knob scale map + `tests/t_knob_map_i6c.c` | this port |
| `infinity6c: SCL->VENC ring depth from RSS_SCL_RING_DIV` | `i6c_pool_configure`: the SCL ring holds 1/N frame (4 = quarter, still the default; 2; 1) and logs the depth. A quarter frame let the scaler lap the main encoder on a YMF46D with a 720p sub (all-IDR main, sub at 13 fps); a half or whole frame fixed it | this port (YMF46D, 2026-11-01; patch 0007) |
| `infinity6c: report ae_luma on the 0..255 scale` | CUS3A's 10-bit `preAvgY` shifted to 8 bits, the scale ric's `night_luma` and upstream's exposure contract use. Passed through as-is, every ric luma comparison ran four times too bright | this port (MC-A85; patch 0006) |
| `infinity6c: opt-in AE max-shutter cap from RSS_AE_MAX_SHUTTER_US` | `i6c_isp_flush_ae_limit`: lowers the tuning's `maxShutterUs` through `MI_ISP_AE_Get/SetExposureLimit`, never below its minimum, applied from `i6c_isp_flush_knobs` (after the first frame and every tuning reload). Unset leaves the tuning's ceiling. On a YMF46D at night, 33333 µs held 25 fps (from ~20) at ~50 % more gain | this port (YMF46D, 2026-11-03; patch 0008; Buildroot option `BR2_PACKAGE_THINGINO_RAPTOR_AE_MAX_SHUTTER_US`, tree patch 0084) |

## How the upstream interface is bridged

John's backend was written against his own fork's `include/raptor_hal.h`, which
adds interface items upstream lacks. `src/infinity6c/i6c_upstream_compat.h`
detects upstream by the absence of `RSS_ISP_AUTO` and defines
`I6C_UPSTREAM_HAL_IFACE`. Under it:

- **Getter types:** six ISP getters are published with upstream's `uint8_t *`
  signature.
- **Dropped items:** the knob-caps op and the green WB gain are left out, and
  the sensor mode is forced to auto.
- **The knob scale map** translates raptor's 0..255 / 128-default scale to each
  module's native units (the header explains why and how).

If upstream ever defines `RSS_ISP_AUTO` itself, the shim switches off. Check
that the interfaces then agree before relying on it.

## Build and test

```bash
make PLATFORM=INFINITY6C SOC_MODEL=ssc378de \
     CROSS_COMPILE=<thingino host>/bin/arm-thingino-linux-uclibcgnueabihf-
cc -std=c11 -Wall -Wextra -Werror -Isrc/infinity6c -o /tmp/t_knob_map_i6c \
   tests/t_knob_map_i6c.c && /tmp/t_knob_map_i6c
```

The build needs only libc headers: MI is reached through `dlopen` at run time.
Last verified 2026-10-24 with GCC 16.2 uClibc: 0 warnings, 0 errors, and the
host test passes.

## Structure for more families

Everything is keyed by vendor and family, so 6E/6B0 (or HiSilicon) slot in
without restructuring:

- **Vendor fragment:** `mk/<vendor>.mk` (the Makefile `-include`s it).
- **One backend directory per family:** `src/infinity6c/` now; John's `src/star/`
  (MI 2.x: Infinity6E/6B0) when wanted. `mk/sigmastar.mk` already routes it.
- **Headers per family:** `sigmastar-headers/<family>/`, with `infinity6e/`
  already present.
- **Platform chain:** `src/hal_internal_<vendor>.h`, one link per vendor.

A `star` import needs its own compat pass, the same way `infinity6c` did.

## Maintenance

- **Bump upstream:** `git fetch upstream`, then
  `git rebase --onto <new pin> 8897102 sigmastar` (better, the pin upstream
  Thingino moves to). Conflicts, if any, are in the three hook files. Then
  rebuild, run the host test, and grep `include/raptor_hal.h` for new or changed
  ISP ops the shim must cover.
- **Refresh John's backend:** `git fetch johnchia` (a local mirror at
  `~/src/mirrors/git/johnchia__raptor-hal.git`). Then
  `git diff 672f8b3 <new> -- src/infinity6c mk/sigmastar.mk src/caps_sigmastar.inc src/hal_internal_sigmastar.h src/hal_symbols.h`,
  apply it, and rebuild: a new fork-only interface use shows up as a compile
  error.
- **Refresh the headers:** re-copy `sigmastar-headers/` from the mirror at a newer
  commit, keeping `VENDORED.md` current. Never edit in place.
- **Backup:** the mirror script (`docs/contrib/thingino/scripts/mirror-sigmastar-deps.sh`)
  bundles this repo with the mirrors, and with `BACKUP=<dir>` copies it to
  drive F.
