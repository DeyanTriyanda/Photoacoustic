# Folder assets

Letakkan file berikut di folder ini (sejajar dengan aplikasi):

## Deep Learning (wajib untuk tab DL)
- `Real-ESRGAN-x4plus.onnx` — **model default** (auto-load, tanpa pilih manual)
- `Real-ESRGAN-x2plus.onnx` — alternatif (dipakai jika x4plus tidak ada)

## Ikon jendela
- `LogoPAI.png` (atau `logoPAI.png` / `logo.png`)

## Contoh lokasi

**Repo / Python:**
```
Photoacoustic/
  assets/
    Real-ESRGAN-x4plus.onnx
    LogoPAI.png
  main.py
  cpp/
```

**Salinan C++ di `E:\Photoacoustic`:**
```
E:\Photoacoustic\
  assets\
    Real-ESRGAN-x4plus.onnx
    LogoPAI.png
  build\PhotoacousticCpp.exe
  frontend\
  backend\
```

Aplikasi mencari `assets/` di samping folder build / project root secara otomatis.
