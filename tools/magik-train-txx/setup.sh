#!/bin/bash
# @tool vendor=ingenic kind=ml purpose=prepare a Linux GPU machine to train YOLOv5 for Ingenic's JZDL engine with the Magik kit
# setup.sh [WORKDIR] -- prepare a Linux x86_64 machine with an NVIDIA GPU to train a YOLOv5 model for
# Ingenic's JZDL engine (the CPU engine of the T-series chips without an accelerator: T20, T21, T23,
# T31 and the like; the Magik kit's target "Txx").
#
# Installs into WORKDIR (default ~/magik): Miniconda with Python 3.8, PyTorch 1.8.1 for CUDA 11.1,
# the Magik kit cloned at a fixed commit, and the kit's training plugin. Nothing outside WORKDIR is
# touched. Needs git, wget and about 6 GB of disk. The plugin's GPU code covers compute capability
# 3.5 to 7.5 and 8.6 only: RTX 20 and 30 series, A10, A40, RTX A6000, V100, P100, T4 work; an A100,
# H100, RTX 40 or 50 series card does not. The check at the end says which you have.
set -euo pipefail

W=${1:-$HOME/magik}
KIT_URL=${KIT_URL:-https://github.com/themactep/magik-toolkit-ingenic}
KIT_REV=${KIT_REV:-4dbb89c}
MINICONDA=Miniconda3-py38_23.11.0-2-Linux-x86_64.sh

mkdir -p "$W"
cd "$W"

if [ ! -x conda/bin/python ]; then
	echo "== Miniconda (Python 3.8)"
	wget -q "https://repo.anaconda.com/miniconda/$MINICONDA" -O mc.sh
	bash mc.sh -b -p "$W/conda" >/dev/null 2>&1
	rm -f mc.sh
fi
PY=$W/conda/bin/python

if [ ! -d kit/.git ]; then
	echo "== the Magik kit (about 700 MB)"
	git clone -q "$KIT_URL" kit
fi
git -C kit checkout -q "$KIT_REV"
chmod +x kit/TransformKit/magik-transform-tools

echo "== PyTorch 1.8.1 + CUDA 11.1, and the training plugin"
# PyTorch 1.8, not 1.10: under 1.10 the ONNX export of the plugin's layers stops on an internal shape
# assertion (the kit's own convert_onnx.py too); under 1.8 the kit's weights export and convert to the
# same bytes as the public model.
"$PY" -m pip install -q torch==1.8.1+cu111 torchvision==0.9.1+cu111 \
	-f https://download.pytorch.org/whl/torch_stable.html
"$PY" -m pip install -q "numpy<1.24" opencv-python-headless pyyaml tqdm matplotlib pandas seaborn \
	scipy thop "pillow<10" requests "onnx<1.15" tensorboard "protobuf<4" "setuptools<59.6"
# numpy<1.24 and pillow<10: the kit's YOLOv5 fork uses np.int and ImageFont.getsize, both removed after.
# setuptools<59.6: PyTorch's tensorboard import of that era (which train.py makes) fails on a newer one.
"$PY" -m pip install -q kit/TrainingKit/pytorch/magik_whl/Magik_py38_torch1.8_cuda-11.1/*.whl

echo "== check"
"$PY" - <<'EOF'
import torch
print("torch", torch.__version__, "| cuda", torch.cuda.is_available(),
      "|", torch.cuda.get_device_name(0) if torch.cuda.is_available() else "no GPU")
from ingenic_magik_trainingkit.QuantizationTrainingPlugin.python import ops  # noqa: F401
print("training plugin: ok")
# The plugin's GPU code is built for these compute capabilities only, with no PTX to fall back on;
# on any other GPU training stops with "no kernel image is available for execution on the device".
ok = {(3, 5), (3, 7), (5, 0), (5, 2), (6, 0), (6, 1), (7, 0), (7, 5), (8, 6)}
if torch.cuda.is_available():
    cap = torch.cuda.get_device_capability(0)
    if cap in ok:
        print("GPU compute capability %d.%d: supported by the plugin" % cap)
    else:
        print("GPU compute capability %d.%d: NOT supported by the plugin (it needs 3.5-7.5 or 8.6:"
              " e.g. RTX 20 or 30 series, A10, A40, RTX A6000, V100, P100, T4); training will fail" % cap)
        raise SystemExit(1)
EOF
"$W/kit/TransformKit/magik-transform-tools" --help >/dev/null 2>&1 && echo "converter: ok" ||
	echo "converter: did not answer --help (it may still convert; see the README)"
echo "== ready in $W"
