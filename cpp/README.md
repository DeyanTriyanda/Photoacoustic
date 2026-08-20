# Photoacoustic Imaging — C++ (susunan sama dengan versi Python)

C++17 + Qt6 Widgets/Charts/SerialPort + PortAudio.

## Struktur (sama seperti Python)

```
cpp/
  main.cpp
  backend/     # config, control, audio, mapping, timing, recorder, deep_learning
  frontend/    # ui_control, fft_widget, spatial_map_widget, deep_learning_widget
  CMakeLists.txt
firmware/      # tetap Arduino .ino (sudah C/C++)
assets/        # model ONNX bersama
```

## Build (Linux)

```bash
sudo apt install qt6-base-dev qt6-charts-dev qt6-serialport-dev portaudio19-dev cmake g++
cd cpp
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j
./build/PhotoacousticCpp
```

## Build (Windows + MSVC / Qt)

1. Install Qt 6 (Widgets, Charts, SerialPort) dan PortAudio.
2. Buka “Qt MSVC” / Developer PowerShell, lalu:

```powershell
cd cpp
cmake -S . -B build -DCMAKE_PREFIX_PATH="C:/Qt/6.x.x/msvc2019_64"
cmake --build build --config Release
.\build\Release\PhotoacousticCpp.exe
```

## Catatan

- Versi Python (`main.py`) tetap ada; ini port C++ paralel dengan alur UI yang sama.
- Samplerate audio: `AUDIO_SAMPLERATE = 192000` di `backend/config.hpp`.
- FFT: min = Set Modulasi, max = 20000 Hz (sama prinsip Python).
