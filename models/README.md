# Detection models

Models we trained or fine-tuned ourselves for raptor's detection on Ingenic
cameras. Each `.bin` or `.mgk` has a names file beside it (`.txt`, one class
a line) and a checksum in `SHA256SUMS`. The camera side (build options, the
Detection page, where a model goes) is in
[docs/DETECTION-GUIDE.md](../docs/DETECTION-GUIDE.md).

| Folder | SoC | Runtime | Needs |
|---|---|---|---|
| `t31/` | T31 and the other SoCs without an accelerator (T20, T21, T23) | JZDL, on the CPU | upstream raptor with `BR2_PACKAGE_THINGINO_RAPTOR_IVS_DETECT` |
| `t41/` | T41 | Uranus, on the NNA | the NNA backend of gtxaspec/raptor-hal#21 and gtxaspec/raptor#97, Ingenic's Uranus runtime and the image changes of [the guide](../docs/DETECTION-GUIDE.md#the-wyze-cam-v4-and-its-accelerator) |

Six classes, where a model has six: `person`, `dog`, `deer`, `raccoon`,
`opossum`, `vehicle` (car, truck, bus and motorcycle in one).

## Which one

- **T31, the default choice:** `magik_model_ft4lim_448x256.bin`. It finds
  more of the people in our cameras' frames than anything else that runs at a
  usable rate, and it is the one we run.
- **T31, pictures unlike ours:** `magik_model_coco4_448x256.bin`, the same
  network with COCO pictures mixed in: about the same on our frames, twice as
  good on COCO's.
- **T31, people only and fast:** `magik_model_sF448_448x256.bin`, half
  ft4lim's time for ten points less recall; it takes more things for people
  (below).
- **T41:** `ours6_t41_640x384.mgk`, the only model here.

## The T31 models

All are YOLOv5 networks trained with Ingenic's Magik kit (the public 1.0
kit, its training plugin, target `Txx`) through
[tools/magik-train-txx](../tools/magik-train-txx/README.md), and converted with
the kit's converter. The six-class models are fine-tunes of the kit's Txx
YOLOv5 sample (width 0.36); the one-class models are narrower networks of the
same family. Every one decodes with YOLOv5's stock anchors, as raptor's JZDL
backend expects.

| File | Classes | Bits | Input | Made |
|---|---|---|---|---|
| `magik_model_ft4lim_448x256.bin` | 6 | 4 | 448x256 | the kit's sample weights fine-tuned 200 epochs on our frames, then 30 more with the bias limit of `txxlim.py` |
| `magik_model_ft8fix_448x256.bin` | 6 | 8 | 448x256 | the same at 8 bits, 200 epochs; dead batch-norm channels rewritten before conversion (`fix_bn.py`) |
| `magik_model_coco4_448x256.bin` | 6 | 4 | 448x256 | ft4lim, 40 more epochs on our frames (listed twice) plus 9,885 COCO train2017 images |
| `magik_model_coco8_448x256.bin` | 6 | 8 | 448x256 | ft8fix, the same 40 epochs |
| `magik_model_sF448_448x256.bin` | person | 4 | 448x256 | width 0.25, trained in float from scratch (60 epochs), then 40 at 4 bits; our frames' people and COCO's |
| `magik_model_sF384_384x224.bin` | person | 4 | 384x224 | the same network at 384x224 |
| `magik_model_fA320_320x192.bin` | person | 4 | 320x192 | the kit's sample network, from the kit's COCO weights, 100 epochs at 4 bits |

**The data.** About 6,000 training frames from our own cameras' sub streams
(yard and kitchen cameras), labelled in the six
classes. The test set is 1,030 held-out frames of the same cameras with 577
people in them, and COCO's val2017, which no model trained on (8,189 people).

**The scores** are what a camera reports: each converted model run in Ingenic's
emulator at raptor's own settings (score at least 0.40, NMS 0.50, the YOLOv5
decode as raptor's JZDL backend does it), person boxes matched at IoU 0.5.
"Found" is the share of people found, "P" the share of reported people that
are people. The emulator's outputs match a T31X's byte for byte. Speed is one
network on a T31X (Wyze Cam Pan v3) with the CPU otherwise free; with `rvd`
streaming beside it, ft4lim took about 0.41 s a result.

| Model | Our frames: found | P | false boxes a frame | COCO: found | P | ms a frame |
|---|---|---|---|---|---|---|
| ft4lim | 0.828 | 0.887 | 0.059 | 0.199 | 0.767 | 182 |
| coco4 | 0.811 | 0.878 | 0.063 | 0.380 | 0.832 | about 180 (ft4lim's network) |
| ft8fix | 0.899 | 0.869 | 0.076 | 0.281 | 0.698 | 2,028 |
| coco8 | 0.860 | 0.867 | 0.074 | 0.419 | 0.821 | about 2,000 (ft8fix's network) |
| sF448 | 0.733 | 0.878 | 0.057 | 0.193 | 0.731 | 99 |
| fA320 | 0.657 | 0.898 | 0.042 | 0.328 | 0.825 | 100 |
| sF384 | 0.672 | 0.864 | 0.059 | 0.172 | 0.697 | 79 |

For comparison, on the same frames and settings: the kit's own 4-bit sample
weights at 448x256 found 0.516 of our people and 0.414 of COCO's; the public
`magik_model_yolov5.bin` (320x416) 0.433 and 0.383; Ingenic's person detector
library 0.272 and 0.219.

What the numbers do not show:

- **Our frames are not yours.** The six-class models learnt our cameras'
  scenes; on COCO's general pictures ft4lim finds a fifth of the people. coco4
  and coco8 trade a few points on our frames for twice that on COCO's.
- **Dogs close to the lens.** Our training dogs are small and far away. A dog
  lying near the lens got a box from coco8 in the right place, but at 0.11,
  under raptor's 0.40; the models before the COCO mix gave no box over it.
- **sF448 live.** Run in `rvd` on a Pan v3 it boxed a dog and coats on hooks
  as people. Its false-box rate on the test frames is ft4lim's, so the scene
  matters; try it on your camera before you rely on it.
- **8 bits** gains about seven points of recall for about ten times the time:
  a result every two seconds.

## The T41 model

`ours6_t41_640x384.mgk`: our own six-class network (ReLU6, 553,351 weights,
built and trained for the SigmaStar IPU; `thingino-ipud` itself runs the
camera's own model, not this one), exported at
640x384 with its three head convolutions as outputs, and converted with the
converter of Ingenic's Magik kit 3.1.7 (post-training quantization, calibrated
on 60 of its validation frames, the uClibc build). A `.mgk` is a compiled MIPS
shared object that Ingenic's Uranus runtime loads; it runs only with that
runtime, which is not in this repository.

- **Accuracy:** the float network scores mAP50 0.936 on its held-out set
  (0.925 in the IPU's integer form). On the T41 it found every labelled object of four held-out
  frames (a person, a dog, two deer, a raccoon), each the right class, boxes
  within about 3 px of the float model's and scores 0.02 to 0.05 below them.
  Four frames show the conversion is sound; they are not a score.
- **Speed**, on a Wyze Cam v4 (T41NQ): 41.7 ms a network, about 54 ms a call
  with the frame copy, resize and decode; in `rvd` about 12.5 results a
  second with both streams at 25 fps, the CPU 48 % idle against 88 % without
  detection.
- **Activation matters on this NNA:** a YOLOv5s with SiLU took 252 ms a
  network, the same with LeakyReLU 69 ms. This model's ReLU6 is one reason it
  is fast.

## Using one

Copy the model and its `.txt` to a `models/` folder at the top of the
camera's SD card (or into the image's `/usr/share/models/`), choose it on
Settings > Detection (or set `model` in `[motion]` of `/etc/raptor.conf`),
set `num_classes` (6 or 1), and restart the stream when the page offers it.
raptor stretches the frame to the model's input, so a 448x256 or 384x224 model
suits a 16:9 sensor.

## Licence

The weights are ours, made with Ingenic's Magik kits; they are published
under this repository's licence. The T31 models were trained with the public
1.0 kit, whose repository carries an MIT licence file; the T41 model was
converted with Ingenic's 3.1.7 kit, which is not public, and the `.mgk` is the
converter's output from our weights. The COCO-mixed models learnt from COCO's
train2017 pictures (annotations CC BY 4.0, images under their own Flickr
licences).
