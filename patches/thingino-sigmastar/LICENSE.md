# Licenses of the Thingino patch series

These patches apply to [Thingino](https://github.com/themactep/thingino-firmware)
(MIT). Some of the files they add are themselves patches to other projects,
which Thingino's build applies to those projects' sources. Each part keeps the
license of the project it modifies, as Buildroot's own `COPYING` says of the
patches it carries. So the license of a hunk depends on the path it touches:

| Path inside a patch | Modifies | License |
|---|---|---|
| `package/thingino-raptor/*.patch` | [gtxaspec/raptor](https://github.com/gtxaspec/raptor) | GPL-3.0 ([text](../../LICENSES/GPL-3.0.txt)) |
| `package/thingino-onvif/*.patch` | [themactep/thingino-onvif](https://github.com/themactep/thingino-onvif) | GPL-3.0 (its `LICENSE`; Thingino's package file says MIT, the project says GPL-3.0) |
| `package/thingino-uhttpd/*.patch` | OpenWrt uhttpd | ISC |
| `board/sigmastar/*/patches/linux/*.patch` | the Linux kernel (device trees) | GPL-2.0 ([text](../../LICENSES/GPL-2.0.txt)) |
| `package/sigmastar-uboot/*.patch` | U-Boot | GPL-2.0-or-later |
| `package/sigmastar-sdk/*.patch`: the new `sensor_gc8613_mipi.c` | SigmaStar's sensor-driver tree in John Chia's `sigmastar-sdk` | GPL-2.0, for this new file. The tree it lands in is marked confidential by SigmaStar and has no license; this patch grants none for it, and carries none of its text |
| everything else: `Config.in`, `*.mk`, package files and scripts, `configs/`, `soc/`, `board/`, fragments, overlays, the web UI | Thingino | MIT ([`LICENSE`](../../LICENSE)) |

A file's own license statement wins over this table.
