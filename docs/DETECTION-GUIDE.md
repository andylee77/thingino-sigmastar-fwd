# Detection: what the patches add and how to run them

This repository carries two different on-camera detectors, one per SoC vendor,
behind one web UI overlay:

| | Ingenic cameras (T31, T41 and the like) | SigmaStar Infinity6C cameras |
|---|---|---|
| Detector | raptor's own: the IVS detection in `rvd`, upstream in Thingino | `thingino-ipud`, on the SoC's IPU |
| Where it is | upstream's build option; this repository adds the settings page, the preview overlay and the agent's settings for it | patch 0022 of `patches/thingino-sigmastar/` |
| Model | public models from the `magik-models` package | a file from the camera's own firmware, taken out with [tools/ipu-extract](../tools/ipu-extract/README.md) |
| Runs on | the CPU, through Ingenic's JZDL engine | the IPU, the SoC's neural-network unit |

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
- **Making one** is outside this repository. Ingenic's Magik toolkit is the
  vendor's own converter and training plugin for these SoCs.

### The Wyze Cam v4 and its accelerator

JZDL runs on the CPU. The T41's neural accelerator is reached through a
different Ingenic runtime, and raptor's HAL has no backend for it: its one
detection backend is `src/hal_ivs_jzdl.cpp`. So on a Wyze Cam v4 these patches
give CPU detection through JZDL, and using the accelerator needs a new backend
in raptor-hal first. That is read from the sources; neither path has been run
on a T41 here.

There is also no model to reuse from the camera itself. The stock image of the
Wyze Cam v4 unit examined for this port (a factory build dated 2024-04-29)
holds no neural model and no inference engine: its application links only
Ingenic's motion library. On the Infinity6C cameras it is the other way round,
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
- **Not run on a T41**, and not on a Wyze Cam v4.
- **Not built from these two series alone for an Ingenic profile.** The
  port's own Ingenic test images come from its development tree, which
  carries more generic work than this repository. The configurations above
  were generated, not built.
- **Detection and the camera's other load.** On the T31 the detector took
  nearly all the CPU that was idle. What it leaves for recording, WebRTC or
  anything else on the camera was not measured.
