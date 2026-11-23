# @tool vendor=ingenic kind=ml purpose=the starting checkpoint for a fine-tune with another class count
"""start_weights.py CFG NC OUT [FROM] -- the starting checkpoint for a fine-tune with NC classes.

Run with the kit's Python, from the kit's Txx YOLOv5 sample folder
(Models/training/pytorch/Txx_Xs2/yolov5). It builds the sample's network (CFG, normally
models/yolov5.yaml) with NC classes and copies into it every tensor of FROM (default: the sample's
own trained weights, runs/train/yolov5-4bit/best.pt, COCO, four classes) whose shape matches. With a
class count other than four, only the three output convolutions of the detection head start fresh.

The sample's train.py loads a checkpoint with strict=False, which still refuses a tensor of another
shape; a checkpoint written here has none, so train.py takes it as it is.
"""
import sys

import torch

sys.path.insert(0, ".")
from models.yolo import Model  # noqa: E402  (the sample's own model code)


def main():
    if len(sys.argv) < 4:
        sys.exit(__doc__)
    cfg, nc, out = sys.argv[1], int(sys.argv[2]), sys.argv[3]
    src = sys.argv[4] if len(sys.argv) > 4 else "runs/train/yolov5-4bit/best.pt"

    ckpt = torch.load(src, map_location="cpu")
    old = (ckpt["ema"] if ckpt.get("ema") is not None else ckpt["model"]).float().state_dict()

    model = Model(cfg, ch=3, nc=nc)
    new = model.state_dict()
    kept = {k: v for k, v in old.items() if k in new and new[k].shape == v.shape}
    fresh = sorted(k for k in new if k not in kept)
    model.load_state_dict(kept, strict=False)

    print(f"{src}: {len(kept)} of {len(new)} tensors taken; starting fresh: {len(fresh)}")
    for k in fresh:
        print("  fresh", k, tuple(new[k].shape))
    torch.save({"epoch": -1, "model": model}, out)
    print("wrote", out)


if __name__ == "__main__":
    main()
