# The generic series

Two patches for [Thingino](https://github.com/themactep/thingino-firmware) that
do not depend on the SigmaStar platform and are not upstream yet. They are
published here so they can be read, and tried, before pull requests of their
own are opened. Every file they touch is Thingino's own
([LICENSE.md](LICENSE.md): MIT).

| # | Patch | What it does |
|---|---|---|
| 0001 | raptor agent: config reads without a process per field; detection settings | the raptor agent adapter and `agent-lib` as the port's development tree runs them: faster reads, and the settings, capabilities and current-detections read for raptor's own detector |
| 0002 | raptor: a detection settings page and a labelled preview overlay | Settings > Detection, a Detections button on the preview with labelled boxes, the event feed behind it; `thingino-ipud`'s overlay shares the drawing code |

## What they apply to

Not to bare upstream: they are cut on top of the Thingino series in
[`../thingino-sigmastar/`](../thingino-sigmastar/). Patch 0001 is a change to
that series' agent adapter, patch 0002 touches `thingino-ipud`'s overlay, which
that series adds, and the boxes in the stream need the two `rvd` fixes it
carries (raptor patches 0112 and 0113).

```sh
cd thingino-firmware
git checkout b8bcd6740
git am /path/to/patches/thingino-sigmastar/*.patch
git am /path/to/patches/thingino-generic/*.patch
```

The base is the one [../README.md](../README.md#base-and-drift) names for the
Thingino series.

## What an image needs to use them

The detection page and overlay are installed when raptor's IVS detection is
built in, which is an upstream option, off by default:

```text
BR2_PACKAGE_THINGINO_RAPTOR_IVS_DETECT=y
```

On an Ingenic profile that selects the JZDL engine and the public YOLOv5
model, both from packages upstream already has. Nothing is taken from a
camera's stock firmware. On a camera whose HAL has no IVS, as on SigmaStar
Infinity6C, the agent reports detection as unsupported and the page says so;
those cameras detect with `thingino-ipud`.

[docs/DETECTION-GUIDE.md](../../docs/DETECTION-GUIDE.md) has the rest: the
build options and what each brings, what the first series changes for an
Ingenic build, the settings and their defaults, models and class names, the
Wyze Cam v4's case, and what was tested.

## State

- Run on an Ingenic T31X camera with the public model: the detector, the
  preview overlay and its feed.
- On the host: the agent's detection answers against a stand-in `raptorctl`,
  the adapter's other answers against ones saved from two Infinity6C cameras,
  and the page scripts (46 checks).
- Not run on a T41. Not built for an Ingenic profile from the two series
  alone: the port's own Ingenic test images come from its development tree,
  which carries more generic work than is published here.
