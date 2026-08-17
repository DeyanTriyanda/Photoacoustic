"""
Konstanta yang WAJIB sama dengan #define / protokol firmware Arduino.

  - Stepper : firmware/stepper_scan/
  - Laser   : firmware/laser_modulasi/  (frekuensi 0..MAX_TARGET_FREQ_HZ via Serial)

Frekuensi target UI = frekuensi modulasi laser = frekuensi ekstraksi mic.
"""

# --- Stepper ---
POINT_DISTANCE_CM = 0.05
ROW_DISTANCE_CM = 0.05
DEFAULT_BAUDRATE = 115200

STEP_PER_CM_X = 1000.0
STEP_PER_CM_Y = 1000.0
JOG_STEP_DELAY_US = 300
SCAN_STEP_DELAY_US = 800
BREAK_TIME_MS = 1000

# --- Frekuensi (laser + mic, harus sama) ---
TARGET_FREQ_HZ = 17000.0          # default UI / scan
MAX_TARGET_FREQ_HZ = 20000.0      # batas atas; > ini = peringatan
MIN_TARGET_FREQ_HZ = 0.1          # batas bawah praktis (firmware)

# Rentang FFT di latar belakang (TIDAK ditampilkan di UI)
FFT_MIN_HZ = 0.0
FFT_MAX_HZ = 20000.0

DEFAULT_FREQ_TOLERANCE_HZ = 100.0

# Deteksi otomatis (mode auto, jika target_freq_hz=None)
AUTO_TARGET_MIN_HZ = 100.0
AUTO_TARGET_MAX_HZ = MAX_TARGET_FREQ_HZ

NOISE_SIDEBAND_FACTOR = 5.0
