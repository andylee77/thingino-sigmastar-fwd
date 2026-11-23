#!/bin/bash
# @tool vendor=ingenic kind=ml purpose=print the Magik Txx YOLOv5 sample folder set to 4 or 8 bits
# sample.sh WORKDIR BITS -- print the folder of the kit's Txx YOLOv5 sample set to BITS (4 or 8).
#
# The sample builds its network at the width set by one line of models/common.py ("bita = 4", the
# public model's). For 8 bits a copy of the sample is made once, beside the kit, with that line
# changed; training and export must use the same copy, so train.sh records the width in the run
# folder and convert.sh reads it back.
set -euo pipefail
W=$1
BITS=$2
S0=$W/kit/Models/training/pytorch/Txx_Xs2/yolov5
[ -d "$S0" ] || {
	echo "no kit in $W: run setup.sh first" >&2
	exit 1
}
case "$BITS" in
4) echo "$S0" ;;
8)
	S=$W/sample-8bit
	if [ ! -d "$S" ]; then
		cp -r "$S0" "$S"
		sed -i 's/^bita = 4$/bita = 8/' "$S/models/common.py"
	fi
	grep -q '^bita = 8$' "$S/models/common.py" || {
		echo "$S/models/common.py does not say bita = 8" >&2
		exit 1
	}
	echo "$S"
	;;
*)
	echo "BITS must be 4 or 8, not $BITS" >&2
	exit 1
	;;
esac
