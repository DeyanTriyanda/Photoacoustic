"""
Implementasi Python murni — dipakai jika _native_impl (.pyd/.so) gagal load.

API sama dengan ekstensi C++ supaya wrapper backend/*.py tidak berubah.
"""

from __future__ import annotations

import math
import threading
import time
from typing import Callable, Optional

import numpy as np

# --- Konstanta (samakan dengan native/include/pa_config.hpp) ---
POINT_DISTANCE_CM = 0.05
ROW_DISTANCE_CM = 0.05
DEFAULT_BAUDRATE = 115200
STEP_PER_CM_X = 1000.0
STEP_PER_CM_Y = 1000.0
JOG_STEP_DELAY_US = 300
SCAN_STEP_DELAY_US = 800
BREAK_TIME_MS = 1000
AUDIO_SAMPLERATE = 96000
TARGET_FREQ_HZ = 17000.0
DEFAULT_FREQ_TOLERANCE_HZ = 100.0
AUTO_TARGET_MIN_HZ = 100.0
AUTO_TARGET_MAX_HZ = 20000.0
NOISE_SIDEBAND_FACTOR = 5.0


def scan_speed_cm_s(scan_step_delay_us=SCAN_STEP_DELAY_US, step_per_cm_x=STEP_PER_CM_X):
    return 1_000_000 / (2 * scan_step_delay_us) / step_per_cm_x


def jog_speed_cm_s(jog_step_delay_us, step_per_cm_x=STEP_PER_CM_X):
    return 1_000_000 / (2 * jog_step_delay_us) / step_per_cm_x


def hitung_titik_per_baris(panjang_cm, point_distance_cm=POINT_DISTANCE_CM):
    if panjang_cm <= 0:
        return 0
    return round(panjang_cm / point_distance_cm) + 1


def hitung_jumlah_baris(lebar_cm, row_distance_cm=ROW_DISTANCE_CM):
    if lebar_cm <= 0:
        return 0
    return round(lebar_cm / row_distance_cm) + 1


def hitung_estimasi_durasi_s(
    x_cm,
    y_cm,
    point_distance_cm=POINT_DISTANCE_CM,
    row_distance_cm=ROW_DISTANCE_CM,
    scan_step_delay_us=SCAN_STEP_DELAY_US,
    step_per_cm_x=STEP_PER_CM_X,
    break_time_ms=BREAK_TIME_MS,
):
    titik = hitung_titik_per_baris(x_cm, point_distance_cm)
    baris = hitung_jumlah_baris(y_cm, row_distance_cm)
    if titik <= 0 or baris <= 0:
        return 0.0
    dwell_s = break_time_ms / 1000.0
    speed = scan_speed_cm_s(scan_step_delay_us, step_per_cm_x)
    travel_point_s = point_distance_cm / speed
    travel_row_s = row_distance_cm / speed
    total_diam = baris * titik * dwell_s
    total_gerak = baris * (titik - 1) * travel_point_s + (baris - 1) * travel_row_s
    return total_diam + total_gerak


def format_jam_menit(detik, bulatkan_ke_atas=False):
    if detik < 0:
        detik = 0
    menit_total = detik / 60.0
    menit_total = -(-menit_total // 1) if bulatkan_ke_atas else menit_total // 1
    jam, menit = divmod(int(menit_total), 60)
    return f"{jam} jam {menit} menit"


def extract_amplitude_at_frequency(freqs, magnitude, target_freq_hz, tolerance_hz=50.0):
    freqs = np.asarray(freqs)
    magnitude = np.asarray(magnitude)
    if len(freqs) == 0:
        return 0.0
    mask = np.abs(freqs - target_freq_hz) <= tolerance_hz
    if not mask.any():
        return 0.0
    return float(magnitude[mask].max())


def estimasi_noise_floor(freqs, mag, target_freq_hz, tolerance_hz, sideband_factor=5.0):
    jarak = np.abs(np.asarray(freqs) - target_freq_hz)
    mask = (jarak > tolerance_hz) & (jarak <= sideband_factor * tolerance_hz)
    if not mask.any():
        return 0.0
    return float(np.median(np.asarray(mag)[mask]))


def amplitude_matrix_to_grayscale(
    matrix, captured_mask=None, amp_min_fixed=None, amp_max_fixed=None
):
    matrix = np.asarray(matrix, dtype=np.float64)
    if amp_min_fixed is not None and amp_max_fixed is not None:
        amp_min, amp_max = float(amp_min_fixed), float(amp_max_fixed)
    else:
        if captured_mask is not None:
            mask = np.asarray(captured_mask, dtype=bool)
            nilai_valid = matrix[mask] if mask.any() else matrix.flatten()
        else:
            nilai_valid = matrix.flatten()
        if nilai_valid.size == 0:
            return np.zeros(matrix.shape, dtype=np.uint8), 0.0, 0.0
        amp_min = float(nilai_valid.min())
        amp_max = float(nilai_valid.max())
    if amp_max <= amp_min:
        return np.full(matrix.shape, 128, dtype=np.uint8), amp_min, amp_max
    normalized = (matrix - amp_min) / (amp_max - amp_min)
    normalized = np.clip(normalized, 0.0, 1.0)
    grayscale = np.clip(np.round(normalized * 255.0), 0, 255).astype(np.uint8)
    return grayscale, amp_min, amp_max


def _sd():
    try:
        import sounddevice as sd
    except OSError as e:
        raise RuntimeError(
            "PortAudio/sounddevice tidak tersedia. "
            "Install PortAudio lalu: pip install sounddevice"
        ) from e
    return sd


class AudioCaptureNative:
    def __init__(self):
        self.stream = None
        self._samplerate = 96000
        self.channels = 1
        self.device = None
        self.buffer_size = self._samplerate
        self._buffer = np.zeros(self.buffer_size, dtype=np.float32)
        self._lock = threading.Lock()
        self._capture_lock = threading.Lock()
        self._capture_event = threading.Event()
        self._capture_active = False
        self._capture_chunks = []
        self._capture_needed = 0
        self._capture_collected = 0
        self.running = False
        self._last_error = ""

    @property
    def samplerate(self):
        return self._samplerate

    @staticmethod
    def list_input_devices(force_rescan=True):
        try:
            sd = _sd()
        except RuntimeError:
            return []
        if force_rescan:
            try:
                sd._terminate()
            except Exception:
                pass
            try:
                sd._initialize()
            except Exception:
                pass
        hasil = []
        try:
            devices = sd.query_devices()
        except Exception:
            return hasil
        for idx, dev in enumerate(devices):
            if dev.get("max_input_channels", 0) > 0:
                label = (
                    f"{idx}: {dev['name']} "
                    f"({dev['max_input_channels']}ch, "
                    f"{int(dev['default_samplerate'])}Hz)"
                )
                hasil.append((idx, label))
        return hasil

    def start(self, device_index, samplerate=96000, channels=1,
              buffer_seconds=1.0, blocksize=1024):
        if self.running:
            self.stop()
        self.device = device_index
        self._samplerate = int(samplerate)
        self.channels = int(channels)
        self.buffer_size = max(int(samplerate * buffer_seconds), 1)
        with self._lock:
            self._buffer = np.zeros(self.buffer_size, dtype=np.float32)
        with self._capture_lock:
            self._capture_active = False
            self._capture_chunks = []
            self._capture_needed = 0
            self._capture_collected = 0
            self._capture_event.clear()

        def _callback(indata, frames, time_info, status):
            if status:
                self._last_error = str(status)
            mono = indata[:, 0] if indata.ndim > 1 else indata
            with self._lock:
                n = len(mono)
                if n >= self.buffer_size:
                    self._buffer[:] = mono[-self.buffer_size :]
                else:
                    self._buffer[:-n] = self._buffer[n:]
                    self._buffer[-n:] = mono
            with self._capture_lock:
                if not self._capture_active:
                    return
                remaining = self._capture_needed - self._capture_collected
                if remaining > 0:
                    take = mono[:remaining] if len(mono) > remaining else mono
                    self._capture_chunks.append(take.copy())
                    self._capture_collected += len(take)
                if self._capture_collected >= self._capture_needed:
                    self._capture_active = False
                    self._capture_event.set()

        try:
            sd = _sd()
            self.stream = sd.InputStream(
                device=device_index,
                channels=channels,
                samplerate=samplerate,
                blocksize=blocksize,
                dtype="float32",
                callback=_callback,
            )
            self.stream.start()
            self.running = True
            return True, f"Audio stream dimulai (device {device_index}, {samplerate} Hz) [Python fallback]"
        except Exception as e:
            self.running = False
            self.stream = None
            return False, str(e)

    def stop(self):
        self.running = False
        with self._capture_lock:
            self._capture_active = False
            self._capture_event.set()
        if self.stream is not None:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception:
                pass
        self.stream = None

    def is_running(self):
        return self.running

    def get_waveform(self):
        with self._lock:
            return self._buffer.copy()

    def _fft_core(self, data, window="hann", min_freq=0.0, max_freq=None):
        n = len(data)
        if n == 0:
            return np.array([]), np.array([])
        win = np.hanning(n) if window == "hann" else np.ones(n)
        windowed = data * win
        window_correction = 1.0 / np.mean(win) if np.mean(win) > 0 else 1.0
        spectrum = np.fft.rfft(windowed)
        freqs = np.fft.rfftfreq(n, d=1.0 / self._samplerate)
        magnitude = (np.abs(spectrum) / n) * 2.0 * window_correction
        magnitude[0] /= 2.0
        if max_freq is None:
            max_freq = self._samplerate / 2.0
        mask = (freqs >= min_freq) & (freqs <= max_freq)
        return freqs[mask], magnitude[mask]

    def get_fft(self, window="hann", min_freq=0.0, max_freq=None):
        return self._fft_core(self.get_waveform(), window=window, min_freq=min_freq, max_freq=max_freq)

    def compute_fft(self, data, window="hann", min_freq=0.0, max_freq=None):
        return self._fft_core(
            np.asarray(data, dtype=np.float32),
            window=window,
            min_freq=min_freq,
            max_freq=max_freq,
        )

    def get_peak(self, min_freq=20.0, max_freq=None):
        freqs, mag = self.get_fft(min_freq=min_freq, max_freq=max_freq)
        if len(mag) == 0:
            return 0.0, 0.0
        idx = int(np.argmax(mag))
        return float(freqs[idx]), float(mag[idx])

    def capture_samples(self, n, timeout=2.0):
        if not self.running or self.stream is None:
            raise RuntimeError("Audio stream belum berjalan -- panggil start() dulu")
        with self._capture_lock:
            self._capture_chunks = []
            self._capture_needed = int(n)
            self._capture_collected = 0
            self._capture_event.clear()
            self._capture_active = True
        ok = self._capture_event.wait(timeout)
        with self._capture_lock:
            self._capture_active = False
            if not ok:
                raise TimeoutError(
                    f"capture_samples({n}) timeout setelah {timeout}s"
                )
            if self._capture_chunks:
                data = np.concatenate(self._capture_chunks)[: self._capture_needed]
            else:
                data = np.zeros(0, dtype=np.float32)
        return data

    def last_error(self):
        return self._last_error


class SerialControllerNative:
    def __init__(self):
        self.ser = None
        self.read_thread = None
        self.running = False
        self._on_message: Optional[Callable[[str], None]] = None
        self._on_status_change: Optional[Callable[[bool], None]] = None

    def set_on_message(self, cb):
        self._on_message = cb

    def set_on_status_change(self, cb):
        self._on_status_change = cb

    @staticmethod
    def list_ports():
        try:
            import serial.tools.list_ports
        except Exception:
            return []
        hasil = []
        for p in serial.tools.list_ports.comports():
            deskripsi = p.description if p.description and p.description != "n/a" else ""
            label = f"{p.device} - {deskripsi}" if deskripsi else p.device
            hasil.append((p.device, label))
        return hasil

    def connect(self, port, baudrate=9600, timeout=1.0):
        try:
            import serial
        except Exception as e:
            return False, f"pyserial tidak tersedia: {e}"
        try:
            self.ser = serial.Serial(port, baudrate, timeout=timeout)
            time.sleep(2)
            self.running = True
            self.read_thread = threading.Thread(target=self._read_loop, daemon=True)
            self.read_thread.start()
            if self._on_status_change:
                self._on_status_change(True)
            return True, f"Terhubung ke {port} @ {baudrate} baud [Python fallback]"
        except Exception as e:
            self.ser = None
            return False, str(e)

    def disconnect(self):
        self.running = False
        if self.read_thread is not None:
            self.read_thread.join(timeout=1)
        if self.ser is not None and self.ser.is_open:
            self.ser.close()
        self.ser = None
        if self._on_status_change:
            self._on_status_change(False)

    def is_connected(self):
        return self.ser is not None and self.ser.is_open

    def send(self, command):
        if not self.is_connected():
            return False, "Belum terhubung ke Arduino"
        try:
            self.ser.write((command.strip() + "\n").encode("utf-8"))
            return True, f"Terkirim: {command}"
        except Exception as e:
            return False, str(e)

    def set_x(self, cm):
        return self.send(f"x={cm}")

    def set_y(self, cm):
        return self.send(f"y={cm}")

    def start_scan(self):
        return self.send("start")

    def stop_scan(self):
        return self.send("stop")

    def jog_kanan(self):
        return self.send("kanan")

    def jog_kiri(self):
        return self.send("kiri")

    def jog_maju(self):
        return self.send("maju")

    def jog_mundur(self):
        return self.send("mundur")

    def _read_loop(self):
        while self.running and self.ser is not None and self.ser.is_open:
            try:
                raw = self.ser.readline()
                if not raw:
                    continue
                line = raw.decode("utf-8", errors="replace").strip()
                if line and self._on_message:
                    self._on_message(line)
            except Exception as e:
                if self._on_message:
                    self._on_message(f"[ERROR BACA SERIAL] {e}")
                break
