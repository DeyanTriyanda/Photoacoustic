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
- `firmware/stepper_scan/` — Arduino 1 (USB ke laptop): motor + forward frekuensi laser
- `firmware/laser_modulasi/` — Arduino 2 (daya saja): modulasi laser D9

## Dua Arduino (stepper + laser)

Hanya **Arduino 1** yang muncul sebagai port Serial di laptop.
Arduino 2 mendapat tegangan (hub 2-in-1) tanpa data USB ke PC.

Wiring data (hardware UART):
- Arduino 1 **TX (pin 1)** → Arduino 2 **RX (pin 0)**
- **GND** bersama
- Saat upload ke Arduino 2: lepaskan dulu kabel ke pin 0

Alur frekuensi:
1. UI **Set Frekuensi** (mis. `17000`) → Python kirim `f=17000` ke Arduino 1
2. Arduino 1 mengulang `f=17000` ke Serial → keluar di **TX pin 1** ke Arduino 2
3. Arduino 2 memodulasi laser di D9 pada frekuensi itu (default `17000` Hz sampai perintah datang)

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
