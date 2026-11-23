# @tool vendor=ingenic kind=ml purpose=keep a Txx model's low-bit layers inside what the converter can store
"""txxlim.py -- keep a Txx model's low-bit layers inside what the kit's converter can store.

The converter (magik-transform-tools 1.0.0, target Txx) stores each output channel of a low-bit
convolution (weights or input under 8 bits) as an int16 multiplier, an int16 shift and an int16 bias
field A = K * steps + Z * sum(w_int), where steps is the folded bias in units of one input step times
one weight step (s_in = 6 / (2^in_bits - 1), s_w = max|w * scale| / (2^(w_bits - 1) - 1)), K is about
6.3, Z = 2^(in_bits - 1) (the input's zero point) and w_int are the channel's integer weights. It needs
|K * steps| <= 16383 and |A| <= 32767; past either it writes a wrong bias and the channel's output is
lost on the camera. Fine-tunes leave such channels (a small batch-norm scale with a large beta).

project(model) raises such a channel's batch-norm scale by the least factor that fits both limits with
a 10 % margin, keeping its folded bias. Called after every optimizer step (train.sh does this for
4-bit runs) training adapts around it; fix_bn.py calls it once before the export.

    python txxlim.py --patch SAMPLE_DIR   add the hook to the sample's train.py (idempotent); the hook
                                          runs when TXX_LIMIT_DIR names this script's folder
"""
import io
import os
import sys

import torch

K, LIM1, LIM2, EPS = 6.3, 0.9 * 16383, 0.9 * 32767, 1e-5
HOOK_AFTER = "                scaler.step(optimizer)  # optimizer.step\n"
HOOK = ("                if os.environ.get('TXX_LIMIT_DIR'):  # txxlim.py hook\n"
        "                    import sys as _sys; _sys.path.insert(0, os.environ['TXX_LIMIT_DIR'])\n"
        "                    import txxlim; txxlim.project(model)\n")


@torch.no_grad()
def project(model):
    """Bring every low-bit channel inside the limits; returns how many channels it changed. Needs a
    forward pass first (the plugin sets each layer's input bit width there)."""
    n_fix = 0
    for mod in model.modules():
        if not (hasattr(mod, "Conv2d") and hasattr(mod, "BatchNorm2d") and hasattr(mod, "QuantizeFeature")):
            continue
        if getattr(mod, "first_layer", False):
            continue
        ib, wb = mod.QuantizeFeature.input_bitwidth, mod.weight_bitwidth
        if ib >= 8 and wb >= 8:
            continue
        bn, cv = mod.BatchNorm2d.batch_norm, mod.Conv2d
        n, q = cv.out_channels, 2 ** (wb - 1) - 1
        wq = cv.QuantizeWeight([cv.weight, torch.zeros(n, device=cv.weight.device)])[0]
        wmax = wq.abs().flatten(1).max(1).values.clamp(min=1e-12)
        z = (2 ** (ib - 1)) * torch.round(wq / (wmax.view(-1, 1, 1, 1) / q)).flatten(1).sum(1)
        scale = bn.weight.clamp(min=0.01) / torch.sqrt(bn.running_var + EPS)
        b = cv.bias if cv.bias is not None else torch.zeros_like(bn.running_mean)
        folded_b = bn.bias + scale * (b - bn.running_mean)
        a = K * folded_b / ((6.0 / (2 ** ib - 1)) * wmax * scale / q)
        room = torch.where(a > 0, LIM2 - z, LIM2 + z).clamp(min=1.0)
        k = torch.maximum(torch.maximum(a.abs() / LIM1, a.abs() / room), torch.ones_like(a))
        bad = k > 1.0
        if not bad.any():
            continue
        new_scale = scale * k
        bn.weight.copy_(torch.where(bad, new_scale * torch.sqrt(bn.running_var + EPS), bn.weight))
        bn.bias.copy_(torch.where(bad, folded_b - new_scale * (b - bn.running_mean), bn.bias))
        n_fix += int(bad.sum())
    return n_fix


def patch(sample):
    p = os.path.join(sample, "train.py")
    t = io.open(p, encoding="utf-8").read()
    if "txxlim.py hook" in t:
        return "already patched"
    if t.count(HOOK_AFTER) != 1:
        sys.exit(f"{p}: the optimizer step line was not found once; the kit's train.py has changed")
    io.open(p, "w", encoding="utf-8", newline="\n").write(t.replace(HOOK_AFTER, HOOK_AFTER + HOOK))
    return "patched " + p


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--patch":
        print(patch(sys.argv[2]))
    else:
        sys.exit(__doc__)
