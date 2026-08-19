#!/usr/bin/env python3
"""
Inferensi SwinIR pada satu citra / folder.

  python scripts/infer.py --ckpt checkpoints/best.pth --input path/citra.png --out outputs/pred.png
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import torch
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from swinir.model import build_swinir
from swinir.utils import ensure_dir, load_config


def load_model(ckpt_path: str, device):
    ckpt = torch.load(ckpt_path, map_location=device)
    cfg = ckpt.get("config", {}).get("model")
    if cfg is None:
        # fallback
        cfg = {
            "img_size": 64,
            "in_chans": 1,
            "embed_dim": 96,
            "depths": [6, 6, 6, 6],
            "num_heads": [6, 6, 6, 6],
            "window_size": 8,
            "upscale": 2,
            "task": "classical_sr",
        }
    model = build_swinir(cfg).to(device)
    model.load_state_dict(ckpt["model"])
    model.eval()
    return model, cfg


@torch.no_grad()
def infer_image(model, path: Path, device, out_path: Path):
    img = Image.open(path).convert("L")
    arr = np.asarray(img, dtype=np.float32) / 255.0
    x = torch.from_numpy(arr).unsqueeze(0).unsqueeze(0).to(device)
    y = model(x).clamp(0, 1).cpu().numpy()[0, 0]
    out = Image.fromarray((y * 255.0).round().astype(np.uint8), mode="L")
    ensure_dir(str(out_path.parent))
    out.save(out_path)
    return out_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", required=True)
    ap.add_argument("--input", required=True, help="file atau folder")
    ap.add_argument("--out", default=str(ROOT / "outputs" / "infer"))
    args = ap.parse_args()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model, _ = load_model(args.ckpt, device)

    inp = Path(args.input)
    out_root = Path(args.out)
    if inp.is_file():
        out_path = out_root if out_root.suffix else out_root / f"{inp.stem}_swinir.png"
        if out_root.suffix:
            out_path = out_root
        p = infer_image(model, inp, device, out_path)
        print(f"Tersimpan: {p}")
        return

    ensure_dir(str(out_root))
    exts = {".png", ".jpg", ".jpeg", ".bmp", ".tif"}
    files = [p for p in sorted(inp.iterdir()) if p.suffix.lower() in exts]
    for f in files:
        infer_image(model, f, device, out_root / f"{f.stem}_swinir.png")
        print(f"OK {f.name}")


if __name__ == "__main__":
    main()
