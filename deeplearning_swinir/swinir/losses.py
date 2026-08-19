"""Loss untuk pelatihan SwinIR medis (L1 + opsional perceptual ringan)."""

from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F


class CharbonnierLoss(nn.Module):
    def __init__(self, eps=1e-6):
        super().__init__()
        self.eps = eps

    def forward(self, pred, target):
        return torch.mean(torch.sqrt((pred - target) ** 2 + self.eps ** 2))


class L1FFTLoss(nn.Module):
    """Opsional: penalti spektrum (berguna citra fotoakustik berpola frekuensi)."""

    def __init__(self, weight=0.05):
        super().__init__()
        self.weight = weight
        self.l1 = nn.L1Loss()

    def forward(self, pred, target):
        # FFT 2D magnitudo
        pred_f = torch.fft.rfft2(pred, norm="ortho")
        tgt_f = torch.fft.rfft2(target, norm="ortho")
        return self.weight * self.l1(torch.abs(pred_f), torch.abs(tgt_f))


class SwinIRLoss(nn.Module):
    def __init__(self, pixel="l1", fft_weight=0.0, charbonnier=False):
        super().__init__()
        if charbonnier:
            self.pixel = CharbonnierLoss()
        elif pixel == "l1":
            self.pixel = nn.L1Loss()
        else:
            self.pixel = nn.MSELoss()
        self.fft = L1FFTLoss(fft_weight) if fft_weight > 0 else None

    def forward(self, pred, target):
        loss = self.pixel(pred, target)
        extras = {"pixel": loss.detach()}
        if self.fft is not None:
            fl = self.fft(pred, target)
            loss = loss + fl
            extras["fft"] = fl.detach()
        return loss, extras
