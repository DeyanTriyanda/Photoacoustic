"""
Konstanta yang WAJIB sama dengan #define firmware Arduino.

  - Stepper : firmware/stepper_scan/stepper_scan.ino
              (USB Serial ke laptop @ DEFAULT_BAUDRATE)
              SoftSerial TX pin 10 @ 9600 → Arduino laser SoftSerial RX pin 8
              + kabel GND bersama ke Arduino laser
  - Laser   : firmware/laser_modulasi/laser_modulasi.ino
              (TARGET_FREQ_HZ == LASER_MOD_FREQ_HZ default)
              Terima "f=<Hz>" di pin 8; modulasi Timer1 di D9 (termasuk 2 Hz)

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
AUDIO_SAMPLERATE = 192000

# --- Laser / ekstraksi amplitudo ---
TARGET_FREQ_HZ = 17000.0
DEFAULT_FREQ_TOLERANCE_HZ = 100.0

# --- Deteksi otomatis frekuensi target saat scan (bukan batas plot FFT) ---
# Batas bawah default; saat scan bisa diganti dari min FFT di UI.
AUTO_TARGET_MIN_HZ = 100.0
AUTO_TARGET_MAX_HZ = 20000.0

# Lebar sideband estimasi lantai derau (x toleransi jendela target).
NOISE_SIDEBAND_FACTOR = 5.0

# --- Pipeline citra Lock-In + Hilbert + DAS (1 laser, 1 mic scanning) ---
# True: amplitudo titik dari lock-in+Hilbert; di akhir scan DAS membentuk citra.
USE_LOCKIN_HILBERT_DAS = True
# LPF setelah mixing lock-in (Hz); semakin kecil semakin sempit pita noise.
LOCK_IN_LP_HZ = 200.0
# Kecepatan suara medium (m/s). Air/gel ~1500; udara ~343.
SOUND_SPEED_M_S = 1500.0
# Panjang A-line per titik (sample) untuk envelope + DAS.
A_LINE_SAMPLES = 4096
