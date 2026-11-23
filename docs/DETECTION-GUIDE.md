# Detection: what the patches add and how to run them

This repository carries two different on-camera detectors, one per SoC vendor,
behind one web UI overlay:

| | Ingenic cameras (T31, T41 and the like) | SigmaStar Infinity6C cameras |
|---|---|---|
| Detector | raptor's own: the IVS detection in `rvd`, upstream in Thingino | `thingino-ipud`, on the SoC's IPU |
| Where it is | upstream's build option; this repository adds the settings page, the preview overlay and the agent's settings for it | patch 0022 of `patches/thingino-sigmastar/` |
| Model | public models from the `magik-models` package | a file from the camera's own firmware, taken out with [tools/ipu-extract](../tools/ipu-extract/README.md) |
| Runs on | the CPU, through Ingenic's JZDL engine, on the SoCs without an accelerator (T20, T21, T23, T31); on the T41, the NNA, through Ingenic's Uranus runtime and a raptor-hal backend offered upstream, since JZDL does not run there (see [the Wyze Cam v4](#the-wyze-cam-v4-and-its-accelerator)) | the IPU, the SoC's neural-network unit |

The rest of this page is about the first column: what an upstream Thingino
build for an Ingenic camera needs to run the detection patches. The Wyze Cam v4
(Ingenic T41NQ) is the worked example. For `thingino-ipud` see the
[README](../README.md#new-package-thingino-ipud-this-port) and
[WHAT-THIS-PORT-ADDS.md](WHAT-THIS-PORT-ADDS.md).

## What is upstream already, and what these patches add

Upstream Thingino has the detector. Its build option is off by default and no
camera profile turns it on, it has no settings page, and what it finds shows
only as unlabelled boxes that `rod` draws into the sub stream.

| Piece | Where |
|---|---|
| Detection in `rvd` (YOLOv5 through JZDL, or the vendor's person detector) | upstream: `BR2_PACKAGE_THINGINO_RAPTOR_IVS_DETECT` |
| Two `rvd` fixes without which no box reaches the sub stream (the OSD pool is sized for the overlay; a full-frame region is placed at the frame's corner) | raptor patches 0112 and 0113, in patch 0012 of [`patches/thingino-sigmastar/`](../patches/thingino-sigmastar/) |
| The agent's detection settings, capabilities and the read of the current detections | patch 0001 of [`patches/thingino-generic/`](../patches/thingino-generic/README.md) |
| Settings > Detection, the Detections button on the preview with labelled boxes, and its event feed | patch 0002 of `patches/thingino-generic/` |

## What the image needs

Everything comes from packages upstream already has. Nothing is taken from a
camera's stock firmware.

| Build option | What it brings | Size, as the option's help states it |
|---|---|---|
| `BR2_PACKAGE_THINGINO_RAPTOR_IVS_DETECT` | detection in `rvd`; with this series also the Detection page, the overlay and the feed | |
| `BR2_PACKAGE_THINGINO_RAPTOR_IVS_JZDL` (on by default under the first) | Ingenic's JZDL inference engine, `libjzdl.m.so`, from `ingenic-lib` | 609 KB |
| `BR2_PACKAGE_THINGINO_RAPTOR_IVS_YOLOV5` (on by default) | `/usr/share/models/magik_model_yolov5.bin` from the `magik-models` package ([gtxaspec/magik_models](https://github.com/gtxaspec/magik_models)): four classes, person, bicycle, car, motorcycle | 870 KB |
| `BR2_PACKAGE_THINGINO_RAPTOR_IVS_PERSONDET` (off by default) | the vendor's person detector, `libpersonDet_inf.so` with four MXU libraries; it needs no model file | about 3.2 MB |

`magik-models` can also install a person model and a face model
(`BR2_PACKAGE_MAGIK_MODELS_PERSONDET`, `BR2_PACKAGE_MAGIK_MODELS_FACEDET`).

Turning the first option on in a Wyze Cam v4 profile resolves to this, and
nothing else changes in the generated configuration:

```text
BR2_THINGINO_LIBSTDCPP=y
BR2_PACKAGE_INGENIC_LIB_JZDL=y
BR2_PACKAGE_MAGIK_MODELS=y
BR2_PACKAGE_MAGIK_MODELS_YOLOV5=y
BR2_PACKAGE_THINGINO_RAPTOR_IVS_DETECT=y
BR2_PACKAGE_THINGINO_RAPTOR_IVS_JZDL=y
BR2_PACKAGE_THINGINO_RAPTOR_IVS_YOLOV5=y
```

That is the JZDL path, which runs on a T31-class SoC. On a T41 it builds but
does not run; [the Wyze Cam v4](#the-wyze-cam-v4-and-its-accelerator) says why
and what runs there instead.

## Applying the patches to upstream, for an Ingenic camera

The generic series is cut on top of the Thingino series, so both go on, in
this order. The detection pages need the agent adapter of the first series,
and the boxes need its two `rvd` fixes.

```sh
cd thingino-firmware
git checkout b8bcd6740
git am /path/to/patches/thingino-sigmastar/*.patch
git am /path/to/patches/thingino-generic/*.patch
```

Then turn detection on for the camera's profile, by adding the line to its
defconfig or in `menuconfig` under the raptor package, and build the profile
as usual:

```text
BR2_PACKAGE_THINGINO_RAPTOR_IVS_DETECT=y
```

The Wyze Cam v4 has two profiles upstream, both in `configs/cameras-exp/`:
`wyze_cam4_t41nq_gc4653_atbm6062s` and `wyze_cam4_t41nq_os04d10_atbm6062s`.

### What the first series changes for an Ingenic build

Its SigmaStar packages are hidden for other vendors (each depends on the
SigmaStar vendor symbol), so none is built. Checked by generating both Wyze
Cam v4 configurations on upstream and with both series applied: no existing
line changes, and the only additions are new options that are off or empty:

```text
# BR2_PACKAGE_THINGINO_NETTEST is not set
BR2_PACKAGE_THINGINO_RAPTOR_UI_STREAM0_RESOLUTIONS=""
BR2_PACKAGE_THINGINO_RAPTOR_UI_STREAM1_RESOLUTIONS=""
BR2_PACKAGE_THINGINO_RAPTOR_UI_FPS=""
BR2_PACKAGE_THINGINO_RAPTOR_UI_STREAM0_BITRATES=""
BR2_PACKAGE_THINGINO_RAPTOR_UI_STREAM1_BITRATES=""
BR2_PACKAGE_THINGINO_RAPTOR_UI_CODECS=""
BR2_PACKAGE_THINGINO_RAPTOR_UI_PROFILES=""
BR2_PACKAGE_THINGINO_RAPTOR_UI_RC_MODES=""
BR2_PACKAGE_THINGINO_RAPTOR_UI_GOP_SECONDS=""
BR2_PACKAGE_THINGINO_RAPTOR_UI_JPEG_QUALITIES=""
BR2_PACKAGE_THINGINO_RAPTOR_UI_MMA_RESERVE_KIB="4096"
```

The configuration is not all of it, though. The series also changes code every
raptor camera runs, and an Ingenic build gets these with it:

- the 13 raptor patches (0101 to 0113);
- the uhttpd conditional-request fix and the cache policy;
- the Streamer pages, which apply a stream as one change. They offer the
  choices of the `BR2_PACKAGE_THINGINO_RAPTOR_UI_*` lists; with the lists
  empty, as above, a page shows the current values and offers no other, so
  set the lists in the profile to change a stream from the web UI;
- the Image Quality page, which shows only the controls the HAL reports;
- the web UI platform flags, which default to upstream's behaviour.

[WHAT-THIS-PORT-ADDS.md](WHAT-THIS-PORT-ADDS.md) describes each.

## Settings

Settings > Detection sets these, and so does the agent
(`/api/v1/settings/motion/...`). They are keys of `[motion]` in
`/etc/raptor.conf`; a profile can preset them at build time with the
`RAPTOR_MOTION_*` keys of its `raptor.config`.

| Key | Values | Default | Applies |
|---|---|---|---|
| `enabled` | true, false | | |
| `algorithm` | `move`, `base_move`, `persondet`, `yolo`; the page offers `persondet` and `yolo` only when their libraries are in the image | `move` | at the next stream restart |
| `sensitivity` | 0 to 4 for the motion grid, 0 to 5 for the person detector | 3 | |
| `cooldown_sec` | seconds | 10 | |
| `model` | a `.bin` under `/usr/share/models/` | `/usr/share/models/magik_model_yolov5.bin` | at the next stream restart |
| `num_classes` | 1 to 80 | 4 | at the next stream restart |
| `conf_threshold` | 1 to 99 | 40 | at the next stream restart |
| `nms_threshold` | 1 to 99 | 50 | at the next stream restart |

`rvd` reads the model keys when it starts, so the page offers a stream restart
after a change to one of them.

Two switches are separate from the detector's own keys:

- **Boxes in the stream.** `rod` draws the boxes into the sub stream whenever
  detection is on and its `detect` element is visible. The page's switch
  declares that element in `raptor.conf`, hidden or visible; it applies at
  once.
- **Boxes on the preview.** The Detections button draws them over the picture
  for the viewer alone, with the class name and score, whatever the stream
  carries. The choice is remembered per browser.

## Models

- **The public model** (`magik_model_yolov5.bin`): a YOLOv5 for JZDL with four
  classes and a portrait input of 320x416, which `rvd` squeezes the frame
  into.
- **Another model.** Put the `.bin` under `/usr/share/models/`, choose it on
  the page (the agent lists every `.bin` there) and set the class count. The
  class names come from a text file beside the model with the same name and
  `.txt` in place of `.bin`, one name a line; without that file the first
  `num_classes` names of the COCO list are used. The JZDL backend takes the
  input size from the model file and decodes a YOLOv5 head with the stock
  anchors, so a model with that head needs no code change.

- **Ours.** [models/](../models/README.md) has the models we trained: seven
  for the T31 (six classes or person only, 4 or 8 bits) and one for the T41's
  NNA, each with its names file, scores and speed.

### Making a model

Every model for these SoCs comes out of Ingenic's Magik toolkit, which
trains, quantizes and converts a network for one runtime. Which runtime
depends on the SoC:

| SoC | Runtime | Model file | Kit |
|---|---|---|---|
| T20, T21, T23, T31 (no accelerator) | JZDL, on the CPU | `.bin` | Magik 1.0, public (`themactep/magik-toolkit-ingenic`); the converter's target is `Txx` |
| T41 (and T40, A1) | Uranus, on the NNA | `.mgk`, a compiled MIPS shared object | Magik 3.x (3.1.7 here), from Ingenic; not public |

**For a T31-class camera**,
[tools/magik-train-txx](../tools/magik-train-txx/README.md) trains a YOLOv5
on your own classes and converts it for `Txx`: it fetches the public kit,
fine-tunes the kit's Txx YOLOv5 sample (the network behind the public model),
works around two converter faults that otherwise ruin a fine-tuned model, and
writes the `.bin` and its names file. Its README has the steps, what the kit
imposes (the kit's own plugin for training, channels in multiples of 16, an
RTX 20 or 30 class GPU) and the scores. In short:

- A float model cannot be converted for the T31: the converter quantizes only
  a network built from the kit's plugin layers, so a model of your own is a
  fine-tune of the kit's sample, not a conversion.
- Six classes at 4 bits, 448x256, convert to within a point of the trained
  model (person mAP50 0.882 on our held-out frames) and run in about 0.18 to
  0.4 s a frame on a T31X; at 8 bits the conversion is exact (0.915) and about
  four times slower.
- Frames from your own cameras teach their scenes and lose the general view;
  mixing in COCO pictures of the same classes (`coco_mix.py`) brings it back
  at the cost of a few points on your own frames.
- Check a converted model before trusting it: the engine takes the frame as
  `pixel - 128` in int8, so a test program that passes raw pixels sees a model
  that finds almost nothing.

**For a T41**, the model is converted with the Magik 3.x kit for Uranus. The
converter needs Ingenic's gcc 7.2 XBurst2 toolchains (published as
`gtxaspec/ingenic-toolchain`) and runs on a Linux PC in under a minute. Two
ways in:

- **Quantization-aware training** with the kit's plugin: mark the input and
  outputs, calibrate on 16 to 20 images, fine-tune, export ONNX, convert.
- **Post-training quantization** of a float ONNX model with 10 to 200
  calibration images, at most 8-bit weights.

Check the result against the kit's PC executor before a camera; gtxaspec's
QEMU fork runs the T41's NNA and gives the same outputs layer for layer. The
activation matters on the NNA: a YOLOv5s with SiLU took 252 ms a network on a
T41, the same network with LeakyReLU 69 ms, and a small ReLU6 network of six
classes 42 ms (below). The backend decodes a YOLOv5 head with the stock
anchors, as the JZDL one does.

There is no script set for the T41 path in this repository: the kit is not
public, and nothing of it can ship here.

### The Wyze Cam v4 and its accelerator

The T41 does have a neural accelerator, Ingenic's NNA, and the kernel side is
already there: Thingino builds the `soc-nna` driver for the T40, T41 and A1
families (`BR2_INGENIC_SDK_SOC_NNA`, on by default for them) and loads it at
boot on a T41.

JZDL, the engine raptor's HAL links upstream, runs on the CPU and does not use
the NNA, and on the T41 it does not run at all: Ingenic ships JZDL for the
T31's MXU (the 5.4.0 build) and an X2000 build (7.2.0, the one T40, T41 and A1
images install) compiled for MSA, the standard MIPS SIMD extension. The T41's
XBurst2 cores have Ingenic's MXU v3 instead and no MSA, so `rvd` stops with an
illegal instruction the moment the model method starts (tested on a Wyze Cam
v4, 2026-11-20). Choosing the model method on a T41 with the JZDL backend
therefore takes the video down until the method is changed back.

Detection on a T41 runs on the NNA instead, through Ingenic's Uranus runtime.
raptor's HAL upstream has no backend for it yet; one is offered as three pull
requests, open as of 2026-11-23:

| Pull request | What it adds |
|---|---|
| [gtxaspec/raptor-hal#21](https://github.com/gtxaspec/raptor-hal/pull/21) | `src/hal_ivs_uranus.cpp`: YOLOv5 on the NNA behind the JZDL backend's `hal_jzdl_*` API, so `rvd` is unchanged; every runtime call on core 0 (the NN instructions work only there); the YOLOv5 decode shared with JZDL in `src/hal_ivs_yolo.h`, with host tests |
| [gtxaspec/raptor#97](https://github.com/gtxaspec/raptor/pull/97) | with `URANUS_LIB` naming the runtime's folder, an `IVS_DETECT` build links the Uranus libraries in place of `libjzdl.m.so` |
| [gtxaspec/raptor#96](https://github.com/gtxaspec/raptor/pull/96) | `[motion] detect_interval_ms`: the inference rate, and with it the CPU spent |

None of the three is in this repository's patch series: they wait on
upstream, and the runtime they link is Ingenic's, which cannot be shipped,
here or in an image. A builder takes it from the Magik 3.x kit (the uClibc
build for a Thingino image). The web UI and the agent of this series work with
it unchanged: they read `rvd`'s detections, whichever backend produced them;
`algorithm = yolo` selects it as it does JZDL.

Besides the backend and the runtime, a T41 image needs three things before the
runtime starts:

1. **The L2 share at 128 KiB.** The T41's on-chip SRAM is split between the L2
   cache and the NNA's ORAM by the CCU register MSCR (0x12200060). Ingenic's
   own SPL sets a 128 KiB share; a Thingino T41 boots with the boot ROM's
   256 KiB. The runtime reads the ORAM's start from MSCR, and on 256 KiB asks
   for an address the `soc-nna` driver's T41 branch does not know: the first
   mapping hangs the camera
   ([themactep/thingino-firmware#2093](https://github.com/themactep/thingino-firmware/issues/2093)).
   Switching the share to 128 KiB after boot with a small kernel module,
   #2093's method, works; writing it from U-Boot left the camera off the
   network.
2. **An `nmem=` reservation** on the kernel command line, which Thingino's
   `bootcmd` does not set; `rmem=44M nmem=20M` worked.
3. **The runtime's libraries with `libstdc++` and `libgcc_s`**, which a
   Thingino image lacks by default, and the name `librt.so.0` for the uClibc
   build to load on uClibc-ng.

There is also no model to reuse from the camera itself. The stock image of the
Wyze Cam v4 unit examined for this port (a factory build dated 2024-04-29)
ships the NNA's kernel driver but no neural model and no inference library:
its application links only Ingenic's motion library. On the Infinity6C cameras it is the other way round,
which is why `thingino-ipud` takes its model from the camera's own firmware.

## What was tested, and what was not

- **Run on an Ingenic T31X camera** (a Wyze Cam Pan v3), from RAM, with the
  public model: a person box within a second; one result about every 0.5 s,
  with the CPU 4.5 % idle against 80.5 % without detection; both streams
  still at 30 fps; about 10 MB more memory. At that rate it classifies what
  moved; it does not track.
- **The preview overlay and its feed** ran on the same camera, the boxes
  following at a median of 360 ms.
- **On the host:** the agent's detection settings and reads pass a test
  against a stand-in `raptorctl`, the adapter's other answers match ones
  saved from two Infinity6C cameras, and the page scripts pass 46 checks.
- **Models of our own on the T31X**, trained and converted with
  `tools/magik-train-txx`: the converted models' output matched Ingenic's
  emulator byte for byte on the same frames, and a person was found in 57 of
  60 polls (4 bits) and 20 of 20 (8 bits). The scores are in
  [its README](../tools/magik-train-txx/README.md#what-was-tested-and-what-was-not).
- **The NNA backend on two Wyze Cam v4 (T41NQ)**, with the three pull
  requests above, the Uranus runtime of Magik kit 3.1.7 and the three image
  changes, in an image of the port's development tree:

  | Network, 640x384 | One network | In `rvd` | CPU idle (88 % without) |
  |---|---|---|---|
  | six classes, ReLU6, 0.55 M weights | 42 ms | about 12.5 results a second | 48 % |
  | YOLOv5s with SiLU | 252 ms | a result every 0.29 s | 38 % |
  | the kit's YOLOv5s with LeakyReLU | 69 ms | | |

  The cost is the CPU's: core 0 issues the NN instructions and waits on the
  unit, about 39 of each 54 ms. Streaming slows the network too (memory
  traffic): 25 ms with raptor stopped against 41 ms streaming at 25 fps. The
  six-class model found every labelled object of four held-out frames within
  about 3 px of the float model.
- **On the emulated T41** (gtxaspec's QEMU fork): the backend's outputs equal
  the kit's PC executor, and the camera's boxes equal the emulator's to the
  last digit.
- **JZDL on a T41**: stops with an illegal instruction (above).
- **Not built from these two series alone for an Ingenic profile.** The
  port's own Ingenic test images come from its development tree, which
  carries more generic work than this repository, and the T41 images also the
  NNA pull requests. The configurations above were generated, not built.
- **Not tried:** the T40 and A1 (the A1's NNA does not run under the
  emulator), and the T20, T21 and T23.
- **Detection and the camera's other load.** On the T31 the detector took
  nearly all the CPU that was idle; on the T41 the six-class model leaves
  about half. What either leaves for recording, WebRTC or anything else on
  the camera was not measured.
