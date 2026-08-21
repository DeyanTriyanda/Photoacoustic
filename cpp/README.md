# Photoacoustic Imaging — C++ (susunan sama dengan versi Python)

C++17 + Qt6 Widgets/PrintSupport/SerialPort + QCustomPlot + PortAudio.

## Struktur

```
cpp/
  main.cpp
  backend/
  frontend/
  third_party/qcustomplot/   # QCustomPlot 2.1.1 (waveform + FFT)
  CMakeLists.txt
```

Firmware Arduino tetap di folder `firmware/` repo utama (opsional saat develop UI).
Model ONNX (opsional DL) di `assets/`.

---

## Kenapa banyak error merah setelah copy?

Itu **normal**. Menyalin source saja belum cukup — editor belum tahu di mana header Qt (`QWidget`, `QCustomPlot`, …) dan PortAudio.

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
| **Qt 6** | Installer Qt Online. Centang: Qt 6.x → MSVC/MinGW 64-bit, **SerialPort** (+ PrintSupport ikut base). Charts **tidak** wajib — grafik pakai QCustomPlot (sudah di `third_party/`). |
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
sudo apt install qt6-base-dev qt6-serialport-dev libqt6printsupport6 portaudio19-dev cmake g++
cd cpp
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j
./build/PhotoacousticCpp
```

> Grafik waveform & FFT memakai **QCustomPlot** (vendored di `third_party/qcustomplot/`). Modul Qt Charts tidak dipakai.

---

## Assets (model + ikon)

Buat folder `assets/` di root project C++ Anda (`E:\Photoacoustic\assets\`):

```
E:\Photoacoustic\
  assets\
    Real-ESRGAN-x4plus.onnx   ← model default (auto, tanpa pilih)
    LogoPAI.png               ← ikon jendela
  build\
  frontend\
  ...
```

Tab Deep Learning memuat model dari `assets/` otomatis (prioritas: x4plus → x2plus).
