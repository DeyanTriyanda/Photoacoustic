"""
Implementasi SwinIR (Swin Transformer for Image Restoration) — grayscale medis.

Referensi: Liang et al., ICCVW 2021 (SwinIR).
Mendukung classical_sr (x2/x4) dan denoising (x1).
"""

from __future__ import annotations

import math
from typing import Optional, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F


def window_partition(x: torch.Tensor, window_size: int):
    b, h, w, c = x.shape
    x = x.view(b, h // window_size, window_size, w // window_size, window_size, c)
    return x.permute(0, 1, 3, 2, 4, 5).contiguous().view(-1, window_size, window_size, c)


def window_reverse(windows: torch.Tensor, window_size: int, h: int, w: int):
    b = int(windows.shape[0] / (h * w / window_size / window_size))
    x = windows.view(b, h // window_size, w // window_size, window_size, window_size, -1)
    return x.permute(0, 1, 3, 2, 4, 5).contiguous().view(b, h, w, -1)


class WindowAttention(nn.Module):
    def __init__(self, dim, window_size, num_heads, qkv_bias=True, attn_drop=0.0, proj_drop=0.0):
        super().__init__()
        self.window_size = window_size if isinstance(window_size, tuple) else (window_size, window_size)
        self.num_heads = num_heads
        head_dim = dim // num_heads
        self.scale = head_dim ** -0.5

        self.relative_position_bias_table = nn.Parameter(
            torch.zeros((2 * self.window_size[0] - 1) * (2 * self.window_size[1] - 1), num_heads)
        )
        coords_h = torch.arange(self.window_size[0])
        coords_w = torch.arange(self.window_size[1])
        coords = torch.stack(torch.meshgrid([coords_h, coords_w], indexing="ij"))
        coords_flatten = torch.flatten(coords, 1)
        relative_coords = coords_flatten[:, :, None] - coords_flatten[:, None, :]
        relative_coords = relative_coords.permute(1, 2, 0).contiguous()
        relative_coords[:, :, 0] += self.window_size[0] - 1
        relative_coords[:, :, 1] += self.window_size[1] - 1
        relative_coords[:, :, 0] *= 2 * self.window_size[1] - 1
        self.register_buffer("relative_position_index", relative_coords.sum(-1))

        self.qkv = nn.Linear(dim, dim * 3, bias=qkv_bias)
        self.attn_drop = nn.Dropout(attn_drop)
        self.proj = nn.Linear(dim, dim)
        self.proj_drop = nn.Dropout(proj_drop)
        nn.init.trunc_normal_(self.relative_position_bias_table, std=0.02)

    def forward(self, x, mask: Optional[torch.Tensor] = None):
        b_, n, c = x.shape
        qkv = (
            self.qkv(x)
            .reshape(b_, n, 3, self.num_heads, c // self.num_heads)
            .permute(2, 0, 3, 1, 4)
        )
        q, k, v = qkv[0], qkv[1], qkv[2]
        attn = (q * self.scale) @ k.transpose(-2, -1)

        relative_position_bias = (
            self.relative_position_bias_table[self.relative_position_index.view(-1)]
            .view(
                self.window_size[0] * self.window_size[1],
                self.window_size[0] * self.window_size[1],
                -1,
            )
            .permute(2, 0, 1)
            .contiguous()
        )
        attn = attn + relative_position_bias.unsqueeze(0)

        if mask is not None:
            n_w = mask.shape[0]
            attn = attn.view(b_ // n_w, n_w, self.num_heads, n, n)
            attn = attn + mask.unsqueeze(1).unsqueeze(0)
            attn = attn.view(-1, self.num_heads, n, n)

        attn = self.attn_drop(F.softmax(attn, dim=-1))
        x = (attn @ v).transpose(1, 2).reshape(b_, n, c)
        return self.proj_drop(self.proj(x))


class MLP(nn.Module):
    def __init__(self, dim, mlp_ratio=4.0, drop=0.0):
        super().__init__()
        hidden = int(dim * mlp_ratio)
        self.fc1 = nn.Linear(dim, hidden)
        self.act = nn.GELU()
        self.fc2 = nn.Linear(hidden, dim)
        self.drop = nn.Dropout(drop)

    def forward(self, x):
        return self.drop(self.fc2(self.drop(self.act(self.fc1(x)))))


class SwinTransformerBlock(nn.Module):
    def __init__(self, dim, num_heads, window_size=8, shift_size=0, mlp_ratio=4.0, drop=0.0, attn_drop=0.0):
        super().__init__()
        self.dim = dim
        self.window_size = window_size
        self.shift_size = shift_size
        self.norm1 = nn.LayerNorm(dim)
        self.attn = WindowAttention(dim, window_size, num_heads, attn_drop=attn_drop, proj_drop=drop)
        self.norm2 = nn.LayerNorm(dim)
        self.mlp = MLP(dim, mlp_ratio, drop)

    def forward(self, x, x_size: Tuple[int, int]):
        h, w = x_size
        b, _, c = x.shape
        shortcut = x
        x = self.norm1(x).view(b, h, w, c)

        ws = self.window_size
        ss = self.shift_size
        if min(h, w) <= ws:
            ss = 0
            ws = min(h, w)

        if ss > 0:
            shifted = torch.roll(x, shifts=(-ss, -ss), dims=(1, 2))
            img_mask = x.new_zeros((1, h, w, 1))
            h_slices = (slice(0, -ws), slice(-ws, -ss), slice(-ss, None))
            w_slices = (slice(0, -ws), slice(-ws, -ss), slice(-ss, None))
            cnt = 0
            for hs in h_slices:
                for wsl in w_slices:
                    img_mask[:, hs, wsl, :] = cnt
                    cnt += 1
            mask_windows = window_partition(img_mask, ws).view(-1, ws * ws)
            attn_mask = mask_windows.unsqueeze(1) - mask_windows.unsqueeze(2)
            attn_mask = attn_mask.masked_fill(attn_mask != 0, float(-100.0)).masked_fill(
                attn_mask == 0, float(0.0)
            )
        else:
            shifted = x
            attn_mask = None

        x_windows = window_partition(shifted, ws).view(-1, ws * ws, c)
        attn_windows = self.attn(x_windows, mask=attn_mask).view(-1, ws, ws, c)
        shifted = window_reverse(attn_windows, ws, h, w)
        if ss > 0:
            x = torch.roll(shifted, shifts=(ss, ss), dims=(1, 2))
        else:
            x = shifted

        x = x.view(b, h * w, c)
        x = shortcut + x
        x = x + self.mlp(self.norm2(x))
        return x


class RSTB(nn.Module):
    def __init__(self, dim, depth, num_heads, window_size, mlp_ratio=4.0, drop=0.0, attn_drop=0.0, rescale=0.2):
        super().__init__()
        self.blocks = nn.ModuleList(
            [
                SwinTransformerBlock(
                    dim,
                    num_heads,
                    window_size,
                    shift_size=0 if i % 2 == 0 else window_size // 2,
                    mlp_ratio=mlp_ratio,
                    drop=drop,
                    attn_drop=attn_drop,
                )
                for i in range(depth)
            ]
        )
        self.conv = nn.Conv2d(dim, dim, 3, 1, 1)
        self.rescale = rescale

    def forward(self, x, x_size: Tuple[int, int]):
        b, _, c = x.shape
        h, w = x_size
        shortcut = x
        for blk in self.blocks:
            x = blk(x, x_size)
        res = self.conv(x.transpose(1, 2).view(b, c, h, w)).flatten(2).transpose(1, 2)
        return shortcut + res * self.rescale


class Upsample(nn.Sequential):
    def __init__(self, scale, num_feat):
        m = []
        if (scale & (scale - 1)) == 0:
            for _ in range(int(math.log2(scale))):
                m += [nn.Conv2d(num_feat, 4 * num_feat, 3, 1, 1), nn.PixelShuffle(2)]
        elif scale == 3:
            m += [nn.Conv2d(num_feat, 9 * num_feat, 3, 1, 1), nn.PixelShuffle(3)]
        else:
            raise ValueError(f"scale={scale} tidak didukung")
        super().__init__(*m)


class SwinIR(nn.Module):
    def __init__(
        self,
        img_size=64,
        in_chans=1,
        embed_dim=96,
        depths=(6, 6, 6, 6),
        num_heads=(6, 6, 6, 6),
        window_size=8,
        mlp_ratio=4.0,
        drop_rate=0.0,
        attn_drop_rate=0.0,
        upscale=2,
        img_range=1.0,
        task="classical_sr",
    ):
        super().__init__()
        self.img_range = img_range
        self.window_size = window_size
        self.task = task
        self.upscale = 1 if task == "denoising" else int(upscale)
        self.embed_dim = embed_dim

        self.conv_first = nn.Conv2d(in_chans, embed_dim, 3, 1, 1)
        self.layers = nn.ModuleList(
            [
                RSTB(
                    embed_dim,
                    depths[i],
                    num_heads[i],
                    window_size,
                    mlp_ratio,
                    drop_rate,
                    attn_drop_rate,
                )
                for i in range(len(depths))
            ]
        )
        self.norm = nn.LayerNorm(embed_dim)
        self.conv_after_body = nn.Conv2d(embed_dim, embed_dim, 3, 1, 1)

        if self.upscale > 1:
            self.conv_before_upsample = nn.Sequential(
                nn.Conv2d(embed_dim, 64, 3, 1, 1),
                nn.LeakyReLU(inplace=True),
            )
            self.upsample = Upsample(self.upscale, 64)
            self.conv_last = nn.Conv2d(64, in_chans, 3, 1, 1)
        else:
            self.conv_last = nn.Conv2d(embed_dim, in_chans, 3, 1, 1)

        self.apply(self._init_weights)

    @staticmethod
    def _init_weights(m):
        if isinstance(m, nn.Linear):
            nn.init.trunc_normal_(m.weight, std=0.02)
            if m.bias is not None:
                nn.init.constant_(m.bias, 0)
        elif isinstance(m, nn.LayerNorm):
            nn.init.constant_(m.bias, 0)
            nn.init.constant_(m.weight, 1.0)

    def check_image_size(self, x):
        _, _, h, w = x.size()
        mod_pad_h = (self.window_size - h % self.window_size) % self.window_size
        mod_pad_w = (self.window_size - w % self.window_size) % self.window_size
        return F.pad(x, (0, mod_pad_w, 0, mod_pad_h), mode="reflect")

    def forward(self, x):
        h0, w0 = x.shape[2:]
        x = self.check_image_size(x) * self.img_range

        x_first = self.conv_first(x)
        b, c, h, w = x_first.shape
        feat = x_first.flatten(2).transpose(1, 2)
        for layer in self.layers:
            feat = layer(feat, (h, w))
        feat = self.norm(feat).transpose(1, 2).view(b, c, h, w)
        res = self.conv_after_body(feat) + x_first

        if self.upscale > 1:
            out = self.conv_last(self.upsample(self.conv_before_upsample(res)))
        else:
            out = self.conv_last(res)

        out = out / self.img_range
        return out[:, :, : h0 * self.upscale, : w0 * self.upscale]


def build_swinir(cfg: dict) -> SwinIR:
    return SwinIR(
        img_size=int(cfg.get("img_size", 64)),
        in_chans=int(cfg.get("in_chans", 1)),
        embed_dim=int(cfg.get("embed_dim", 96)),
        depths=tuple(cfg.get("depths", [6, 6, 6, 6])),
        num_heads=tuple(cfg.get("num_heads", [6, 6, 6, 6])),
        window_size=int(cfg.get("window_size", 8)),
        mlp_ratio=float(cfg.get("mlp_ratio", 4.0)),
        upscale=int(cfg.get("upscale", 2)),
        img_range=float(cfg.get("img_range", 1.0)),
        task=str(cfg.get("task", "classical_sr")),
    )
