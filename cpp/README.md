# Photoacoustic Imaging — C++ (susunan sama dengan versi Python)

C++17 + Qt6 Widgets/Charts/SerialPort + PortAudio.

## Struktur

```
cpp/
  main.cpp
  backend/
  frontend/
  CMakeLists.txt
```

Firmware Arduino tetap di folder `firmware/` repo utama (opsional saat develop UI).
Model ONNX (opsional DL) di `assets/`.

---

## Kenapa banyak error merah setelah copy?

Itu **normal**. Menyalin source saja belum cukup — editor belum tahu di mana header Qt (`QWidget`, `QChart`, …) dan PortAudio.

Error merah hilang setelah:

1. **Install toolchain** (Qt6 + PortAudio + CMake + compiler)
2. **Configure CMake** sekali (supaya path include ketemu)
3. Buka folder **`cpp/`** sebagai workspace (bukan file satuan), dan pakai ekstensi **CMake Tools**

Kode yang di-copy biasanya sudah benar; yang merah = IntelliSense belum terhubung.

---

## Persiapan Windows (VS Code / Cursor / Visual Studio)

### 1) Install

| Komponen | Catatan |
|----------|---------|
| **Qt 6** | Installer Qt Online. Centang: Qt 6.x → MSVC 2019/2022 64-bit, **Charts**, **SerialPort** |
| **CMake** | https://cmake.org atau via Visual Studio |
| **MSVC** | “Desktop development with C++” di Visual Studio Installer |
| **PortAudio** | Build/install, atau letakkan di `C:\portaudio` (harus ada `include/portaudio.h` + `.lib`) |

### 2) Configure + build

Di **Developer PowerShell for VS** / terminal Cursor:

```powershell
cd E:\path\ke\PhotoacousticCpp   # folder hasil copy (= isi cpp/)
cmake -S . -B build `
  -DCMAKE_PREFIX_PATH="C:/Qt/6.7.3/msvc2019_64" `
  -DCMAKE_BUILD_TYPE=Release
cmake --build build --config Release
.\build\Release\PhotoacousticCpp.exe
```

Sesuaikan `CMAKE_PREFIX_PATH` ke folder Qt Anda (lihat di `C:\Qt\...`).

Jika PortAudio tidak ketemu otomatis:

```powershell
cmake -S . -B build `
  -DCMAKE_PREFIX_PATH="C:/Qt/6.7.3/msvc2019_64" `
  -DPORTAUDIO_INCLUDE_DIR="C:/portaudio/include" `
  -DPORTAUDIO_LIBRARY="C:/portaudio/lib/portaudio_x64.lib"
```

### 3) Hilangkan garis merah di Cursor / VS Code

1. Buka folder project (`cpp` / hasil copy) sebagai root workspace
2. Install ekstensi: **CMake Tools**, **C/C++** (Microsoft)
3. Command Palette → **CMake: Configure**
4. Pilih kit **Visual Studio / MSVC**, set `CMAKE_PREFIX_PATH` seperti di atas
5. Setelah configure sukses, IntelliSense biasanya bersih

Jangan mengandalkan “Open File” tanpa CMake — `#include <QWidget>` pasti merah.

---

## Build (Linux)

```bash
sudo apt install qt6-base-dev qt6-charts-dev qt6-serialport-dev portaudio19-dev cmake g++
cd cpp
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j
./build/PhotoacousticCpp
```

---

## Catatan

- Versi Python (`main.py`) terpisah; ini port C++ paralel.
- Samplerate: `AUDIO_SAMPLERATE = 192000` di `backend/config.hpp`.
- FFT: min = Set Modulasi, max = 20000 Hz; Skala Log memakai ylim adaptif (sama Python).
- Refresh FFT UI ~60 FPS (`FFT_UPDATE_INTERVAL_MS = 16`) + FFT radix-2.
- Jog: tekan = gerak, lepas = stop.
- Folder `build/` tidak perlu di-copy — selalu generate ulang dengan `cmake`.
