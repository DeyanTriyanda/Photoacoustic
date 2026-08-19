# Panduan Google Colab — path Anda

## Lokasi yang dipakai

| Apa | Di mana |
|---|---|
| Program SwinIR (PC) | `E:\fotoakustik\Photoacoustic DeepLearning SwinIR` |
| Dataset HQ (PC) | `E:\fotoakustik\Dataset DL PAI` |
| Dataset HQ (Google Drive) | `MyDrive/Dataset DL PAI` |

Di Colab, path Drive menjadi:

`/content/drive/MyDrive/Dataset DL PAI`

---

## Cell 1 — Mount Drive

```python
from google.colab import drive
drive.mount('/content/drive')
```

## Cell 2 — Masuk ke folder program

**Opsi A** — program sudah diupload ke Drive (disarankan):

Upload isi folder  
`E:\fotoakustik\Photoacoustic DeepLearning SwinIR`  
ke Drive, misalnya ke `MyDrive/Photoacoustic DeepLearning SwinIR`, lalu:

```python
%cd "/content/drive/MyDrive/Photoacoustic DeepLearning SwinIR"
!pip install -r requirements.txt
```

**Opsi B** — ambil dari GitHub (folder di repo bernama `deeplearning_swinir`):

```python
%cd /content
!git clone -b cursor/refactor-fotoakustik-light-c588 https://github.com/DeyanTriyanda/Photoacoustic.git
%cd /content/Photoacoustic/deeplearning_swinir
!pip install -r requirements.txt
```

## Cell 3 — Siapkan pasangan LQ/HQ dari dataset Drive

```python
!python scripts/prepare_dataset.py --hq-dir "/content/drive/MyDrive/Dataset DL PAI" --out data --scale 2
```

## Cell 4 — Latih

```python
!python scripts/train.py --config configs/train_pa_x2.yaml
```

## Cell 5 — Ekspor ONNX (opsional)

```python
!python scripts/export_onnx.py --ckpt checkpoints/best.pth --onnx "/content/drive/MyDrive/SwinIR-x2-pa.onnx"
```

---

## Catatan Colab

- Jangan tulis `cd folder` di cell Python biasa → error. Pakai `%cd` atau awali perintah shell dengan `!`.
- Runtime → Change runtime type → **GPU**.
- Dataset sudah di Drive: **tidak perlu** upload ulang dari `E:\...` setiap kali.
