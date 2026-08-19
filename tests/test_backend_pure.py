"""Tes fungsi murni backend -- tanpa hardware/GUI."""

import csv
import os
import tempfile

import numpy as np
import pytest

from backend.config import (
    AUTO_TARGET_MAX_HZ,
    BREAK_TIME_MS,
    POINT_DISTANCE_CM,
    TARGET_FREQ_HZ,
)
from backend.scan_timing import (
    format_jam_menit,
    hitung_estimasi_durasi_s,
    hitung_jumlah_baris,
    hitung_titik_per_baris,
    jog_speed_cm_s,
    scan_speed_cm_s,
)
from backend.spatial_mapping import (
    amplitude_matrix_to_grayscale,
    estimasi_noise_floor,
    extract_amplitude_at_frequency,
    extract_amplitude_object_black_background,
)
from backend import noise_analysis as na
from backend import deep_learning as dl


class TestScanTiming:
    def test_grid_size(self):
        # 1.0 cm / 0.05 + 1 = 21
        assert hitung_titik_per_baris(1.0) == 21
        assert hitung_jumlah_baris(1.0) == 21
        assert hitung_titik_per_baris(0) == 0
        assert hitung_jumlah_baris(-1) == 0

    def test_scan_speed_matches_firmware_formula(self):
        # 1_000_000 / (2 * 800) / 1000 = 0.625 cm/s
        assert scan_speed_cm_s(800, 1000.0) == pytest.approx(0.625)
        assert jog_speed_cm_s(300, 1000.0) == pytest.approx(
            1_000_000 / (2 * 300) / 1000.0
        )

    def test_estimasi_durasi_positif(self):
        d = hitung_estimasi_durasi_s(0.2, 0.2)
        assert d > 0
        # Minimal = titik * baris * dwell
        titik = hitung_titik_per_baris(0.2)
        baris = hitung_jumlah_baris(0.2)
        assert d >= titik * baris * (BREAK_TIME_MS / 1000.0)

    def test_format_jam_menit(self):
        assert format_jam_menit(0) == "0 jam 0 menit"
        assert format_jam_menit(90) == "0 jam 1 menit"
        assert format_jam_menit(61, bulatkan_ke_atas=True) == "0 jam 2 menit"
        assert format_jam_menit(3600) == "1 jam 0 menit"


class TestAmplitudeExtraction:
    def test_peak_in_window(self):
        freqs = np.array([100.0, 200.0, 300.0, 400.0])
        mag = np.array([0.1, 0.5, 2.0, 0.2])
        assert extract_amplitude_at_frequency(freqs, mag, 300.0, 50.0) == 2.0

    def test_empty_or_miss(self):
        assert extract_amplitude_at_frequency([], [], 100.0) == 0.0
        freqs = np.array([100.0, 200.0])
        mag = np.array([1.0, 2.0])
        assert extract_amplitude_at_frequency(freqs, mag, 1000.0, 10.0) == 0.0

    def test_black_background_ignores_below_target(self):
        # Plat kuat di 10 kHz, objek di 17 kHz — citra hanya pakai objek
        freqs = np.array([10000.0, 15000.0, 16900.0, 17000.0, 17100.0])
        mag = np.array([9.0, 8.0, 0.5, 3.0, 0.4])
        assert extract_amplitude_object_black_background(
            freqs, mag, 17000.0, 100.0
        ) == pytest.approx(3.0)
        # Tanpa aturan background, jendela ±100 Hz masih bisa kena 16900
        # Dengan background: f < 17000 di-nol-kan → 16900 tidak dipakai
        assert extract_amplitude_object_black_background(
            freqs, mag, 17000.0, 200.0
        ) == pytest.approx(3.0)

    def test_black_background_all_below_is_zero(self):
        freqs = np.array([1000.0, 5000.0, 10000.0])
        mag = np.array([5.0, 7.0, 9.0])
        assert extract_amplitude_object_black_background(
            freqs, mag, 17000.0, 100.0
        ) == 0.0

    def test_noise_floor_sideband(self):
        freqs = np.linspace(0, 1000, 1001)
        mag = np.ones_like(freqs) * 0.1
        mag[500] = 5.0  # puncak di 500 Hz
        floor = estimasi_noise_floor(freqs, mag, 500.0, 20.0, sideband_factor=5.0)
        assert floor == pytest.approx(0.1)

    def test_grayscale_minmax(self):
        matrix = np.array([[0.0, 1.0], [0.5, 0.25]])
        mask = np.ones_like(matrix, dtype=bool)
        gray, amin, amax = amplitude_matrix_to_grayscale(matrix, captured_mask=mask)
        assert amin == 0.0 and amax == 1.0
        assert gray.dtype == np.uint8
        assert gray[0, 0] == 0
        assert gray[0, 1] == 255

    def test_grayscale_identical_values(self):
        matrix = np.full((2, 2), 0.7)
        mask = np.ones_like(matrix, dtype=bool)
        gray, _, _ = amplitude_matrix_to_grayscale(matrix, captured_mask=mask)
        assert np.all(gray == 128)

    def test_grayscale_ignores_uncaptured(self):
        matrix = np.array([[0.0, 10.0], [0.0, 0.0]])
        mask = np.array([[False, True], [False, False]])
        gray, amin, amax = amplitude_matrix_to_grayscale(matrix, captured_mask=mask)
        # Hanya satu titik valid -> rentang 0 -> abu-abu tengah
        assert amin == amax == 10.0
        assert gray[0, 1] == 128


class TestNoiseAnalysis:
    def test_temukan_puncak(self):
        freqs = np.linspace(0, 20000, 4001)
        mag = np.ones_like(freqs) * 0.05
        mag[np.argmin(np.abs(freqs - 8000))] = 2.0
        mag[np.argmin(np.abs(freqs - 12000))] = 1.5
        mag[np.argmin(np.abs(freqs - 17000))] = 3.0
        puncak = na.temukan_puncak_spektrum(freqs, mag, n_puncak=5)
        assert len(puncak) >= 3
        assert puncak[0].freq_hz == pytest.approx(17000, abs=20)
        labeled = na.beri_label_puncak(puncak, frekuensi_modulasi_hz=17000.0)
        # 8k dan 12k di bawah 17k → plat
        assert any(p.label == "plat" for p in labeled if p.freq_hz < 16000)
        assert any(p.label == "modulasi" for p in labeled)


class TestDeepLearningIO:
    def test_dari_gray_matrix_flip(self):
        gray = np.array([[10, 20], [30, 40]], dtype=np.uint8)
        out = dl.dari_gray_matrix(gray)
        assert out.dtype == np.float32
        assert out.shape == (2, 2)
        # baris 0 scan jadi baris bawah -> flipud
        assert out[0, 0] == pytest.approx(30 / 255.0)
        assert out[1, 0] == pytest.approx(10 / 255.0)

    def test_siapkan_input_size(self):
        data = np.random.rand(40, 30).astype(np.float32)
        out = dl.siapkan_input(data, 16)
        assert out.shape == (16, 16)
        assert 0.0 <= out.min() <= out.max() <= 1.0

    def test_muat_csv_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "m.csv")
            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["Y\\X", "0.00", "0.05"])
                w.writerow(["0.00", "1", "2"])
                w.writerow(["0.05", "3", "4"])
            data = dl.muat_csv(path)
            assert data.shape == (2, 2)
            assert data.min() >= 0.0 and data.max() <= 1.0

    def test_interpretasi_vector(self):
        jenis, nilai = dl.interpretasi_keluaran(np.array([[0.1, 0.7, 0.2]]))
        assert jenis == "vector"
        assert nilai.shape == (3,)
        assert int(np.argmax(nilai)) == 1

    def test_interpretasi_image_chw(self):
        # (C,H,W) channel-first RGB
        raw = np.random.rand(1, 3, 8, 8).astype(np.float32)
        jenis, img = dl.interpretasi_keluaran(raw)
        assert jenis == "image"
        assert img.shape == (8, 8, 3)

    def test_samakan_ukuran_grayscale(self):
        # Simulasi keluaran 2x dari Real-ESRGAN → dipotong kembali ke input.
        big = np.random.rand(128, 128).astype(np.float32)
        out = dl.samakan_ukuran(big, 64, 64)
        assert out.shape == (64, 64)
        assert 0.0 <= out.min() <= out.max() <= 1.0

    def test_ukuran_citra(self):
        assert dl.ukuran_citra(np.zeros((21, 33))) == (21, 33)

    def test_path_model_default(self):
        path = dl.path_model_default()
        assert path.endswith("Real-ESRGAN-x2plus.onnx")
        assert "assets" in path

    def test_cari_model_fleksibel(self):
        with tempfile.TemporaryDirectory() as tmp:
            assets = os.path.join(tmp, "assets")
            os.makedirs(assets)
            assert dl.cari_model_di_assets(tmp) is None
            lain = os.path.join(assets, "Real-ESRGAN-x4plus.onnx")
            with open(lain, "wb") as f:
                f.write(b"dummy")
            ketemu = dl.cari_model_di_assets(tmp)
            assert ketemu == lain
            assert "Real-ESRGAN-x4plus.onnx" in dl.daftar_model_di_assets(tmp)

    def test_model_ext_ditolak(self):
        with pytest.raises(ValueError):
            dl.ModelDL("model.xyz", warm_load=False)


class TestConfigConsistency:
    def test_target_below_mic_limit(self):
        assert 0 < TARGET_FREQ_HZ < AUTO_TARGET_MAX_HZ
        assert POINT_DISTANCE_CM > 0
