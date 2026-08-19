"""Pengukuran amplitudo di frekuensi modulasi (plat vs sample).

Di fotoakustik termodulasi, plat dan sample biasanya BERADA DI FREKUENSI
YANG SAMA (f modulasi). Yang membedakan biasanya AMPLITUDO, bukan pergeseran Hz.
"""

from __future__ import annotations

import numpy as np

from backend.spatial_mapping import (
    estimasi_noise_floor,
    extract_amplitude_at_frequency,
)


def ukur_amplitudo_modulasi(
    audio,
    *,
    mod_hz,
    tolerance_hz=100.0,
    fft_n=8192,
    n_avg=8,
    fft_min_hz=100.0,
    fft_max_hz=20000.0,
    timeout=3.0,
):
    """
    Rata-rata beberapa FFT; baca amplitudo tepat di sekitar frekuensi modulasi.

    Returns dict:
      amp_mod, peak_freq, peak_amp, noise_floor, snr, freqs, mag_avg
    """
    mod_hz = float(mod_hz)
    tol = float(tolerance_hz)
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
        return {
            "amp_mod": 0.0,
            "peak_freq": 0.0,
            "peak_amp": 0.0,
            "noise_floor": 0.0,
            "snr": 0.0,
            "freqs": np.array([]),
            "mag_avg": np.array([]),
        }

    mag_avg = (acc / float(n_avg)).astype(np.float64)
    freqs = freqs_ref

    amp_mod = extract_amplitude_at_frequency(freqs, mag_avg, mod_hz, tol)
    idx_peak = int(np.argmax(mag_avg))
    peak_freq = float(freqs[idx_peak])
    peak_amp = float(mag_avg[idx_peak])
    noise = estimasi_noise_floor(freqs, mag_avg, mod_hz, tol)
    snr = float(amp_mod / noise) if noise > 0 else 0.0

    return {
        "amp_mod": float(amp_mod),
        "peak_freq": peak_freq,
        "peak_amp": peak_amp,
        "noise_floor": float(noise),
        "snr": snr,
        "freqs": freqs,
        "mag_avg": mag_avg,
    }


# Alias lama (kompatibilitas)
def ukur_puncak_frekuensi(audio, **kwargs):
    hasil = ukur_amplitudo_modulasi(audio, **kwargs)
    return (
        hasil["peak_freq"],
        hasil["amp_mod"],
        hasil["freqs"],
        hasil["mag_avg"],
    )
