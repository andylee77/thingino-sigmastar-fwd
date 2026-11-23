#!/bin/bash
# @tool vendor=ingenic kind=ml purpose=fine-tune the Magik Txx YOLOv5 sample on your dataset
# train.sh DATA_YAML [EPOCHS] [IMG_SIZE] [extra train.py options...]
#
# Fine-tune the Magik kit's Txx YOLOv5 sample on your dataset, starting from the sample's own
# trained weights. DATA_YAML is a YOLOv5 dataset file with absolute paths (see the README).
# EPOCHS defaults to 100, IMG_SIZE to 448 (a multiple of 32; pick the larger side of the input size
# you will convert to). The result is $MAGIK_WORK/runs/$NAME/weights/best.pt.
#
# Environment: MAGIK_WORK (default ~/magik, as setup.sh made it), NAME (default custom),
# BATCH (default 32; lower it if the GPU runs out of memory), DEVICE (default 0),
# HYP (default data/hyp.scratch.yaml, learning rate 0.01; the kit's data/hyp.lowbit.yaml, 0.001, is
# for small adjustments), BITS (4, the public model's width and the default, or 8), START (a
# checkpoint of your own to continue from instead of the sample's weights: same classes, same BITS).
#
# --noautoanchor is always passed: the camera's decoder (raptor's JZDL backend) uses YOLOv5's stock
# anchors, so the model must keep them. At 4 bits the sample's train.py gets a hook (txxlim.py) that
# keeps every low-bit channel's bias inside what the converter can store, after each optimizer step.
# stallwatch.sh runs beside it and writes an alert line to $OUT/watch.log (and the box console) if the
# run does not learn, plateaus, falls back or hits a NaN; STALLWATCH=0 turns it off.
set -euo pipefail

[ $# -ge 1 ] || {
	sed -n '2,/^[^#]/s/^# \{0,1\}//p' "$0"
	exit 1
}
HERE=$(cd "$(dirname "$0")" && pwd)
W=${MAGIK_WORK:-$HOME/magik}
S=$("$HERE/sample.sh" "$W" "${BITS:-4}") || exit 1
PY=$W/conda/bin/python
DATA=$(readlink -f "$1")
EPOCHS=${2:-100}
IMG=${3:-448}
shift $(($# < 3 ? $# : 3))
NAME=${NAME:-custom}
OUT=$W/runs/$NAME

[ -x "$PY" ] || {
	echo "no kit in $W: run setup.sh first" >&2
	exit 1
}
[ -f "$DATA" ] || {
	echo "no dataset file $DATA" >&2
	exit 1
}
[ $((IMG % 32)) -eq 0 ] || {
	echo "IMG_SIZE $IMG is not a multiple of 32" >&2
	exit 1
}
NC=$("$PY" -c 'import sys, yaml; d = yaml.safe_load(open(sys.argv[1])); assert len(d["names"]) == int(d["nc"]), "nc and names differ"; print(int(d["nc"]))' "$DATA")

mkdir -p "$OUT"
cp "$DATA" "$OUT/data.yaml"
echo "${BITS:-4}" >"$OUT/bits"
if [ "${BITS:-4}" = 4 ]; then
	# keep the low-bit layers inside what the converter can store (txxlim.py), at every step
	"$PY" "$HERE/txxlim.py" --patch "$S"
	export TXX_LIMIT_DIR=$HERE
fi
cd "$S"
if [ -n "${START:-}" ]; then
	# continue from a checkpoint of your own (same classes, same bit width), e.g. an earlier run's best.pt
	echo "== start weights: $START"
	cp "$START" "$OUT/start.pt"
else
	echo "== start weights: the sample's, $NC classes"
	"$PY" "$HERE/start_weights.py" models/yolov5.yaml "$NC" "$OUT/start.pt"
fi
if [ "${STALLWATCH:-1}" != 0 ]; then
	(setsid nohup bash "$HERE/stallwatch.sh" "$W/runs" "$OUT/watch.log" "$NAME" >/dev/null 2>&1 </dev/null &)
fi
echo "== train: $EPOCHS epochs at $IMG, ${BITS:-4} bits, ${HYP:-data/hyp.scratch.yaml}"
"$PY" train.py --data "$DATA" --cfg models/yolov5.yaml --weights "$OUT/start.pt" \
	--hyp "${HYP:-data/hyp.scratch.yaml}" --epochs "$EPOCHS" --batch-size "${BATCH:-32}" --img-size "$IMG" \
	--noautoanchor --device "${DEVICE:-0}" --project "$OUT" --exist-ok "$@"
echo "== done: $OUT/weights/best.pt"
