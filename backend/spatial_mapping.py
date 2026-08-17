"""
Ekstraksi amplitudo pada frekuensi target + normalisasi grayscale.

Amplitudo diambil sebagai MAKSIMUM magnitude dalam jendela
[target - tolerance, target + tolerance] -- bukan 1 bin tunggal -- agar
puncak yang sedikit bergeser dari angka nominal tetap tertangkap.
"""

import numpy as np


def extract_amplitude_at_frequency(freqs, magnitude, target_freq_hz,
                                   tolerance_hz=50.0):
    """
    Amplitudo puncak dalam jendela +/- tolerance_hz di sekitar target.

    Return 0.0 jika tidak ada bin FFT di dalam jendela.
    """
    freqs = np.asarray(freqs)
    magnitude = np.asarray(magnitude)
    if len(freqs) == 0:
        return 0.0

    mask = np.abs(freqs - target_freq_hz) <= tolerance_hz
    if not mask.any():
        return 0.0
    return float(magnitude[mask].max())


def estimasi_noise_floor(freqs, mag, target_freq_hz, tolerance_hz,
                         sideband_factor=5.0):
    """Median magnitudo bin sideband di sekitar jendela target."""
    jarak = np.abs(np.asarray(freqs) - target_freq_hz)
    mask = (jarak > tolerance_hz) & (jarak <= sideband_factor * tolerance_hz)
    if not mask.any():
        return 0.0
    return float(np.median(np.asarray(mag)[mask]))


def amplitude_matrix_to_grayscale(matrix, captured_mask=None,
                                  amp_min_fixed=None, amp_max_fixed=None):
    """
    Normalisasi min-max linear matrix amplitudo -> grayscale 0-255 (uint8).

    captured_mask: jika diberikan, skala hanya dari sel yang sudah terekam.
    """
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
        grayscale = np.full(matrix.shape, 128, dtype=np.uint8)
        return grayscale, amp_min, amp_max

    normalized = (matrix - amp_min) / (amp_max - amp_min)
    normalized = np.clip(normalized, 0.0, 1.0)
    grayscale = np.clip(np.round(normalized * 255.0), 0, 255).astype(np.uint8)
    return grayscale, amp_min, amp_max
