# @tool vendor=ingenic kind=ml purpose=export a trained Txx checkpoint to ONNX for the converter
"""export_onnx.py CFG NC WEIGHTS OUT.onnx -- export a trained checkpoint for the converter.

Run with the kit's Python, from the kit's Txx YOLOv5 sample folder. It does what the sample's own
convert_onnx.py does (the same model code, the same torch.onnx.export options, the model left in
training mode so the graph ends at the three raw head convolutions, which the camera decodes), with
the class count as an argument where the sample's script has four built in.
"""
import sys

import torch

sys.path.insert(0, ".")
from models.yolo import Model  # noqa: E402  (the sample's own model code)


def main():
    if len(sys.argv) != 5:
        sys.exit(__doc__)
    cfg, nc, weights, out = sys.argv[1], int(sys.argv[2]), sys.argv[3], sys.argv[4]

    model = Model(cfg, ch=3, nc=nc).cuda()
    ckpt = torch.load(weights)
    net = ckpt["ema"] if ckpt.get("ema") is not None else ckpt["model"]
    model.load_state_dict(net.float().state_dict(), strict=True)

    dummy = torch.randn(2, 3, 128, 128).cuda()
    torch.onnx.export(
        model,
        dummy,
        out,
        verbose=False,
        enable_onnx_checker=False,
        do_constant_folding=False,
        operator_export_type=torch.onnx.OperatorExportTypes.ONNX_ATEN_FALLBACK,
    )
    print("wrote", out)


if __name__ == "__main__":
    main()
