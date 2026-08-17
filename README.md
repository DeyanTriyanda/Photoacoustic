# Photoacoustic Imaging Software

Aplikasi desktop (Tkinter) untuk scanning fotoakustik: akuisisi audio,
kontrol stepper Arduino, citra 2D, dan inferensi deep learning.

**Frontend:** Python (Tkinter)  
**Backend inti:** C++ (PortAudio, FFTW, serial termios) via pybind11

## Dependensi sistem

Debian/Ubuntu:

```bash
sudo apt install g++ cmake python3-dev portaudio19-dev libfftw3-dev \
  libportaudio2 python3-tk
```

## Build backend C++

```bash
pip install -r requirements.txt
python setup.py build_ext --inplace
```

Ini menghasilkan `backend/_native*.so`.

## Jalankan

```bash
python main.py
```

Aplikasi Deep Learning mandiri (tanpa panel scan):

```bash
python deep_learning_app.py
```

## Struktur

- `native/` — sumber C++ (config, timing, mapping, FFT, audio, serial)
- `backend/` — wrapper Python tipis + orkestrasi scan + deep learning I/O
- `frontend/` — widget Tkinter
- `assets/Real-ESRGAN-x2plus.onnx` — model Deep Learning default

## Kolom kiri UI

1. Koneksi Serial (Port Arduino + Device Mic)  
2. Rentang Frekuensi FFT  
3. Sampling Points (X/Y + Set Area + Start + progres)  
4. Position Adjustment  

Samplerate audio tetap **96000 Hz** (tanpa UI).

## Tes

```bash
python setup.py build_ext --inplace
python -m pytest tests/ -q
```
