# Data — hasil `prepare_dataset.py`

## Sumber HQ Anda

| Tempat | Path |
|---|---|
| PC | `E:\fotoakustik\Dataset DL PAI` |
| Google Drive | `MyDrive/Dataset DL PAI` → di Colab: `/content/drive/MyDrive/Dataset DL PAI` |

Program: `E:\fotoakustik\Photoacoustic DeepLearning SwinIR`

Jangan isi `train/hq` manual. Contoh Colab:

```python
!python scripts/prepare_dataset.py --hq-dir "/content/drive/MyDrive/Dataset DL PAI" --out data --scale 2
```

Hasil otomatis:

```
data/train/hq
data/train/lq
data/val/hq
data/val/lq
```
