"""
Akuisisi audio -- inti PortAudio + FFT (FFTW) di C++.

API Python tetap sama agar frontend tidak berubah.
"""

import numpy as np

from backend._native import AudioCaptureNative
from backend.spatial_mapping import extract_amplitude_at_frequency


class AudioCapture:
    """Streaming audio input + FFT. on_error(str) untuk warning non-fatal."""

    def __init__(self, on_error=None):
        self._native = AudioCaptureNative()
        self.on_error = on_error
        self.samplerate = 96000
        self.channels = 1
        self.device = None
        self.running = False
        self.stream = None  # kompatibilitas API lama (tidak dipakai)

    @staticmethod
    def list_input_devices(force_rescan=True):
        try:
            return list(AudioCaptureNative.list_input_devices(force_rescan))
        except Exception:
            return []

    def start(self, device_index, samplerate=96000, channels=1,
              buffer_seconds=1.0, blocksize=1024):
        if self.running:
            self.stop()
        ok, msg = self._native.start(
            int(device_index), int(samplerate), int(channels),
            float(buffer_seconds), int(blocksize),
        )
        if ok:
            self.device = device_index
            self.samplerate = int(samplerate)
            self.channels = int(channels)
            self.running = True
        else:
            self.running = False
        return ok, msg

    def stop(self):
        self._native.stop()
        self.running = False

    def is_running(self):
        return bool(self._native.is_running())

    def get_waveform(self):
        arr = np.asarray(self._native.get_waveform(), dtype=np.float32)
        err = self._native.last_error()
        if err and self.on_error:
            self.on_error(err)
        return arr

    def get_fft(self, window="hann", min_freq=0.0, max_freq=None):
        freqs, mag = self._native.get_fft(window, float(min_freq), max_freq)
        return np.asarray(freqs), np.asarray(mag)

    def compute_fft(self, data, window="hann", min_freq=0.0, max_freq=None):
        data = np.asarray(data, dtype=np.float32)
        freqs, mag = self._native.compute_fft(data, window, float(min_freq), max_freq)
        return np.asarray(freqs), np.asarray(mag)

    def get_peak(self, min_freq=20.0, max_freq=None):
        return self._native.get_peak(float(min_freq), max_freq)

    def capture_samples(self, n, timeout=2.0):
        return np.asarray(
            self._native.capture_samples(int(n), float(timeout)), dtype=np.float32
        )

    def capture_and_measure(self, n, target_freq_hz, freq_tolerance_hz=50.0,
                            window="hann", extract_fn=None, timeout=2.0):
        if extract_fn is None:
            extract_fn = extract_amplitude_at_frequency
        samples = self.capture_samples(n, timeout=timeout)
        freqs, mag = self.compute_fft(samples, window=window)
        value = extract_fn(freqs, mag, target_freq_hz, freq_tolerance_hz)
        return value, freqs, mag
