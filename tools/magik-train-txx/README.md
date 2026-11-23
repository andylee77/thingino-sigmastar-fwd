# magik-train-txx: train a detection model for a T31-class camera

Scripts that train a YOLOv5 model on your own classes and turn it into a
model file that raptor's detection runs on the camera, faithfully: the model on
the camera finds what the trained model finds. It is for the Ingenic
chips without a neural accelerator (T20, T21, T23, T31 and their variants, such
as the T31X and T31ZX), where the model runs on the CPU through Ingenic's JZDL
engine. Ingenic's Magik kit calls this target `Txx`. The camera model does not
matter; the SoC does.

The scripts carry nothing of Ingenic's. `setup.sh` fetches the Magik kit from
its public repository, and the training uses the kit's own sample network and
code. What these scripts add is the glue: starting from the sample's trained
weights with another class count, keeping the anchors the camera's decoder
expects, working around two limits of the converter that otherwise break a
fine-tuned model (below), and exporting and converting with the settings that
are known to give a working model.

| Script | What it does |
|---|---|
| `setup.sh` | installs Miniconda (Python 3.8), PyTorch 1.8.1 for CUDA 11.1, the Magik kit at a fixed commit and its training plugin, and checks the GPU |
| `start_weights.py` | the sample network with your class count, every tensor of the sample's trained weights that fits copied in |
| `sample.sh` | the kit's sample folder for a bit width: the kit's own for 4 bits, a copy for 8 |
| `txxlim.py` | keeps every 4-bit layer's bias inside what the converter can store; `train.sh` runs it after each training step |
| `train.sh` | trains: the kit's `train.py` with the right options, from the sample's weights or a checkpoint of your own |
| `stallwatch.sh` | started by `train.sh` beside the training: writes an alert line to the run's `watch.log` when a run does not learn, plateaus, falls back or hits a NaN; `STALLWATCH=0` turns it off |
| `coco_mix.py` | optional: a subset of COCO in your classes, to mix into your own frames |
| `fix_bn.py` | before export: rewrites the batch-norm channels the converter folds badly, and applies `txxlim.py` once more |
| `export_onnx.py` | the sample's ONNX export, with your class count |
| `convert.sh` | `fix_bn.py`, the export and the conversion for `Txx`, the class names beside the model |

For the camera side (build options, the Detection page, where the model goes)
see [DETECTION-GUIDE.md](../../docs/DETECTION-GUIDE.md).

## Why the sample network, and why fine-tune

The kit's converter puts three conditions on a JZDL model:

- **It must be trained with the kit's plugin.** The converter does not quantize
  a float model for `Txx`; only a network built from the plugin's quantizing
  layers converts. A YOLOv5 trained the usual way, or a model made for another
  accelerator, cannot be converted as it is.
- **Every convolution's output channels are a multiple of 16** (the head's last
  convolutions excepted).
- **A stride-2 3x3 convolution pads on the right and bottom only.** The
  plugin's layers do this; a network trained in plain PyTorch does not, so its
  weights give wrong answers even when the shapes fit.

The kit's Txx YOLOv5 sample meets all three and is the network behind the
public `magik_model_yolov5.bin`. Fine-tuning it from those weights is the
shortest way to a model of your own classes.

## What you need

- A Linux x86_64 machine with an NVIDIA GPU the kit's training plugin has code
  for: compute capability 3.5 to 7.5, or 8.6. That is the RTX 20 and 30
  series, A10, A40, RTX A6000, V100, P100 and T4. An A100 (8.0), H100, or an
  RTX 40 or 50 series card does **not** work: the plugin carries no code for
  them and training stops with "no kernel image is available". `setup.sh`
  checks the card. A rented GPU is fine.
- About 6 GB of disk for the tools, plus your dataset.
- A dataset in YOLO format: images, and for each image a `.txt` of the same
  name with one `class x_center y_center width height` line per object
  (normalized 0 to 1), in a `labels/` folder beside `images/`. Frames from the
  camera itself train best.

## Steps

### 1. Set up

```sh
./setup.sh                  # into ~/magik; or ./setup.sh /path/to/workdir and export MAGIK_WORK=that path
```

It installs Miniconda with Python 3.8, PyTorch 1.8.1 for CUDA 11.1, the kit
(at a fixed commit) and its training plugin, then checks that the GPU and the
plugin answer. PyTorch 1.8, not the newer 1.10 the kit also offers a plugin
for: under 1.10 the ONNX export of the plugin's layers fails, the kit's own
exporter included. The plugin has GPU code for compute capability 3.5 to 7.5
and 8.6 only, so `setup.sh` stops on any other card.

### 2. Describe the dataset

A YOLOv5 dataset file, with absolute paths:

```yaml
train: /data/mycams/images/train
val: /data/mycams/images/val
nc: 3
names: ['person', 'car', 'dog']
```

`train:` can also name a text file with one image path a line, which is how a
mix of your frames and COCO's (next step) is given.

### 2a. Optional: mix in COCO

A model fine-tuned only on frames from your own cameras learns those scenes
and loses much of the general view. Ours, trained on our yard and kitchen
cameras, scored person mAP50 0.915 on our own held-out frames but 0.363 on
COCO's pictures, where the kit's own weights score 0.550; and it missed a dog
lying close to the lens, because every training dog was small and walking.
Mixing COCO pictures of the same classes into the training keeps both.

```sh
# COCO's annotations: http://images.cocodataset.org/annotations/annotations_trainval2017.zip
python3 coco_mix.py annotations/instances_train2017.json /data/coco-mix \
    "person:0,dog:1,car:5,truck:5,bus:5,motorcycle:5" --all dog --per-class 2000 --fetch
```

It takes every COCO image of the classes given with `--all`, `--per-class`
images of each other class, labels every box of your classes in them (crowd
boxes skipped) and, with `--fetch`, downloads the images (a few minutes for
10,000). Use COCO's train2017 only, so that its val2017 stays free for
testing. Then list your images and COCO's in one file for `train:`; if COCO's
would outnumber yours, list yours twice through a second path (a symlinked
folder for both `images/` and `labels/`: the kit's loader drops a path it has
already seen).

### 3. Train

```sh
./train.sh /data/mycams/data.yaml 100 448
```

The arguments are the dataset file, the epochs (default 100) and the training
image size (default 448, a multiple of 32: use the larger side of the input
size you will convert to). `NAME=mymodel` names the run (default `custom`),
`BATCH=16` lowers the batch if the GPU runs out of memory. Further options go to
the kit's `train.py`. The weights land in `~/magik/runs/<NAME>/weights/best.pt`.

- `BITS=8` trains at 8 bits instead of the public model's 4 (a copy of the
  sample with its one bit-width line changed; `convert.sh` follows the run's
  setting). Both convert faithfully (below); an 8-bit model is about four
  times slower on the camera.
- At 4 bits `train.sh` adds a hook to the kit's `train.py` (`txxlim.py`) that
  keeps every layer's bias inside what the converter can store, after each
  training step. Without it a fine-tune converts to a model that finds almost
  nothing (below).
- `HYP` picks the kit's hyperparameter file. The default,
  `data/hyp.scratch.yaml`, starts at a learning rate of 0.01; the kit's
  `data/hyp.lowbit.yaml` starts at 0.001, which is for small adjustments to a
  model that already knows its classes and leaves new classes barely learnt.
- Give it epochs: 200 in our test from the sample's weights, and both runs
  were still improving slowly.
- `START=/path/to/best.pt` continues from a checkpoint of your own (same
  classes and bit width) instead of the sample's weights, for example to add
  COCO to a model already trained on your frames: fewer epochs are needed.

The anchors are kept at YOLOv5's stock values (`--noautoanchor`), because the
camera decodes with those.

### 4. Convert

```sh
./convert.sh ~/magik/runs/custom 448 256
```

It rewrites the batch-norm channels the converter folds badly (`fix_bn.py`;
the model's own output does not change), exports the weights, converts them for
`Txx` at the given width and height, and writes the class names beside the
model. It also brings inside any 4-bit channel still past the converter's
bias limit (`txxlim.py`): a run trained through `train.sh` has a few of those,
one trained some other way a hundred or more, and then the converted model
will not match the trained one.

- `~/magik/runs/custom/model/magik_model_custom_448x256.bin`
- `~/magik/runs/custom/model/magik_model_custom_448x256.txt`

raptor stretches the camera's frame to the model's input, so for a 16:9 sensor
pick a 16:9-like size: 448x256, 384x224 or 320x192. The public model's input is
320x416, portrait, which squeezes a landscape picture, so a model whose input
matches the frame's shape matters. Smaller is faster: on a T31X the
sample's weights gave a result about every 370 ms at 448x256, 260 ms at 384x224
and 210 ms at 320x192, with the CPU fully used.

The converter has been seen to exit with 1 after writing a good model, so the
script checks for the file instead of the exit code.

### Check the converted model

A converted model can differ from the trained one without any error message,
so check it before trusting it:

- **On the camera:** the log shows `JZDL: model loaded`, and
  `raptorctl rvd ivs-detections` lists the boxes found in the current frame.
- **Against the trained model:** run a few frames through both. The JZDL engine
  takes the frame as `pixel - 128` in int8 (`jzdl::image_sub(img, 128)` before
  the cast), as raptor feeds it; a test program that passes the raw pixels gets
  a model that seems to find almost nothing. The trained model in the kit's
  PyTorch, in eval mode, takes the pixels divided by 255. The raw outputs of
  the three heads should match closely; mAP on held-out frames should match to
  a point or two.

## Known converter limits

The kit's converter (`magik-transform-tools` 1.0.0, target `Txx`) gets two
kinds of channel wrong; a model fine-tuned from the sample's weights has both,
the sample's own weights almost none. Found by converting copies of a model
that differ in one channel and comparing the files and their outputs.

- **Dead batch-norm channels** (running variance near 0): the folded scale is
  in the hundreds and the converter folds it badly; the error spreads through
  the following layers. `fix_bn.py` rewrites them to an equivalent channel with
  scale 1, the model's output unchanged.
- **The 4-bit bias field:** for each output channel of a 4-bit layer the
  converter stores a multiplier, a shift and the bias as a 16-bit integer:
  about 6.3 x the bias counted in steps of one input level times one weight
  level, plus the input's zero point (16 for 5-bit inputs, 8 for 4-bit) times
  the sum of the channel's integer weights. The bias part must stay within
  16383 and the whole within 32767; past either the converter writes a wrong
  value and the channel's output is lost. A channel with a small batch-norm
  scale and a large beta needs tens of thousands. `txxlim.py` raises such a
  channel's scale just enough, keeping its bias, after every training step, so
  that training adapts around it; applied only after training it costs
  accuracy (0.775 against 0.881 in our test).

The 8-bit layers have no such field limit.

### 5. On the camera

Copy both files to `/usr/share/models/`, choose the model on Settings >
Detection (or set `model` in `[motion]` of `/etc/raptor.conf`), set
`num_classes` to your class count, and restart the stream when the page offers
it. The `.txt` gives the boxes their names. See
[DETECTION-GUIDE.md](../../docs/DETECTION-GUIDE.md#models).

## What was tested, and what was not

All scores are person mAP50 / mAP50-95 on 1,030 held-out frames from our own
cameras (577 people), the converted model run in Ingenic's QEMU, whose output
matched a T31X byte for byte on the same frames.

| Model | Trained (PyTorch) | Converted | On a T31X (Wyze Cam Pan v3) |
|---|---|---|---|
| 8-bit, 200 epochs, 6 classes, `convert.sh` | 0.915 / 0.618 | 0.915 / 0.617 | 2.0 s a frame; a person found in 20 of 20 polls, confidence 0.80 to 0.89 |
| 4-bit, the same without `txxlim.py` | 0.881 / 0.555 | 0.012 / 0.003 | - |
| 4-bit, 30 more epochs with `txxlim.py` | 0.888 / 0.562 | 0.882 / 0.566 | 0.41 s a frame; a person found in 57 of 60 polls, confidence 0.41 to 0.90 |

- **Set up and trained on** a Tesla P100 and an RTX 2080 Ti (PyTorch 1.8.1),
  rented.
- **On the camera** both models loaded in raptor from `/tmp` and gave the same
  output as the emulator. Neither found a dog lying on a bed close to the
  lens.
- **With COCO mixed in** (step 2a: our frames listed twice, 9,885 COCO images
  with every dog, 40 more epochs from those models with `START=`), on COCO's
  val pictures person mAP50 rose from 0.363 to 0.532 at 8 bits and from 0.314
  to 0.510 at 4 bits (the kit's own weights: 0.550), and dogs from about 0 to
  0.10 and 0.07. On our own frames person fell 3 points and dogs 10 points at
  8 bits and 32 at 4 bits: our cameras' dogs are small and far, COCO's mostly
  large and close. The dog lying near the lens got a box in the right place,
  but at 0.11, under raptor's 0.40. A gentler pass (the lower learning rate,
  your own frames weighted more, frames of the case you care about) is the
  next thing to try.
- **Also tested:** the converter on the sample's trained weights at four input
  sizes, and those models on a T31X through raptor's JZDL backend, with the
  rates above.
- **Not tried:** the T20, T21 and T23. They take the same `Txx` target and the
  same engine, so the model should run there too.

## Licence

These scripts are under this repository's licence. The Magik kit is fetched
from its own repository and is not part of this one; it carries an MIT licence
file. COCO's annotations are under CC BY 4.0, and its images under their own
Flickr licences (listed per image in the annotations file). A model you train
is yours to use; check the kit's terms and COCO's before you share
one.
