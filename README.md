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
- `frontend/` — widget Tkinter (termasuk tab **Cek Noise Plat**)
- `assets/Real-ESRGAN-x2plus.onnx` / `x4plus.onnx` — model Deep Learning
- `firmware/stepper_scan/` — Arduino 1 (USB ke laptop): motor + forward frekuensi laser
- `firmware/laser_modulasi/` — Arduino 2 (daya saja): modulasi laser D9

## Dua Arduino (stepper + laser)

Hanya **Arduino 1** yang muncul sebagai port Serial di laptop.
Arduino 2 mendapat tegangan (hub 2-in-1) tanpa data USB ke PC.

Wiring data:
- Arduino 1 **pin 10** → Arduino 2 **pin 8** (bukan pin 0)
- **GND bersama**: sambungkan pin **GND** Arduino 1 ke pin **GND** Arduino 2
- Jangan pakai pin 0 Arduino 2 untuk data (bentrok USB; perintah `f=` bisa gagal)
- Saat upload ke Arduino 2: kabel data boleh tetap di pin 8

Alur frekuensi:
1. UI **Frekuensi Modulasi Laser** → **Set Modulasi** (mis. `2` atau `17000`)
2. Python otomatis: FFT min, target citra, kirim `f=` ke Arduino 1
3. Arduino 1 SoftSerial pin 10 → Arduino 2 pin 8; Timer1 memodulasi laser di **D9**

## Kolom kiri UI

1. Koneksi Serial (Port Arduino + Device Mic)
2. Frekuensi Modulasi Laser — **satu nilai** untuk:
   - modulasi laser (Arduino 1 → Arduino 2)
   - min plot FFT
   - frekuensi target citra 2D
3. Sampling Points
4. Position Adjustment

Alur: isi mis. `17000` → **Set Modulasi** → Python + Arduino ikut nilai itu.

## Tab Cek Noise Plat

Untuk mengukur frekuensi noise saat laser mengenai tatakan (tanpa sampel):
1. Connect mic + Set Modulasi + arahkan laser ke plat
2. Buka tab **Cek Noise Plat** → **Ambil Spektrum Noise**
3. Lihat daftar puncak (label `plat` = di bawah frekuensi set)

Samplerate audio tetap **96000 Hz**.

## Tes

```bash
python -m pytest tests/ -q
```
