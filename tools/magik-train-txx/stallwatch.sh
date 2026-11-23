#!/bin/bash
# @tool vendor=ingenic kind=ml purpose=on the training box, flag a dead, plateaued, NaN or collapsing Magik training run on the console
# stallwatch.sh RUNS_DIR LOG [TAG] -- on the training box: watch every run's results.txt under RUNS_DIR
# while any train.py runs, and write one console line (the console standard, KIND alert) to LOG and the
# box console when a run goes wrong, once per run and kind:
#   dead     -- by epoch DEAD_EP (default 8) its best mAP50 is under DEAD_MAP (0.02): it is not learning
#               (2026-11-22: three narrow candidates trained from scratch at 4 bits sat at 0.002 for 25 epochs)
#   plateau  -- after PLAT_EP (20) epochs, the last PLAT_WIN (15) did not beat the best before them by
#               PLAT_GAIN (0.005) in mAP50
#   nan      -- a NaN or inf in the epoch's losses or metrics
#   drop     -- the last two mAP50s are under half its best, after the best passed 0.1 (one low epoch
#               in warm-up is noise: sF448 float went 0.25, 0.03, 0.38 on 2026-11-22)
# Also a stage line every STATUS_EVERY (10) epochs a run: epoch, P, R, mAP50, best.
# results.txt columns (the kit's YOLOv5 train.py): epoch k/N, mem, box, obj, cls, total, labels, img,
# P, R, mAP50, mAP50-95, then the val losses.
set -uo pipefail
RUNS=${1:?RUNS_DIR} LOG=${2:?LOG} TAG=${3:-train}
DEAD_EP=${DEAD_EP:-8} DEAD_MAP=${DEAD_MAP:-0.02}
PLAT_EP=${PLAT_EP:-20} PLAT_WIN=${PLAT_WIN:-15} PLAT_GAIN=${PLAT_GAIN:-0.005}
STATUS_EVERY=${STATUS_EVERY:-10} EVERY=${EVERY:-60}
SEEN=$RUNS/.stallwatch
mkdir -p "$SEEN"
say() {
	local l
	l="[$TAG $(date -u +%H:%M:%SZ)] $*"
	echo "$l" >>"$LOG"
	echo "$l" >/proc/1/fd/1 2>/dev/null
}
once() { # once RUN KIND TEXT
	[ -e "$SEEN/$1.$2" ] && return
	: >"$SEEN/$1.$2"
	say "$3"
}
check() { # check RUN_NAME RESULTS_TXT
	local n=$1 f=$2 out
	out=$(awk -v de="$DEAD_EP" -v dm="$DEAD_MAP" -v pe="$PLAT_EP" -v pw="$PLAT_WIN" -v pg="$PLAT_GAIN" '
		{ e = NR; m[e] = $11 + 0; p = $9; r = $10; last = $11 + 0
		  for (i = 3; i <= NF; i++) if ($i ~ /nan|inf/) bad = 1 }
		END {
			if (!e) exit
			best = 0; for (i = 1; i <= e; i++) if (m[i] > best) best = m[i]
			printf "epochs %d P %s R %s mAP50 %s best %.4f\n", e, p, r, last, best
			if (bad) print "nan"
			if (e >= de && best < dm) print "dead"
			if (e >= pe && e > pw) {
				b0 = 0; for (i = 1; i <= e - pw; i++) if (m[i] > b0) b0 = m[i]
				b1 = 0; for (i = e - pw + 1; i <= e; i++) if (m[i] > b1) b1 = m[i]
				if (b1 < b0 + pg) print "plateau"
			}
			if (best > 0.1 && e >= 2 && last < best / 2 && m[e - 1] < best / 2) print "drop"
		}' "$f")
	[ -n "$out" ] || return
	local st=${out%%$'\n'*} ep
	ep=$(awk '{print $2}' <<<"$st")
	grep -qx nan <<<"$out" && once "$n" nan "alert $n: NaN or inf in its losses ($st)"
	grep -qx dead <<<"$out" && once "$n" dead "alert $n: not learning, best mAP50 under $DEAD_MAP by epoch $DEAD_EP ($st)"
	grep -qx plateau <<<"$out" && once "$n" plateau "alert $n: plateau, the last $PLAT_WIN epochs did not beat the best before them by $PLAT_GAIN ($st)"
	grep -qx drop <<<"$out" && once "$n" drop "alert $n: mAP50 fell under half its best ($st)"
	[ $((ep % STATUS_EVERY)) -eq 0 ] && once "$n" "status$ep" "stage $n: $st"
}
for _ in $(seq 1 60); do # started beside train.py: give it up to 10 minutes to appear
	pgrep -f "train.py" >/dev/null && break
	sleep 10
done
while :; do
	for f in "$RUNS"/*/results.txt; do
		[ -s "$f" ] || continue
		check "$(basename "$(dirname "$f")")" "$f"
	done
	pgrep -f "train.py" >/dev/null || break
	sleep "$EVERY"
done
