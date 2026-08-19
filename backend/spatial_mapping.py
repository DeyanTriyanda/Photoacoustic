"""
Ekstraksi amplitudo pada frekuensi target + normalisasi grayscale.

Aturan citra (Set Modulasi = f_set, mis. 17000 Hz):
  - f < f_set  → background hitam (tidak dipakai sebagai objek)
  - f ≈ f_set  → objek (amplitudo di jendela toleransi)

Pemetaan grayscale:
  - amplitudo tinggi → terang
  - amplitudo rendah → gelap
"""

import numpy as np


def extract_amplitude_at_frequency(freqs, magnitude, target_freq_hz,
                                   tolerance_hz=50.0):
    freqs = np.asarray(freqs)
    magnitude = np.asarray(magnitude)
    if len(freqs) == 0:
        return 0.0

    mask = np.abs(freqs - target_freq_hz) <= tolerance_hz
    if not mask.any():
        return 0.0
    return float(magnitude[mask].max())


def extract_amplitude_object_black_background(
    freqs, magnitude, target_freq_hz, tolerance_hz=50.0
):
    """
    Amplitudo objek dengan pita di bawah frekuensi set sebagai background hitam.

    Spektrum pada f < target_freq_hz di-nol-kan (background hitam / plat),
    lalu amplitudo diambil hanya di sekitar target_freq_hz (± tolerance_hz).
    """
    freqs = np.asarray(freqs)
    magnitude = np.asarray(magnitude, dtype=np.float64)
    if len(freqs) == 0:
        return 0.0

    mag = magnitude.copy()
    mag[freqs < float(target_freq_hz)] = 0.0
    return extract_amplitude_at_frequency(
        freqs, mag, target_freq_hz, tolerance_hz
    )


def estimasi_noise_floor(freqs, mag, target_freq_hz, tolerance_hz,
                         sideband_factor=5.0):
    jarak = np.abs(np.asarray(freqs) - target_freq_hz)
    mask = (jarak > tolerance_hz) & (jarak <= sideband_factor * tolerance_hz)
    # Sideband di bawah f_set sudah dianggap background; pakai sisi atas saja
    # agar lantai derau tidak terkontaminasi energi plat.
    mask = mask & (np.asarray(freqs) >= float(target_freq_hz))
    if not mask.any():
        return 0.0
    return float(np.median(np.asarray(mag)[mask]))


def amplitude_matrix_to_grayscale(
    matrix,
    captured_mask=None,
    amp_min_fixed=None,
    amp_max_fixed=None,
    invert=False,
):
    """
    Normalisasi matrix amplitudo ke grayscale 0..255.

    invert=False (default): amp tinggi → terang, amp rendah → gelap.
    invert=True: amp rendah → terang, amp tinggi → gelap
    (cocok sample lebih lembek dari plat → amp turun).
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
        # Semua sama: jika nol → hitam (background); jika tidak → abu-abu
        if amp_max <= 0.0:
            grayscale = np.zeros(matrix.shape, dtype=np.uint8)
        else:
            grayscale = np.full(matrix.shape, 128, dtype=np.uint8)
        return grayscale, amp_min, amp_max

    normalized = (matrix - amp_min) / (amp_max - amp_min)
    normalized = np.clip(normalized, 0.0, 1.0)
    if invert:
        # amp rendah (sample lembek) → 255 terang; amp tinggi (plat) → 0 gelap
        normalized = 1.0 - normalized
    grayscale = np.clip(np.round(normalized * 255.0), 0, 255).astype(np.uint8)
    return grayscale, amp_min, amp_max
