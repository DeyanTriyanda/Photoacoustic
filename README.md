# Photoacoustic Imaging Software

Aplikasi desktop (Tkinter) untuk scanning fotoakustik: akuisisi audio,
kontrol stepper Arduino, citra 2D, dan inferensi deep learning.

**Full Python** (backend + frontend).

## Dependensi

Debian/Ubuntu (opsional untuk mic):
```bash
sudo apt install libportaudio2 python3-tk
```

```bash
pip install -r requirements.txt
python main.py
```

Windows PowerShell:
```powershell
pip install -r requirements.txt
python main.py
```

## Struktur

- `backend/` — audio, serial, jadwal scan, mapping, deep learning
- `frontend/` — widget Tkinter
- `assets/Real-ESRGAN-x2plus.onnx` — model Deep Learning default
- `firmware/` — Arduino

## Kolom kiri UI

1. Koneksi Serial (Port Arduino + Device Mic)
2. Rentang Frekuensi FFT
3. Sampling Points
4. Position Adjustment

Samplerate audio tetap **96000 Hz**.

## Tes

```bash
python -m pytest tests/ -q
```
