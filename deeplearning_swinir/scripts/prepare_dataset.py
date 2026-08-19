#!/usr/bin/env python3
"""
Siapkan dataset LQ/HQ dari citra HQ fotoakustik.

Mode classical_sr:
  HQ asli → downscale bicubic jadi LQ (x2/x4)

Mode denoising:
  HQ asli → LQ = HQ + noise Gaussian

  python scripts/prepare_dataset.py --hq-dir /path/hq_pngs --out data --scale 2
"""

from __future__ import annotations

import argparse
import random
from pathlib import Path

import numpy as np
from PIL import Image

EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}


def list_imgs(folder: Path):
    return [p for p in sorted(folder.iterdir()) if p.suffix.lower() in EXTS]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hq-dir", required=True, help="Folder citra HQ grayscale")
    ap.add_argument("--out", default="data")
    ap.add_argument("--scale", type=int, default=2)
    ap.add_argument("--task", choices=["classical_sr", "denoising"], default="classical_sr")
    ap.add_argument("--noise-sigma", type=float, default=0.05, help="untuk denoising (0..1)")
    ap.add_argument("--val-ratio", type=float, default=0.2)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    random.seed(args.seed)
    hq_files = list_imgs(Path(args.hq_dir))
    if not hq_files:
        raise SystemExit(f"Tidak ada citra di {args.hq_dir}")

    random.shuffle(hq_files)
    n_val = max(1, int(len(hq_files) * args.val_ratio))
    val_files = set(hq_files[:n_val])
    train_files = hq_files[n_val:]
    if not train_files:
        train_files, val_files = hq_files[:-1], set(hq_files[-1:])

    out = Path(args.out)
    for split in ("train", "val"):
        (out / split / "hq").mkdir(parents=True, exist_ok=True)
        (out / split / "lq").mkdir(parents=True, exist_ok=True)

    def process(files, split):
        for p in files:
            img = Image.open(p).convert("L")
            # crop ke genap agar scale rapi
            w, h = img.size
            w2, h2 = w - (w % args.scale), h - (h % args.scale)
            img = img.crop((0, 0, w2, h2))
            hq_arr = np.asarray(img, dtype=np.float32) / 255.0

            if args.task == "classical_sr":
                lq = img.resize((w2 // args.scale, h2 // args.scale), Image.BICUBIC)
            else:
                noise = np.random.normal(0, args.noise_sigma, hq_arr.shape).astype(np.float32)
                lq_arr = np.clip(hq_arr + noise, 0, 1)
                lq = Image.fromarray((lq_arr * 255).astype(np.uint8), mode="L")

            name = p.stem + ".png"
            img.save(out / split / "hq" / name)
            lq.save(out / split / "lq" / name)

    process(train_files, "train")
    process(list(val_files), "val")
    print(f"[OK] train={len(train_files)} val={len(val_files)}")
    print(f"Struktur: {out}/train|val / lq|hq")


if __name__ == "__main__":
    main()
