# @tool vendor=ingenic kind=ml purpose=a COCO train2017 subset in your classes, YOLO labels, optional download
"""coco_mix.py ANNOTATIONS.json OUTDIR MAP [--per-class N] [--all CLASS] [--fetch] -- a COCO subset in your classes.

Fine-tuning only on frames from your own cameras makes a model that knows those scenes and little else:
a dog close to the lens, lying down or half out of the picture is missed if every training dog was small
and walking across a yard. Mixing in COCO pictures of the same classes keeps the general view.

ANNOTATIONS.json is COCO's instances_train2017.json (from annotations_trainval2017.zip). Use train2017
only, so that COCO's val2017 stays free for testing. MAP names the COCO categories to keep and your class
number for each, as "person:0,dog:1,car:5,truck:5,bus:5,motorcycle:5". Every image holding a category of
--all (repeatable) is taken; of the other mapped categories --per-class N images each (default 2000,
random with seed 0). In every chosen image all mapped boxes are labelled; crowd boxes are skipped.

Writes OUTDIR/labels/coco_<id>.txt (YOLO format), OUTDIR/urls.txt (url, tab, file name) and, with
--fetch, the images into OUTDIR/images/ (16 at a time, skipping those already there). Then list the
images in your training set, for example in a text file of image paths that the dataset file's train:
names, with your own images listed twice if COCO's would otherwise outnumber them.
"""
import argparse
import json
import os
import random
import sys
import urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("annotations")
    ap.add_argument("outdir")
    ap.add_argument("map")
    ap.add_argument("--per-class", type=int, default=2000)
    ap.add_argument("--all", action="append", default=[])
    ap.add_argument("--fetch", action="store_true")
    a = ap.parse_args()

    d = json.load(open(a.annotations, encoding="utf-8"))
    cat = {c["name"]: c["id"] for c in d["categories"]}
    mapping = {}
    for item in a.map.split(","):
        name, num = item.rsplit(":", 1)
        if name not in cat:
            sys.exit(f"no COCO category '{name}'")
        mapping[cat[name]] = int(num)
    for name in a.all:
        if name not in cat or cat[name] not in mapping:
            sys.exit(f"--all {name}: not a category of MAP")

    imgs = {i["id"]: i for i in d["images"]}
    boxes, has = defaultdict(list), defaultdict(set)
    for an in d["annotations"]:
        c = mapping.get(an["category_id"])
        if c is None or an.get("iscrowd"):
            continue
        boxes[an["image_id"]].append((c, an["bbox"]))
        has[an["category_id"]].add(an["image_id"])

    random.seed(0)
    chosen = set()
    for name in a.all:
        chosen |= has[cat[name]]
    for cid in mapping:
        if any(cat[n] == cid for n in a.all):
            continue
        pool = sorted(has[cid] - chosen)
        chosen |= set(random.sample(pool, min(a.per_class, len(pool))))

    os.makedirs(os.path.join(a.outdir, "labels"), exist_ok=True)
    count = defaultdict(int)
    todo = []
    with open(os.path.join(a.outdir, "urls.txt"), "w", encoding="utf-8", newline="\n") as u:
        for iid in sorted(chosen):
            im = imgs[iid]
            W, H = im["width"], im["height"]
            lines = []
            for c, (x, y, w, h) in boxes[iid]:
                if w < 2 or h < 2:
                    continue
                lines.append(f"{c} {(x + w / 2) / W:.6f} {(y + h / 2) / H:.6f} {w / W:.6f} {h / H:.6f}")
                count[c] += 1
            name = f"coco_{iid:012d}"
            with open(os.path.join(a.outdir, "labels", name + ".txt"), "w", encoding="utf-8", newline="\n") as f:
                f.write("\n".join(lines) + ("\n" if lines else ""))
            u.write(f"{im['coco_url']}\t{name}.jpg\n")
            todo.append((im["coco_url"], name + ".jpg"))
    print(f"{len(chosen)} images; boxes per class: " + ", ".join(f"{c}: {n}" for c, n in sorted(count.items())))

    if a.fetch:
        idir = os.path.join(a.outdir, "images")
        os.makedirs(idir, exist_ok=True)

        def get(job):
            url, fn = job
            p = os.path.join(idir, fn)
            if os.path.exists(p) and os.path.getsize(p):
                return 0
            for _ in range(3):
                try:
                    urllib.request.urlretrieve(url, p)
                    return 0
                except OSError:
                    pass
            return 1

        with ThreadPoolExecutor(16) as ex:
            failed = sum(ex.map(get, todo))
        print(f"fetched into {idir}; {failed} failed")


if __name__ == "__main__":
    main()
