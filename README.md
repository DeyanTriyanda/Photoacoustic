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
- `assets/Real-ESRGAN-x2plus.onnx` — model Deep Learning default (wajib ada untuk inferensi)

## Kolom kiri UI

1. Koneksi Serial (Arduino Stepper)  
2. Audio Input  
3. Frekuensi Target (+ Port Laser)  
4. Sampling Points (X/Y + Set Area + Start + progres)  
5. Position Adjustment  

Rentang FFT (0..20 kHz) diset di latar belakang (tanpa UI).  
Frekuensi target UI dikirim ke Arduino laser (`f=17000`) dan dipakai ekstraksi mic.

## Tes

```bash
python -m pytest tests/ -q
```
