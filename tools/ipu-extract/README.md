# ipu-extract

`thingino-ipud`, this port's on-camera object detector, runs a compiled model
on the Infinity6C IPU. The model is a camera vendor's file that no license lets
this repository ship. This tool takes it out of firmware you already have,
checks it against the model ipud is known to decode, and stages it for a build
or an SD card. It carries no vendor bytes of its own.

## What you need

- **The model** (913,408 bytes): the 6-class YOLOv5 detector of the JL12D2's
  stock firmware. Take it from a full flash read of a JL12D2 (the backup made
  before Thingino went on, a clip or programmer read, or a copy of its rootfs
  partition), or from its vendor firmware download. Some other Infinity6C
  vendor builds ship the same model; the tool knows it by its md5, whatever the
  image.
- **Python 3.8 or newer and unsquashfs 4.5 or newer** (squashfs-tools:
  `apt install squashfs-tools` on Debian and Ubuntu, `brew install squashfs`
  on macOS). On Windows, run it in WSL.

No IPU firmware is needed: the IPU runtime these images carry never reads the
firmware file ipud names (an empty and an all-zero file run the model the
same). ipud still checks that the file exists, so the tool writes an empty
one.

## Run

```sh
python3 ipu_extract.py <jl12d2-flash-read.bin>
```

An input can be a firmware image, a `.zip` holding one, a file already taken
out of an image, or a folder of any of these. In each image the tool finds the
SquashFS file systems and reads only the models out of them; nothing from an
input is run. It writes to `./ipud` (`-o` picks another folder):

| File | What it is |
|---|---|
| `model.img` | the detection model |
| `model.labels` | its class names, `person,bicycle,car,motorcycle,bus,truck` |
| `ipu_firmware.bin` | empty: ipud checks that it exists; an existing one is left as it is |

Exit status 0 means the folder holds a model, 1 that it holds none or a file
was refused.

## Use them

- **In a build:** copy the three files into `package/thingino-ipud/vendor/` of
  the patched firmware tree (or point `-o` there). The package installs them
  to `/usr/share/ipud/`, and the image has a built-in model. The package's
  `.gitignore` keeps `vendor/` out of git: never commit the files.
- **On the SD card, with no rebuild:** copy the folder onto the card as
  `ipud/`, then on the camera's *Object detection* page set *Load the model
  from* to *SD card*.

## The known model

ipud decodes anchor-based YOLOv5 heads (`[1, 3, H, W, 5 + nc]`). The tool
takes a model only when it knows its md5:
`db90485e5e307daee5e04c743e91a1af`.

Any other model is listed and left out. `--any` takes it anyway, for
experiments (with `--pick <md5>` when there are several): ipud may refuse it or
decode nothing useful, and an unknown model gets no `model.labels`. `--list`
shows what the inputs hold and writes nothing; `--force` replaces a different
model already in the output folder.

## License

MIT, as the rest of this repository. The model it extracts is the camera
vendor's, not this repository's, and comes with no license to redistribute it:
use it on your own cameras, and do not publish it or an image that carries it.
