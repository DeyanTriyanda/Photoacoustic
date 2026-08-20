"""
Pipeline citra fotoakustik (1 laser + 1 mic scanning):

  1. Lock-In Amplifier digital (quadrature demodulation)
  2. Hilbert transform → envelope
  3. Delay-and-Sum (DAS) / backprojection

Sistem: Single-Element Synthetic Aperture (laser & mic bergeser bersama).
"""

from __future__ import annotations

import numpy as np


def _moving_average(x: np.ndarray, win: int) -> np.ndarray:
    win = max(int(win), 1)
    if win == 1:
        return np.asarray(x, dtype=np.float64)
    kernel = np.ones(win, dtype=np.float64) / win
    return np.convolve(np.asarray(x, dtype=np.float64), kernel, mode="same")


def lock_in_quadrature(
    signal: np.ndarray,
    samplerate: float,
    f_ref_hz: float,
    lp_hz: float = 200.0,
):
    """
    Quadrature demodulation (lock-in digital) tanpa kabel referensi hardware.

    Referensi buatan: cos/sin murni pada f_ref_hz (mis. 18000 Hz).
    Returns:
      amp_t: amplitudo vs waktu setelah LPF (bentuk lambat)
      i_f, q_f: komponen in-phase / quadrature tersaring
    """
    x = np.asarray(signal, dtype=np.float64).reshape(-1)
    if x.size == 0:
        z = np.zeros(0, dtype=np.float64)
        return z, z, z

    fs = float(samplerate)
    f_ref = float(f_ref_hz)
    t = np.arange(x.size, dtype=np.float64) / fs
    # Referensi sintetis (bukan dari Input 2 hardware)
    ref_i = np.cos(2.0 * np.pi * f_ref * t)
    ref_q = np.sin(2.0 * np.pi * f_ref * t)

    mixed_i = x * ref_i
    mixed_q = x * ref_q

    # LPF setelah mixing ≈ envelope lambat di sekitar DC
    win = max(int(round(fs / max(lp_hz, 1.0))), 1)
    i_f = _moving_average(mixed_i, win)
    q_f = _moving_average(mixed_q, win)
    amp_t = 2.0 * np.sqrt(np.maximum(i_f * i_f + q_f * q_f, 0.0))
    return amp_t, i_f, q_f


def hilbert_envelope(signal: np.ndarray) -> np.ndarray:
    """
    Envelope via transformasi Hilbert (analytic signal, FFT).
    Mengubah osilasi +/- menjadi intensitas mutlak (garis luar).
    """
    x = np.asarray(signal, dtype=np.float64).reshape(-1)
    n = x.size
    if n == 0:
        return x.copy()

    X = np.fft.fft(x)
    h = np.zeros(n, dtype=np.float64)
    if n % 2 == 0:
        h[0] = 1.0
        h[n // 2] = 1.0
        h[1 : n // 2] = 2.0
    else:
        h[0] = 1.0
        h[1 : (n + 1) // 2] = 2.0
    analytic = np.fft.ifft(X * h)
    return np.abs(analytic).astype(np.float64)


def process_a_line_lockin_hilbert(
    signal: np.ndarray,
    samplerate: float,
    f_ref_hz: float,
    lp_hz: float = 200.0,
):
    """
    Langkah 1–2 per A-line: lock-in lalu Hilbert pada amplitudo lock-in
    (atau langsung envelope sinyal band-limited hasil lock-in).

    Returns:
      envelope: 1D float64
      scalar_amp: ringkasan skalar (mean envelope) untuk tampilan titik
    """
    amp_t, _, _ = lock_in_quadrature(signal, samplerate, f_ref_hz, lp_hz=lp_hz)
    # Hilbert pada jejak lock-in memperhalus envelope absolut
    env = hilbert_envelope(amp_t)
    scalar = float(np.mean(env)) if env.size else 0.0
    return env, scalar


def delay_and_sum(
    envelopes: np.ndarray,
    positions_xy_m: np.ndarray,
    image_x_m: np.ndarray,
    image_y_m: np.ndarray,
    samplerate: float,
    sound_speed_m_s: float,
):
    """
    Delay-and-Sum / backprojection (synthetic aperture, 1 elemen scanning).

    envelopes: shape (N_scan, N_samples) — envelope per posisi scan
    positions_xy_m: shape (N_scan, 2) — koordinat (x,y) mic/laser [meter]
    image_x_m, image_y_m: 1D grid koordinat piksel [meter]

    Asumsi path akustik satu arah (sumber PA di piksel → mic di posisi scan):
      delay = distance / c
    """
    env = np.asarray(envelopes, dtype=np.float64)
    if env.ndim != 2:
        raise ValueError("envelopes harus 2D (N_scan, N_samples)")
    pos = np.asarray(positions_xy_m, dtype=np.float64)
    if pos.shape != (env.shape[0], 2):
        raise ValueError("positions_xy_m harus (N_scan, 2)")

    xs = np.asarray(image_x_m, dtype=np.float64).reshape(-1)
    ys = np.asarray(image_y_m, dtype=np.float64).reshape(-1)
    n_scan, n_samp = env.shape
    fs = float(samplerate)
    c = float(sound_speed_m_s)
    if c <= 0:
        raise ValueError("sound_speed_m_s harus > 0")

    img = np.zeros((ys.size, xs.size), dtype=np.float64)
    for iy, y in enumerate(ys):
        for ix, x in enumerate(xs):
            acc = 0.0
            for s in range(n_scan):
                dx = x - pos[s, 0]
                dy = y - pos[s, 1]
                dist = float(np.hypot(dx, dy))
                delay_s = dist / c
                idx = int(round(delay_s * fs))
                if 0 <= idx < n_samp:
                    acc += env[s, idx]
            img[iy, ix] = acc
    return img


def reconstruct_scan_das(
    envelopes: np.ndarray,
    n_rows: int,
    n_cols: int,
    point_distance_m: float,
    row_distance_m: float,
    samplerate: float,
    sound_speed_m_s: float,
    zigzag: bool = True,
):
    """
    Susun posisi raster (zig-zag seperti firmware) lalu DAS ke grid yang sama.
    envelopes diurutkan row-major sesuai urutan perekaman zigzag.
    """
    env = np.asarray(envelopes, dtype=np.float64)
    expected = n_rows * n_cols
    if env.shape[0] != expected:
        raise ValueError(
            f"jumlah A-line {env.shape[0]} != n_rows*n_cols ({expected})"
        )

    positions = np.zeros((expected, 2), dtype=np.float64)
    k = 0
    for r in range(n_rows):
        cols = range(n_cols) if (not zigzag or r % 2 == 0) else range(n_cols - 1, -1, -1)
        for c in cols:
            positions[k, 0] = c * point_distance_m
            positions[k, 1] = r * row_distance_m
            k += 1

    xs = np.arange(n_cols, dtype=np.float64) * point_distance_m
    ys = np.arange(n_rows, dtype=np.float64) * row_distance_m
    return delay_and_sum(
        env, positions, xs, ys, samplerate, sound_speed_m_s
    )
