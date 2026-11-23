# @tool vendor=ingenic kind=ml purpose=rewrite the batch-norm channels the Txx converter cannot store faithfully
"""fix_bn.py CFG NC IN.pt OUT.pt -- rewrite the batch-norm channels the Txx converter cannot store faithfully.

Run with the kit's Python, from the kit's Txx YOLOv5 sample folder of the run's bit width (sample.sh), as
convert.sh does before the export. Two rewrites, both found and checked 2026-11-20 against the converter
(magik-transform-tools 1.0.0) and the camera's engine (JZDL 1.7.0) under the Ingenic QEMU:

  dead channels: running_var under 1e-3. Training leaves such a channel constant with a folded scale
      (gamma / sqrt(var + eps)) in the hundreds, which the converter folds badly; the error spreads
      through the following layers. The channel becomes scale 1 (var 1 - eps, gamma 1) with its constant
      in beta: the PyTorch output is unchanged.

  low-bit bias fields (layers with weights or input under 8 bits): the converter keeps each channel's
      bias in an int16 field with limits (txxlim.py says which); a channel past them is brought inside by
      raising its scale. That changes the PyTorch output where it acts, so a 4-bit run is trained with the
      same limits (train.sh does) and then has only a few channels left to change here (the saved averaged
      weights drift a little from the trained ones).

A 6-class 8-bit fine-tune converted with the first rewrite scores person mAP50 0.915, as in PyTorch. A 6-class
4-bit one trained with the limits and converted with both scores 0.882 converted against 0.888 in PyTorch; the
same fine-tune trained without them converted to 0.012. Writes OUT.pt as
{"model": ..., "ema": None} and prints what it changed.
"""
import os
import sys

import torch

sys.path.insert(0, ".")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from models.yolo import Model  # noqa: E402  (the sample's own model code)
import txxlim  # noqa: E402

EPS = 1e-5  # the plugin's batchNorm2d calls F.batch_norm without eps


def main():
    if len(sys.argv) != 5:
        sys.exit(__doc__)
    cfg, nc, src, dst = sys.argv[1], int(sys.argv[2]), sys.argv[3], sys.argv[4]
    model = Model(cfg, ch=3, nc=nc).cuda()
    ckpt = torch.load(src, map_location="cuda")
    net = ckpt["ema"] if ckpt.get("ema") is not None else ckpt["model"]
    model.load_state_dict(net.float().state_dict(), strict=True)
    model.eval()
    dead_n = 0
    with torch.no_grad():
        for mod in model.modules():
            if not (hasattr(mod, "Conv2d") and hasattr(mod, "BatchNorm2d")):
                continue
            bn, cv = mod.BatchNorm2d.batch_norm, mod.Conv2d
            dead = bn.running_var < 1e-3
            if not dead.any():
                continue
            b = cv.bias if cv.bias is not None else torch.zeros_like(bn.running_mean)
            scale = bn.weight.clamp(min=0.01) / torch.sqrt(bn.running_var + EPS)
            folded_b = bn.bias + scale * (b - bn.running_mean)
            bn.running_var[dead] = 1.0 - EPS
            bn.weight[dead] = 1.0
            bn.bias[dead] = (folded_b - (b - bn.running_mean))[dead]
            dead_n += int(dead.sum())
        model(torch.zeros(1, 3, 256, 448).cuda())  # sets each layer's input bit width
        lim_n = txxlim.project(model)
    torch.save({"model": model.cpu(), "ema": None}, dst)
    print(f"dead channels rewritten: {dead_n}; low-bit channels brought inside the bias-field limits: {lim_n}")
    if lim_n:
        print("  (the PyTorch output moved where they acted; a 4-bit run trained without train.sh's limits needs a hundred or more)")
    print("wrote", dst)


if __name__ == "__main__":
    main()
