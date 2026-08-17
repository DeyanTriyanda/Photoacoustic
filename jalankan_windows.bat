@echo off
cd /d "%~dp0"

echo [1/3] Hapus native C++ rusak (jika ada)...
del /q backend\_native_impl*.pyd 2>nul
del /q backend\_native_impl*.so 2>nul
del /q backend\_native*.so 2>nul

echo [2/3] Install dependensi Python...
python -m pip install numpy sounddevice pyserial matplotlib pillow onnxruntime pybind11

echo [3/3] Jalankan aplikasi (Windows = Python fallback)...
python main.py
pause
