"""
Akuisisi sinyal audio (sounddevice/PortAudio) untuk sistem fotoakustik.
"""

import threading

import numpy as np

from backend.spatial_mapping import extract_amplitude_at_frequency


def _sd():
    try:
        import sounddevice as sd
    except OSError as e:
        raise RuntimeError(
            "PortAudio/sounddevice tidak tersedia. "
            "Install library sistem PortAudio lalu: pip install sounddevice"
        ) from e
    return sd


class AudioCapture:
    """Streaming audio input + FFT. on_error(str) untuk warning/xrun non-fatal."""

    def __init__(self, on_error=None):
        self.stream = None
        self.samplerate = 96000
        self.channels = 1
        self.device = None

        self.buffer_size = self.samplerate
        self._buffer = np.zeros(self.buffer_size, dtype=np.float32)
        self._lock = threading.Lock()

        self._capture_lock = threading.Lock()
        self._capture_event = threading.Event()
        self._capture_active = False
        self._capture_chunks = []
        self._capture_needed = 0
        self._capture_collected = 0

        self.on_error = on_error
        self.running = False

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
        self.samplerate = samplerate
        self.channels = channels
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
            if status and self.on_error:
                self.on_error(str(status))
            mono = indata[:, 0] if indata.ndim > 1 else indata

            with self._lock:
                n = len(mono)
                if n >= self.buffer_size:
                    self._buffer[:] = mono[-self.buffer_size:]
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
            return True, f"Audio stream dimulai (device {device_index}, {samplerate} Hz)"
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

        if window == "hann":
            win = np.hanning(n)
        else:
            win = np.ones(n)

        windowed = data * win
        window_correction = 1.0 / np.mean(win) if np.mean(win) > 0 else 1.0

        spectrum = np.fft.rfft(windowed)
        freqs = np.fft.rfftfreq(n, d=1.0 / self.samplerate)

        magnitude = (np.abs(spectrum) / n) * 2.0 * window_correction
        magnitude[0] /= 2.0

        if max_freq is None:
            max_freq = self.samplerate / 2.0

        mask = (freqs >= min_freq) & (freqs <= max_freq)
        return freqs[mask], magnitude[mask]

    def get_fft(self, window="hann", min_freq=0.0, max_freq=None):
        return self._fft_core(
            self.get_waveform(), window=window, min_freq=min_freq, max_freq=max_freq
        )

    def compute_fft(self, data, window="hann", min_freq=0.0, max_freq=None):
        return self._fft_core(
            np.asarray(data, dtype=np.float32),
            window=window, min_freq=min_freq, max_freq=max_freq,
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
                    f"capture_samples({n}) timeout setelah {timeout}s -- "
                    "cek apakah stream audio masih hidup / device tidak lepas"
                )
            if self._capture_chunks:
                data = np.concatenate(self._capture_chunks)[: self._capture_needed]
            else:
                data = np.zeros(0, dtype=np.float32)

        return data

    def capture_and_measure(self, n, target_freq_hz, freq_tolerance_hz=50.0,
                            window="hann", extract_fn=None, timeout=2.0):
        if extract_fn is None:
            extract_fn = extract_amplitude_at_frequency

        samples = self.capture_samples(n, timeout=timeout)
        freqs, mag = self.compute_fft(samples, window=window)
        value = extract_fn(freqs, mag, target_freq_hz, freq_tolerance_hz)
        return value, freqs, mag
