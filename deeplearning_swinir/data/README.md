# Data — hasil `prepare_dataset.py`

Sumber foto HQ (jangan diubah manual ke sini):

`E:\fotoakustik\Dataset DL PAI`

Setelah menjalankan:

```powershell
python scripts/prepare_dataset.py --hq-dir "E:\fotoakustik\Dataset DL PAI" --out data --scale 2
```

folder ini terisi otomatis:

```
data/train/hq
data/train/lq
data/val/hq
data/val/lq
```
