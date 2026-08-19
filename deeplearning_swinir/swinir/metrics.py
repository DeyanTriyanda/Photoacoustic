"""Metrik evaluasi: PSNR / SSIM (grayscale)."""

from __future__ import annotations

import torch
import torch.nn.functional as F


def psnr(pred: torch.Tensor, target: torch.Tensor, data_range=1.0) -> float:
    pred = pred.detach().clamp(0, data_range)
    target = target.detach().clamp(0, data_range)
    mse = torch.mean((pred - target) ** 2).item()
    if mse <= 1e-12:
        return 99.0
    import math
    return 10.0 * math.log10((data_range ** 2) / mse)


def ssim(pred: torch.Tensor, target: torch.Tensor, data_range=1.0, window_size=11) -> float:
    """SSIM batch-mean sederhana."""
    pred = pred.detach().clamp(0, data_range)
    target = target.detach().clamp(0, data_range)
    channel = pred.size(1)
    sigma = 1.5
    coords = torch.arange(window_size, dtype=pred.dtype, device=pred.device) - window_size // 2
    g = torch.exp(-(coords ** 2) / (2 * sigma ** 2))
    g = g / g.sum()
    kernel = (g[:, None] * g[None, :]).unsqueeze(0).unsqueeze(0)
    kernel = kernel.repeat(channel, 1, 1, 1)

    pad = window_size // 2
    mu1 = F.conv2d(pred, kernel, padding=pad, groups=channel)
    mu2 = F.conv2d(target, kernel, padding=pad, groups=channel)
    mu1_sq, mu2_sq, mu12 = mu1 ** 2, mu2 ** 2, mu1 * mu2
    sigma1_sq = F.conv2d(pred * pred, kernel, padding=pad, groups=channel) - mu1_sq
    sigma2_sq = F.conv2d(target * target, kernel, padding=pad, groups=channel) - mu2_sq
    sigma12 = F.conv2d(pred * target, kernel, padding=pad, groups=channel) - mu12

    c1 = (0.01 * data_range) ** 2
    c2 = (0.03 * data_range) ** 2
    ssim_map = ((2 * mu12 + c1) * (2 * sigma12 + c2)) / (
        (mu1_sq + mu2_sq + c1) * (sigma1_sq + sigma2_sq + c2)
    )
    return float(ssim_map.mean().item())
