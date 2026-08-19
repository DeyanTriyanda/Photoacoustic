#!/usr/bin/env python3
"""
Ekspor checkpoint SwinIR ke TorchScript (.pt) dan/atau ONNX (.onnx)
agar bisa dibungkus ke software utama (folder assets/).

  python scripts/export_onnx.py --ckpt checkpoints/best.pth \\
      --onnx ../assets/SwinIR-x2-pa.onnx --torchscript checkpoints/swinir_x2.pt
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from swinir.model import build_swinir


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", required=True)
    ap.add_argument("--onnx", type=str, default="")
    ap.add_argument("--torchscript", type=str, default="")
    ap.add_argument("--height", type=int, default=64)
    ap.add_argument("--width", type=int, default=64)
    ap.add_argument("--opset", type=int, default=17)
    args = ap.parse_args()

    device = torch.device("cpu")
    ckpt = torch.load(args.ckpt, map_location=device)
    cfg = ckpt.get("config", {}).get("model", {
        "embed_dim": 96,
        "depths": [6, 6, 6, 6],
        "num_heads": [6, 6, 6, 6],
        "window_size": 8,
        "upscale": 2,
        "task": "classical_sr",
        "in_chans": 1,
        "img_size": 64,
    })
    model = build_swinir(cfg)
    model.load_state_dict(ckpt["model"])
    model.eval()

    # Pastikan ukuran contoh kelipatan window_size
    ws = int(cfg.get("window_size", 8))
    h = args.height - (args.height % ws)
    w = args.width - (args.width % ws)
    dummy = torch.randn(1, 1, h, w)

    if args.torchscript:
        out_ts = Path(args.torchscript)
        out_ts.parent.mkdir(parents=True, exist_ok=True)
        scripted = torch.jit.trace(model, dummy)
        scripted.save(str(out_ts))
        print(f"[OK] TorchScript: {out_ts}")

    if args.onnx:
        out_onnx = Path(args.onnx)
        out_onnx.parent.mkdir(parents=True, exist_ok=True)
        torch.onnx.export(
            model,
            dummy,
            str(out_onnx),
            input_names=["input"],
            output_names=["output"],
            dynamic_axes={
                "input": {2: "height", 3: "width"},
                "output": {2: "height_out", 3: "width_out"},
            },
            opset_version=args.opset,
            do_constant_folding=True,
        )
        print(f"[OK] ONNX: {out_onnx}")
        print("Salin file ONNX ke assets/ lalu muat lewat tab Deep Learning / Pilih Model.")

    if not args.onnx and not args.torchscript:
        print("Tentukan --onnx dan/atau --torchscript")


if __name__ == "__main__":
    main()
