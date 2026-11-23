#!/bin/bash
# @tool vendor=ingenic kind=ml purpose=turn a train.sh run into a JZDL model file for the camera (fix_bn, ONNX, convert)
# convert.sh RUN_DIR WIDTH HEIGHT [TAG]
#
# Turn a run of train.sh into a model file for the camera: rewrite the batch-norm channels the converter
# folds badly (fix_bn.py; the PyTorch output is unchanged), export to ONNX, convert it for JZDL
# (--target_device Txx) at WIDTH x HEIGHT, and write the class names beside it.
# WIDTH and HEIGHT are multiples of 32; for a 16:9 sensor 448x256, 384x224 or 320x192 keep the
# picture undistorted (raptor stretches the frame to the model's input). TAG defaults to the run's
# folder name.
#
# Output in RUN_DIR/model/: magik_model_<TAG>_<W>x<H>.bin and .txt (one class name a line).
#
# Environment: MAGIK_WORK (default ~/magik).
set -euo pipefail

[ $# -ge 3 ] || {
	sed -n '2,/^[^#]/s/^# \{0,1\}//p' "$0"
	exit 1
}
HERE=$(cd "$(dirname "$0")" && pwd)
W=${MAGIK_WORK:-$HOME/magik}
PY=$W/conda/bin/python
CONV=$W/kit/TransformKit/magik-transform-tools
RUN=$(readlink -f "$1")
IW=$2
IH=$3
TAG=${4:-$(basename "$RUN")}_${IW}x${IH}

for v in "$IW" "$IH"; do
	[ $((v % 32)) -eq 0 ] || {
		echo "$v is not a multiple of 32" >&2
		exit 1
	}
done
[ -f "$RUN/weights/best.pt" ] && [ -f "$RUN/data.yaml" ] || {
	echo "$RUN has no weights/best.pt and data.yaml (a train.sh run folder)" >&2
	exit 1
}
S=$("$HERE/sample.sh" "$W" "$(cat "$RUN/bits" 2>/dev/null || echo 4)") || exit 1
NC=$("$PY" -c 'import sys, yaml; print(int(yaml.safe_load(open(sys.argv[1]))["nc"]))' "$RUN/data.yaml")
O=$RUN/model
mkdir -p "$O"

echo "== batch-norm channels the converter folds badly (fix_bn.py)"
(cd "$S" && "$PY" "$HERE/fix_bn.py" models/yolov5.yaml "$NC" "$RUN/weights/best.pt" "$O/fixed.pt") 2>&1 |
	grep -v "BITA\|INFO\|Warn"

echo "== ONNX ($NC classes)"
(cd "$S" && "$PY" "$HERE/export_onnx.py" models/yolov5.yaml "$NC" "$O/fixed.pt" "$O/best.onnx")

echo "== convert for Txx at ${IW}x${IH}"
cd "$O"
rm -f "magik_model_$TAG.bin"
set +e
"$CONV" --framework onnx --target_device Txx \
	--inputpath "$O/best.onnx" --outputpath "$TAG.mk.h" \
	--mean 0 --var 255 --img_width "$IW" --img_height "$IH" --img_channel 3 \
	--input_prepad true >"$O/$TAG.convert.log" 2>&1
rc=$?
set -e
# The converter has been seen to exit 1 after writing a good model, so the file decides, not the code.
if [ ! -s "magik_model_$TAG.bin" ]; then
	echo "no model written (converter exit $rc); the end of $O/$TAG.convert.log:" >&2
	sed 's/\x1b\[[0-9;]*m//g' "$O/$TAG.convert.log" | tail -n 25 >&2
	exit 1
fi
"$PY" -c 'import sys, yaml; print("\n".join(yaml.safe_load(open(sys.argv[1]))["names"]))' \
	"$RUN/data.yaml" >"magik_model_$TAG.txt"
echo "== $O/magik_model_$TAG.bin ($(stat -c %s "magik_model_$TAG.bin") bytes), converter exit $rc"
echo "   $O/magik_model_$TAG.txt ($NC names)"
