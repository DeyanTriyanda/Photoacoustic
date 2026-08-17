# Photoacoustic Imaging Software

Aplikasi desktop (Tkinter) untuk scanning fotoakustik: akuisisi audio,
kontrol stepper Arduino, citra 2D, dan inferensi deep learning.

## Jalankan

Sistem butuh PortAudio (untuk sounddevice), mis. di Debian/Ubuntu:
`sudo apt install libportaudio2 python3-tk`

```bash
pip install -r requirements.txt
python main.py
```

Aplikasi Deep Learning mandiri (tanpa panel scan):

```bash
python deep_learning_app.py
```

## Struktur

- `backend/` — audio, serial, jadwal scan, mapping, deep learning (tanpa GUI)
- `frontend/` — widget Tkinter
- `backend/config.py` — konstanta yang harus sama dengan `#define` firmware

## Tes

```bash
python -m pytest tests/ -q
```
