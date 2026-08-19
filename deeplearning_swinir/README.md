# SwinIR Deep Learning — Fotoakustik (terpisah dari software utama)

Paket lengkap untuk **melatih, menguji, dan mengekspor** model **SwinIR**
(grayscale) khusus citra fotoakustik. Hasil akhir bisa dibungkus `.pth` /
`.onnx` lalu dimasukkan ke `assets/` software utama.

Folder ini **tidak** menggantikan `frontend/` / `backend/` aplikasi scanning.

## Struktur

```
deeplearning_swinir/
  swinir/           # library: model, dataset, loss, metrics
  configs/          # YAML pelatihan
  scripts/          # train / infer / export / prepare_dataset
  data/             # dataset LQ/HQ (Anda isi)
  checkpoints/      # hasil .pth
  outputs/          # log & hasil inferensi
```

## Instalasi (lingkungan terpisah disarankan)

```powershell
cd deeplearning_swinir
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

GPU NVIDIA: install PyTorch CUDA sesuai https://pytorch.org

## 1) Siapkan dataset

Dataset HQ Anda sudah ada di:

`E:\fotoakustik\Dataset DL PAI`

Jangan pindahkan foto ke `data/train/hq` manual. Jalankan script di bawah
dari folder `deeplearning_swinir` — script yang mengisi `data/train|val / hq|lq`.

**Super-resolution x2**
```powershell
python scripts/prepare_dataset.py --hq-dir "E:\fotoakustik\Dataset DL PAI" --out data --scale 2 --task classical_sr
```

**Denoising**
```powershell
python scripts/prepare_dataset.py --hq-dir "E:\fotoakustik\Dataset DL PAI" --out data --task denoising --noise-sigma 0.05
```

Hasil:
```
data/train/lq  data/train/hq
data/val/lq    data/val/hq
```

## 2) Latih

```powershell
python scripts/train.py --config configs/train_pa_x2.yaml
```

Opsional model lebih besar:
```powershell
python scripts/train.py --config configs/train_pa_x2_large.yaml
```

Resume:
```powershell
python scripts/train.py --config configs/train_pa_x2.yaml --resume checkpoints/last.pth
```

Output penting:
- `checkpoints/best.pth` — bobot terbaik (PSNR val)
- `checkpoints/last.pth` — epoch terakhir
- `outputs/logs/train_log.csv`

## 3) Inferensi uji

```powershell
python scripts/infer.py --ckpt checkpoints/best.pth --input path\uji.png --out outputs\pred.png
```

## 4) Bungkus untuk software utama

**ONNX** (disarankan untuk tab Deep Learning + onnxruntime):
```powershell
python scripts/export_onnx.py --ckpt checkpoints/best.pth --onnx ..\assets\SwinIR-x2-pa.onnx
```

**TorchScript** (opsional):
```powershell
python scripts/export_onnx.py --ckpt checkpoints/best.pth --torchscript checkpoints\swinir_x2.pt
```

Lalu di aplikasi utama: tab Deep Learning → **Pilih Model** → pilih `SwinIR-x2-pa.onnx`.

## Tips medis / fotoakustik

1. Pakai loss Charbonnier + `fft_weight` kecil (sudah di config) agar spektrum lebih terjaga.
2. Jangan andalkan GAN (Real-ESRGAN) untuk klaim kuantitatif; SwinIR lebih aman.
3. Mulai dari `train_pa_x2.yaml` (embed 96). Naik ke `large` hanya jika GPU kuat & data banyak.
4. Minimal puluhan–ratusan pasangan citra; augmentasi flip/rotasi sudah otomatis.
5. `img_size` / `patch_size` harus **kelipatan `window_size` (8)**.

## File yang berhubungan dengan software utama

| Folder / file | Peran |
|---|---|
| `deeplearning_swinir/` | Latih & ekspor (baru) |
| `assets/*.onnx` | Model siap pakai di UI |
| `frontend/deep_learning_widget.py` | Memuat ONNX (sudah ada) |

Tidak perlu mengubah `spatial_map_widget.py` untuk paket ini.
