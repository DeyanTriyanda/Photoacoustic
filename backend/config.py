"""
Konstanta yang WAJIB sama dengan #define firmware Arduino.

  - Stepper : firmware/stepper_scan/stepper_scan.ino
              (USB Serial ke laptop @ DEFAULT_BAUDRATE)
              SoftSerial TX pin 10 @ 9600 → Arduino laser RX
  - Laser   : firmware/laser_modulasi/laser_modulasi.ino
              (TARGET_FREQ_HZ == LASER_MOD_FREQ_HZ default)
              Terima "f=<Hz>" dari Arduino stepper

Satu sumber kebenaran -- diimpor ui_control, SpatialScanRecorder,
SpatialMapWidget. Jangan hardcode ulang di tempat lain.
"""

# --- Stepper (harus sama dengan firmware stepper) ---
POINT_DISTANCE_CM = 0.05
ROW_DISTANCE_CM = 0.05
DEFAULT_BAUDRATE = 115200

STEP_PER_CM_X = 1000.0
STEP_PER_CM_Y = 1000.0
JOG_STEP_DELAY_US = 300
SCAN_STEP_DELAY_US = 800
BREAK_TIME_MS = 1000

# --- Audio (tetap, tanpa UI) ---
AUDIO_SAMPLERATE = 96000

# --- Laser / ekstraksi amplitudo ---
TARGET_FREQ_HZ = 17000.0
DEFAULT_FREQ_TOLERANCE_HZ = 100.0

# --- Deteksi otomatis frekuensi target saat scan (bukan batas plot FFT) ---
# Batas bawah default; saat scan bisa diganti dari min FFT di UI.
AUTO_TARGET_MIN_HZ = 100.0
AUTO_TARGET_MAX_HZ = 20000.0

# Lebar sideband estimasi lantai derau (x toleransi jendela target).
NOISE_SIDEBAND_FACTOR = 5.0
