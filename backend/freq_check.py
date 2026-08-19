"""Pengukuran puncak frekuensi (plat / sample) dari mic aktif."""

from __future__ import annotations

import numpy as np


def ukur_puncak_frekuensi(
    audio,
    *,
    mod_hz,
    fft_n=8192,
    n_avg=8,
    fft_min_hz=100.0,
    fft_max_hz=20000.0,
    window_half_hz=2000.0,
    timeout=3.0,
):
    """
    Rata-rata beberapa FFT; cari puncak di sekitar frekuensi modulasi.

    Returns:
        (freq_hz, amp, freqs, mag_avg)
    """
    mod_hz = float(mod_hz)
    acc = None
    freqs_ref = None
    for _ in range(int(n_avg)):
        samples = audio.capture_samples(int(fft_n), timeout=timeout)
        freqs, mag = audio.compute_fft(
            samples, min_freq=float(fft_min_hz), max_freq=float(fft_max_hz)
        )
        if freqs_ref is None:
            freqs_ref = freqs
            acc = mag.astype(np.float64)
        else:
            n = min(len(acc), len(mag))
            acc[:n] += mag[:n]
    if freqs_ref is None or acc is None or len(freqs_ref) == 0:
        return 0.0, 0.0, np.array([]), np.array([])

    mag_avg = (acc / float(n_avg)).astype(np.float64)
    freqs = freqs_ref

    f0 = max(float(fft_min_hz), mod_hz - float(window_half_hz))
    f1 = min(float(fft_max_hz), mod_hz + float(window_half_hz))
    mask = (freqs >= f0) & (freqs <= f1)
    if not np.any(mask):
        mask = np.ones(len(freqs), dtype=bool)
    idxs = np.flatnonzero(mask)
    idx_local = int(np.argmax(mag_avg[mask]))
    idx = int(idxs[idx_local])
    return float(freqs[idx]), float(mag_avg[idx]), freqs, mag_avg
