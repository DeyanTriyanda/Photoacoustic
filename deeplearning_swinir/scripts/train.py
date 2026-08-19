#!/usr/bin/env python3
"""
Pelatihan SwinIR untuk citra fotoakustik.

Contoh:
  cd deeplearning_swinir
  python scripts/train.py --config configs/train_pa_x2.yaml
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import torch
from torch.utils.data import DataLoader
from tqdm import tqdm

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from swinir.dataset import PairedImageDataset
from swinir.losses import SwinIRLoss
from swinir.metrics import psnr, ssim
from swinir.model import build_swinir
from swinir.utils import ensure_dir, load_checkpoint, load_config, save_checkpoint, set_seed


def parse_args():
    p = argparse.ArgumentParser(description="Train SwinIR (fotoakustik)")
    p.add_argument("--config", type=str, required=True)
    p.add_argument("--resume", type=str, default="")
    return p.parse_args()


@torch.no_grad()
def validate(model, loader, device, use_amp=False):
    model.eval()
    psnr_v, ssim_v, n = 0.0, 0.0, 0
    for batch in loader:
        lq = batch["lq"].to(device)
        hq = batch["hq"].to(device)
        with torch.cuda.amp.autocast(enabled=use_amp):
            pred = model(lq)
        # crop pred ke ukuran hq jika padding
        pred = pred[:, :, : hq.shape[2], : hq.shape[3]]
        psnr_v += psnr(pred, hq)
        ssim_v += ssim(pred, hq)
        n += 1
    return psnr_v / max(n, 1), ssim_v / max(n, 1)


def main():
    args = parse_args()
    cfg = load_config(args.config)
    set_seed(int(cfg.get("seed", 42)))

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[INFO] device={device}")

    data_cfg = cfg["data"]
    model_cfg = cfg["model"]
    train_cfg = cfg["train"]

    train_set = PairedImageDataset(
        lq_dir=data_cfg["train_lq"],
        hq_dir=data_cfg["train_hq"],
        patch_size=int(data_cfg.get("patch_size", 64)),
        scale=int(model_cfg.get("upscale", 2)),
        augment=True,
        task=model_cfg.get("task", "classical_sr"),
    )
    val_set = PairedImageDataset(
        lq_dir=data_cfg["val_lq"],
        hq_dir=data_cfg["val_hq"],
        patch_size=int(data_cfg.get("patch_size", 64)),
        scale=int(model_cfg.get("upscale", 2)),
        augment=False,
        task=model_cfg.get("task", "classical_sr"),
    )

    train_loader = DataLoader(
        train_set,
        batch_size=int(train_cfg.get("batch_size", 4)),
        shuffle=True,
        num_workers=int(train_cfg.get("num_workers", 2)),
        pin_memory=device.type == "cuda",
        drop_last=True,
    )
    val_loader = DataLoader(
        val_set,
        batch_size=1,
        shuffle=False,
        num_workers=0,
    )

    model = build_swinir(model_cfg).to(device)
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=float(train_cfg.get("lr", 2e-4)),
        weight_decay=float(train_cfg.get("weight_decay", 1e-4)),
        betas=(0.9, 0.99),
    )
    total_epochs = int(train_cfg.get("epochs", 100))
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
        optimizer, T_max=total_epochs, eta_min=float(train_cfg.get("lr_min", 1e-6))
    )
    criterion = SwinIRLoss(
        pixel=train_cfg.get("pixel_loss", "l1"),
        fft_weight=float(train_cfg.get("fft_weight", 0.02)),
        charbonnier=bool(train_cfg.get("charbonnier", True)),
    )

    use_amp = bool(train_cfg.get("amp", True)) and device.type == "cuda"
    scaler = torch.cuda.amp.GradScaler(enabled=use_amp)

    ckpt_dir = ensure_dir(train_cfg.get("checkpoint_dir", str(ROOT / "checkpoints")))
    log_dir = ensure_dir(train_cfg.get("log_dir", str(ROOT / "outputs" / "logs")))
    start_epoch, best_psnr = 0, 0.0

    if args.resume:
        start_epoch, best_psnr = load_checkpoint(args.resume, model, optimizer, device)
        print(f"[INFO] resume epoch={start_epoch} best_psnr={best_psnr:.3f}")

    log_path = Path(log_dir) / "train_log.csv"
    if not log_path.exists():
        log_path.write_text("epoch,loss,psnr,ssim,lr\n", encoding="utf-8")

    for epoch in range(start_epoch + 1, total_epochs + 1):
        model.train()
        running = 0.0
        t0 = time.time()
        pbar = tqdm(train_loader, desc=f"Epoch {epoch}/{total_epochs}")
        for batch in pbar:
            lq = batch["lq"].to(device)
            hq = batch["hq"].to(device)
            optimizer.zero_grad(set_to_none=True)
            with torch.cuda.amp.autocast(enabled=use_amp):
                pred = model(lq)
                pred = pred[:, :, : hq.shape[2], : hq.shape[3]]
                loss, _ = criterion(pred, hq)
            scaler.scale(loss).backward()
            if float(train_cfg.get("grad_clip", 0)) > 0:
                scaler.unscale_(optimizer)
                torch.nn.utils.clip_grad_norm_(
                    model.parameters(), float(train_cfg["grad_clip"])
                )
            scaler.step(optimizer)
            scaler.update()
            running += loss.item()
            pbar.set_postfix(loss=f"{loss.item():.4f}")

        scheduler.step()
        avg_loss = running / max(len(train_loader), 1)
        val_psnr, val_ssim = validate(model, val_loader, device, use_amp)
        lr = optimizer.param_groups[0]["lr"]
        dt = time.time() - t0
        print(
            f"[Epoch {epoch}] loss={avg_loss:.5f} PSNR={val_psnr:.3f} "
            f"SSIM={val_ssim:.4f} lr={lr:.2e} time={dt:.1f}s"
        )
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"{epoch},{avg_loss:.6f},{val_psnr:.4f},{val_ssim:.5f},{lr:.8f}\n")

        save_checkpoint(
            {
                "epoch": epoch,
                "model": model.state_dict(),
                "optimizer": optimizer.state_dict(),
                "best_psnr": best_psnr,
                "config": cfg,
            },
            str(Path(ckpt_dir) / "last.pth"),
        )

        if val_psnr >= best_psnr:
            best_psnr = val_psnr
            save_checkpoint(
                {
                    "epoch": epoch,
                    "model": model.state_dict(),
                    "optimizer": optimizer.state_dict(),
                    "best_psnr": best_psnr,
                    "config": cfg,
                },
                str(Path(ckpt_dir) / "best.pth"),
            )
            print(f"  -> best.pth diperbarui (PSNR={best_psnr:.3f})")

    print("[SELESAI] Pelatihan selesai. Pakai checkpoints/best.pth untuk ekspor ONNX.")


if __name__ == "__main__":
    main()
