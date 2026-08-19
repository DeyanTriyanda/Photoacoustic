"""
Analisis spektrum noise saat laser mengenai plat (tatakan).

Mencari puncak-puncak frekuensi dari FFT mic agar diketahui
frekuensi noise plat (biasanya di bawah frekuensi modulasi sampel).
"""

import csv
from dataclasses import dataclass

import numpy as np


@dataclass
class PuncakNoise:
    freq_hz: float
    amplitude: float
    rank: int
    label: str = ""  # "plat" / "modulasi" / "lain"


def temukan_puncak_spektrum(
    freqs,
    magnitude,
    min_freq_hz=20.0,
    max_freq_hz=20000.0,
    n_puncak=20,
    min_rel_amp=0.02,
):
    """
    Cari puncak lokal di spektrum FFT.

    min_rel_amp: ambang relatif terhadap puncak maksimum (0..1).
    Return list PuncakNoise terurut amplitudo menurun.
    """
    freqs = np.asarray(freqs, dtype=np.float64)
    mag = np.asarray(magnitude, dtype=np.float64)
    if len(freqs) < 3 or len(mag) != len(freqs):
        return []

    mask = (freqs >= float(min_freq_hz)) & (freqs <= float(max_freq_hz))
    f = freqs[mask]
    m = mag[mask]
    if len(f) < 3:
        return []

    # Puncak lokal sederhana
    kandidat_idx = []
    for i in range(1, len(m) - 1):
        if m[i] >= m[i - 1] and m[i] > m[i + 1]:
            kandidat_idx.append(i)

    if not kandidat_idx:
        # Fallback: satu puncak global
        i = int(np.argmax(m))
        return [
            PuncakNoise(
                freq_hz=float(f[i]),
                amplitude=float(m[i]),
                rank=1,
            )
        ]

    amp_max = float(np.max(m))
    ambang = max(amp_max * float(min_rel_amp), 0.0)
    tersaring = [i for i in kandidat_idx if m[i] >= ambang]
    if not tersaring:
        tersaring = [int(np.argmax(m))]

    # Urutkan by amplitude, hilangkan tetangga terlalu dekat (~30 Hz)
    tersaring.sort(key=lambda i: m[i], reverse=True)
    terpilih = []
    for i in tersaring:
        if any(abs(f[i] - f[j]) < 30.0 for j in terpilih):
            continue
        terpilih.append(i)
        if len(terpilih) >= int(n_puncak):
            break

    hasil = []
    for rank, i in enumerate(terpilih, start=1):
        hasil.append(
            PuncakNoise(
                freq_hz=float(f[i]),
                amplitude=float(m[i]),
                rank=rank,
            )
        )
    return hasil


def beri_label_puncak(puncak_list, frekuensi_modulasi_hz=None, toleransi_hz=150.0):
    """
    Label: dekat modulasi → 'modulasi'; di bawahnya → 'plat'; sisanya → 'lain'.
    """
    out = []
    fmod = float(frekuensi_modulasi_hz) if frekuensi_modulasi_hz else None
    for p in puncak_list:
        label = "lain"
        if fmod is not None and fmod > 0:
            if abs(p.freq_hz - fmod) <= float(toleransi_hz):
                label = "modulasi"
            elif p.freq_hz < fmod:
                label = "plat"
            else:
                label = "lain"
        out.append(
            PuncakNoise(
                freq_hz=p.freq_hz,
                amplitude=p.amplitude,
                rank=p.rank,
                label=label,
            )
        )
    return out


def ringkas_teks(puncak_list):
    """Teks ringkas untuk UI / log."""
    if not puncak_list:
        return "Tidak ada puncak terdeteksi."
    baris = ["Peringkat | Frekuensi (Hz) | Amplitudo | Label"]
    baris.append("-" * 52)
    for p in puncak_list:
        baris.append(
            f"{p.rank:>8} | {p.freq_hz:>13.1f} | {p.amplitude:>9.4g} | {p.label or '-'}"
        )
    return "\n".join(baris)


def simpan_puncak_csv(path, puncak_list):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["rank", "freq_hz", "amplitude", "label"])
        for p in puncak_list:
            w.writerow([p.rank, f"{p.freq_hz:.3f}", f"{p.amplitude:.8g}", p.label])
