# An emulated camera as a test unit

A Thingino image for an Ingenic SoC boots unchanged under
[gtxaspec's QEMU fork](https://github.com/gtxaspec/qemu): SPL, U-Boot, Linux,
the web UI and the raptor streamer, with an emulated sensor that shows colour
bars. Upstream Thingino ships the harness for it, `scripts/qemu-dev`, with its
reference in `docs/dev/qemu.md` and test profiles in `configs/cameras-testing/`.
None of that is this port's work. These are notes from using it as a second
test unit beside real cameras: what it was good for, where it stops, and what
it took to run a detection model through the emulated T41's neural accelerator.

It is Ingenic only. The fork has no SigmaStar machine, so nothing of the
Infinity6C port runs in it. What it tests for this port is the code both
platforms share: the web UI, the CGIs, the agent, init, the generic part of
raptor.

## What was run on it

On images built from this port's development tree on 2026-11-18, with the
profiles `qemu_t31x_eth` (a T31X, gc2053 sensor) and `qemu_t41nq` (a T41NQ,
two cores, gc4023 sensor, the accelerator).

| Area | On the emulated camera | Still needs a camera |
|---|---|---|
| Boot, init scripts, services | SPL to a root shell in 40 to 47 s; `uhttpd`, `dropbear`, `ntpd`, `mdnsd`, the ONVIF notify server and the raptor daemons start as on a camera | boot timing, and anything a board's pins decide |
| Flash layout, overlay, reboot | the image's own partitions and jffs2 overlay; a saved setting survives `reboot`, a RAM bind mount does not | flashing, U-Boot on real flash, recovery |
| Web UI pages and scripts | pages load in a browser with the full menu and no console error | the live WebRTC preview, which never connects (see [Limits](#limits)) |
| Config CGIs and sessions | login, reads and saves through the CGIs; a validation defect found on a camera reproduced, and so did its fix | none found |
| The agent | the adapter answers through `agent.cgi` on the web UI's pages | adapter paths that read a vendor's hardware |
| raptor | 1920x1080 and 640x360 H.264 at 30 fps with AAC audio over RTSP, the OSD drawn, JPEG snapshots | image quality, encoder limits, memory budgets, speed |
| The T41 | a shell in 37 s on kernel 4.4.94 with both cores; the gc4023 at 2560x1440; RTSP main and sub, read at about 20 fps | as for the T31 |
| The T41's accelerator | a YOLOv5s runs end to end and matches the vendor's PC result, with a fix to the emulator that its release 0.7.26 carries (see [below](#a-model-on-the-emulated-t41s-accelerator)) | every speed number; the comparisons with a chip are other people's, not ours |

ONVIF, Wi-Fi and the setup portal, audio, GPIO, PWM and ADC are supported by
the harness and were not tried here.

## How it was started

In a Thingino tree, on Linux. The emulator needs `libslirp0` and
`libpixman-1-0` on the host; the harness fetches the QEMU release the tree
pins (about 11 MB) on first use.

```sh
make GROUP=testing CAMERA=qemu_t31x_eth WORKFLOW=1
scripts/qemu-dev up output/<branch>/qemu_t31x_eth-*/images/thingino-qemu_t31x_eth.bin \
    --name qemu_t31x_eth --fwd 554 -- -device image-sensor,model=gc2053,bus=i2c0
scripts/qemu-dev info
scripts/qemu-dev sh -- 'grep BUILD_ID /etc/os-release; raptorctl status'
scripts/qemu-dev down
```

- `up` returns at a root shell and prints the forwarded SSH and web ports,
  which are new on every start. Every `up` boots a fresh copy of the flash, so
  the camera starts as just flashed; `--keep` keeps the last session's flash
  instead, as a power cycle would.
- The sensor is named after `--` because the vendor ISP driver can oops
  without one. Use the sensor the profile was built for (`gc4023` for
  `qemu_t41nq`).
- `--fwd 554` forwards RTSP as well. `put` and `get` copy files.
- A build writes about 7 GB of output; the image itself is 16 MB.

## Trying a change

The same way as on a camera, so that the same commands and the same undo work
on both: put the file in `/tmp` and bind it over the image's copy.

```sh
scripts/qemu-dev put json-config-webui.cgi /tmp/test.cgi
scripts/qemu-dev sh -- 'chmod 755 /tmp/test.cgi; mount --bind /tmp/test.cgi /var/www/x/json-config-webui.cgi'
```

`reboot` undoes bind mounts and `/tmp`; `down` and `up` undo everything.
Pages and scripts under `/var/www/a` are stamped by the build, so take those
from a built `rootfs.squashfs`, not from the source tree. A change meant for
upstream is still checked on a real camera before it is offered; the emulated
one comes first, or stands in for the Ingenic camera of the pair.

## A model on the emulated T41's accelerator

The T41's accelerator (the NNA) is driven by Ingenic's Venus runtime through
the `soc-nna` kernel driver, which Thingino builds and loads on a T41. On
2026-11-18 a YOLOv5s ran end to end on the emulated T41 and found the same 19
people in the Magik kit's test frame as Ingenic's PC executor does for the
same model. Getting there took four things.

1. **A fix to the emulator.** At the fork's `330a3aaa21` (release 0.7.25) the
   NNA model gives this network's layers wrongly, and the kit's sample finds
   nothing. Two rules were off: the quantizing read-out is one bit short in
   the weight modes a converted YOLOv5 uses (`msf_mode` 0 and 2), and a tap
   mask with a gap, which a residual add sets, was read in the wrong order.
   The fork's [issue 18](https://github.com/gtxaspec/qemu/issues/18) reports
   the same symptom beside a real T41NQ, which gets it right. The fix is a
   17-line change to `hw/misc/ingenic-nna.c` with a test case, offered to the
   fork as [pull request 19](https://github.com/gtxaspec/qemu/pull/19). The
   fork's author checked it on a T41NQ and released it in `ingenic-0.7.26`,
   and the reporter of issue 18 then found their network byte-identical to
   their chip on that release. So use release 0.7.26 or later. Where the
   tree still pins an older one, name a newer build to the harness with
   `QEMU_BIN=<path to qemu-system-mipsel>`.
2. **Three boot settings**, written with `fw_setenv` on the emulated camera
   and followed by a reboot:
   - `mw 0xb2200060 0x02000400;` in front of `bootcmd`. It sets the L2
     cache's share of the on-chip SRAM to 128 KiB, where the driver's T41
     branch expects the accelerator's RAM. The image boots with the boot
     ROM's 256 KiB, and the runtime's first mapping then ends in a kernel bug
     check.
   - `nmem=32M@0xc000000` on the kernel command line: the runtime's memory.
   - `osmem` and `rmem` moved to make room (`128M@0x0`, `64M@0x8000000`).
3. **The runtime**: a T41 uclibc build of Venus 0.1.2.5 (`libvenus.so`,
   `libaip.so`, `libdrivers.so`) from Ingenic's Magik kit, in a folder under
   `/tmp` with `LD_LIBRARY_PATH` set to it, together with `libstdc++.so.6`
   and `libgcc_s.so.1` from the toolchain's sysroot. `libvenus.so` names the
   dynamic loader as a dependency, which the image's loader refuses;
   `patchelf --remove-needed ld-uClibc-mipsn8.so.0` removes it. Stop raptor
   first. The kit's `InferenceKit/nna2` libraries are an A1 build and stop in
   a bus error on a T41.
4. **A model from the kit's current converter.** One made with a 2022
   converter (model format 0.0.3) loads and gives nonsense; that was not
   followed further.

What the comparison showed, for the converted YOLOv5s against the PC
executor's per-layer dump of the same model and picture:

| | Release 0.7.25 | With the fix |
|---|---|---|
| Convolutions before the first add | correlation 0.945, then 0.07 | byte for byte |
| First residual add | wrong | 99.71 % equal, the rest one count off |
| All 83 layer outputs | wrong from the second on | lowest correlation 0.9946 |
| The three head tensors | wrong | correlation 0.9987 to 0.9995 |
| Boxes | none usable | 19, the PC executor's 19 |
| The kit's own T41 model and sample | no box | 19 boxes |

An inference takes 7 to 8 s in the emulator. That number says nothing about a
camera.

None of the vendor's files are in this repository: no runtime, no model, no
converter.

## Limits

- **Timing is not the hardware's.** The guest runs under TCG. By the fork's
  own measurements integer code runs 1.5 to 3 times faster than the chip,
  floating point 2 to 5 times slower, and code that misses the TLB 7 to 25
  times slower. A frame rate, a CPU load or an inference time measured here
  says nothing about a camera.
- **The picture is a test pattern**: colour bars with a white stripe that
  crosses every two seconds. The fork can feed a video file instead; not
  tried.
- **The WebRTC preview does not connect.** The page's offer is answered and
  the state then stays at "ICE: checking": the harness forwards single TCP
  ports, and the media path needs UDP to an address the browser cannot reach.
  The snapshot, the MJPEG CGIs and RTSP work.
- **Board hardware is not there.** Motors, IR-cut drivers, lights and buttons
  are GPIO levels and PWM traces that a test reads or drives.
- **A test profile is not a camera profile.** It boots with a root shell on
  the console and has a wired interface that some cameras lack.
- **The emulator moves fast**: several releases a day, and the tree's pin
  follows upstream. A result belongs to the release it ran on.

## What was not tested

- **No chip was at hand here for the accelerator.** Our reference is
  Ingenic's PC executor, which is the vendor's own model of the quantized
  network, not silicon. The comparisons with a T41NQ are the fork author's
  (the fix's test case and a sweep of both weight modes, on pull request 19)
  and the reporter's of issue 18 (a YOLOv5n, byte-identical on release
  0.7.26).
- **The emulated A1.** Its machine does not connect the accelerator to the
  CPUs, so the first accelerator instruction is an illegal instruction there.
- **Detection on the CPU** (JZDL, what
  [the detection guide](DETECTION-GUIDE.md) describes) was not run in the
  emulator.
- **raptor with the accelerator.** raptor's HAL has no backend for the Venus
  runtime; the runs above are the kit's sample and a small test program, not
  the streamer.
- **The automated suite** `scripts/qemu-test/run.sh` was not set up.
