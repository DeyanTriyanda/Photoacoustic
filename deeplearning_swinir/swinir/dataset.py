"""Dataset pasangan LQ/HQ untuk pelatihan SwinIR (grayscale)."""

from __future__ import annotations

import os
import random
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np
import torch
from PIL import Image
from torch.utils.data import Dataset


IMG_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}


def list_images(folder: str) -> List[Path]:
    folder_p = Path(folder)
    if not folder_p.is_dir():
        return []
    files = [p for p in sorted(folder_p.iterdir()) if p.suffix.lower() in IMG_EXTS]
    return files


def load_gray01(path: Path) -> np.ndarray:
    img = Image.open(path).convert("L")
    return np.asarray(img, dtype=np.float32) / 255.0


def random_crop_pair(lq: np.ndarray, hq: np.ndarray, patch: int, scale: int):
    """Crop sinkron LQ patch & HQ (patch*scale)."""
    h, w = lq.shape
    if h < patch or w < patch:
        # pad LQ lalu HQ
        pad_h = max(patch - h, 0)
        pad_w = max(patch - w, 0)
        lq = np.pad(lq, ((0, pad_h), (0, pad_w)), mode="reflect")
        hq = np.pad(hq, ((0, pad_h * scale), (0, pad_w * scale)), mode="reflect")
        h, w = lq.shape

    top = random.randint(0, h - patch)
    left = random.randint(0, w - patch)
    lq_p = lq[top : top + patch, left : left + patch]
    hq_p = hq[top * scale : (top + patch) * scale, left * scale : (left + patch) * scale]
    return lq_p, hq_p


def augment_pair(lq: np.ndarray, hq: np.ndarray):
    if random.random() < 0.5:
        lq = np.flip(lq, axis=1).copy()
        hq = np.flip(hq, axis=1).copy()
    if random.random() < 0.5:
        lq = np.flip(lq, axis=0).copy()
        hq = np.flip(hq, axis=0).copy()
    k = random.randint(0, 3)
    if k:
        lq = np.rot90(lq, k).copy()
        hq = np.rot90(hq, k).copy()
    return lq, hq


class PairedImageDataset(Dataset):
    """
    Struktur folder:
      root/train/lq/*.png
      root/train/hq/*.png   (nama file sama)
      root/val/lq , root/val/hq
    """

    def __init__(
        self,
        lq_dir: str,
        hq_dir: str,
        patch_size: int = 64,
        scale: int = 2,
        augment: bool = True,
        task: str = "classical_sr",
    ):
        self.lq_paths = list_images(lq_dir)
        self.hq_dir = Path(hq_dir)
        self.patch_size = int(patch_size)
        self.scale = 1 if task == "denoising" else int(scale)
        self.augment = augment
        self.task = task

        if not self.lq_paths:
            raise FileNotFoundError(f"Tidak ada citra di {lq_dir}")

        missing = [p.name for p in self.lq_paths if not (self.hq_dir / p.name).is_file()]
        if missing:
            raise FileNotFoundError(
                f"{len(missing)} file LQ tanpa pasangan HQ, contoh: {missing[:3]}"
            )

    def __len__(self):
        return len(self.lq_paths)

    def __getitem__(self, idx: int):
        lq_path = self.lq_paths[idx]
        hq_path = self.hq_dir / lq_path.name
        lq = load_gray01(lq_path)
        hq = load_gray01(hq_path)

        if self.task == "denoising" and self.scale == 1:
            # HQ & LQ ukuran sama; crop sama
            h, w = min(lq.shape[0], hq.shape[0]), min(lq.shape[1], hq.shape[1])
            lq, hq = lq[:h, :w], hq[:h, :w]
            lq, hq = random_crop_pair(lq, hq, self.patch_size, 1)
        else:
            # Pastikan HQ = LQ * scale
            th, tw = lq.shape[0] * self.scale, lq.shape[1] * self.scale
            if hq.shape[0] != th or hq.shape[1] != tw:
                hq_img = Image.fromarray((hq * 255).astype(np.uint8), mode="L")
                hq_img = hq_img.resize((tw, th), Image.BICUBIC)
                hq = np.asarray(hq_img, dtype=np.float32) / 255.0
            lq, hq = random_crop_pair(lq, hq, self.patch_size, self.scale)

        if self.augment:
            lq, hq = augment_pair(lq, hq)

        lq_t = torch.from_numpy(lq).unsqueeze(0).float()
        hq_t = torch.from_numpy(hq).unsqueeze(0).float()
        return {"lq": lq_t, "hq": hq_t, "name": lq_path.stem}
