"""
Perekam matriks intensitas 2D fotoakustik per titik raster.

Firmware open-loop: Python mereplikasi jadwal diam/gerak firmware.
Akuisisi di TENGAH jendela BREAK_TIME; sinkronisasi ulang per baris via
pesan serial "Scanning baris ke-N". Stream mic tetap kontinu -- yang
dibuka/tutup hanya jendela capture_samples.

Per titik: n_avg blok FFT dirata-ratakan -> amplitudo RAW objek di
target +/- toleransi, dengan f < target sebagai background hitam
-> TERKOREKSI (raw - noise floor sideband atas).
"""

import threading
import time

import numpy as np

from backend.config import (
    AUTO_TARGET_MAX_HZ,
    AUTO_TARGET_MIN_HZ,
    NOISE_SIDEBAND_FACTOR,
)
from backend.scan_timing import scan_speed_cm_s
from backend.spatial_mapping import (
    estimasi_noise_floor,
    extract_amplitude_at_frequency,
    extract_amplitude_object_black_background,
)


def _capture_avg_spectrum(audio, fft_n=4096, n_avg=4, should_continue=None):
    """Rata-rata magnitudo FFT dari n_avg blok baru. None jika dibatalkan."""
    n_avg = max(int(n_avg), 1)
    freqs = None
    mag_sum = None
    for _ in range(n_avg):
        if should_continue is not None and not should_continue():
            return None
        samples = audio.capture_samples(int(fft_n))
        f, m = audio.compute_fft(samples, window="hann")
        if len(f) == 0:
            continue
        if mag_sum is None:
            freqs, mag_sum = f, m.astype(np.float64)
        else:
            mag_sum += m
    if freqs is None:
        return None, None
    return freqs, mag_sum / n_avg


class SpatialScanRecorder:
    def __init__(self, audio_capture, point_distance_cm, row_distance_cm,
                 scan_step_delay_us, step_per_cm_x, break_time_ms,
                 target_freq_hz=None, freq_tolerance_hz=50.0,
                 fft_n=4096, n_avg=4, settling_time_ms=40.0):
        """
        target_freq_hz=None -> deteksi otomatis puncak spektrum di titik
        pertama (AUTO_TARGET_MIN_HZ..AUTO_TARGET_MAX_HZ).
        """
        if target_freq_hz is not None:
            if target_freq_hz > AUTO_TARGET_MAX_HZ:
                raise ValueError(
                    f"target_freq_hz={target_freq_hz} Hz melebihi batas "
                    "respons mikrofon ECM8000 (20000 Hz)."
                )
            if target_freq_hz <= 0:
                raise ValueError("target_freq_hz harus > 0 Hz.")

        self.audio = audio_capture
        self.point_distance_cm = point_distance_cm
        self.row_distance_cm = row_distance_cm
        self.scan_speed_cm_s = scan_speed_cm_s(scan_step_delay_us, step_per_cm_x)
        self.break_time_ms = break_time_ms
        self.target_freq_hz = target_freq_hz
        self.freq_tolerance_hz = freq_tolerance_hz

        self.fft_n = int(fft_n)
        self.n_avg = max(int(n_avg), 1)
        self.settling_time_s = settling_time_ms / 1000.0

        acquisition_s = (self.n_avg * self.fft_n) / self.audio.samplerate
        self._acquisition_s = acquisition_s
        self._min_dwell_s = self.settling_time_s + acquisition_s

        self._running = False
        self._thread = None
        self.matrix = None       # amplitudo terkoreksi
        self.matrix_raw = None   # amplitudo raw

        self._sync_lock = threading.Lock()
        self._sync_row = None
        self._sync_time = None
        self._sync_seen = False
        self._est_row_duration_s = 0.0
        self.row_sync_slack_s = 2.0

        self.on_point_captured = None
        self.on_finished = None
        self.on_timing_warning = None
        self.on_error = None
        self.on_target_detected = None

    def start_recording(self, x_cm, y_cm):
        print(f"[SpatialScanRecorder] start_recording dipanggil: x={x_cm}cm y={y_cm}cm")

        jumlah_titik = round(x_cm / self.point_distance_cm) + 1
        jumlah_baris = round(y_cm / self.row_distance_cm) + 1
        if jumlah_titik < 1 or jumlah_baris < 1:
            print("[SpatialScanRecorder] jumlah_titik/jumlah_baris < 1, batal merekam")
            return

        print(f"[SpatialScanRecorder] grid: {jumlah_baris} baris x {jumlah_titik} titik")

        self.matrix = np.zeros((jumlah_baris, jumlah_titik))
        self.matrix_raw = np.zeros((jumlah_baris, jumlah_titik))
        self._running = True
        self._thread = threading.Thread(
            target=self._record_loop_safe,
            args=(jumlah_titik, jumlah_baris),
            daemon=True,
        )
        self._thread.start()

    def _record_loop_safe(self, jumlah_titik, jumlah_baris):
        try:
            self._record_loop(jumlah_titik, jumlah_baris)
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            print("[SpatialScanRecorder] ERROR di thread perekaman:")
            print(tb)
            self._running = False
            if self.on_error:
                try:
                    self.on_error(f"{e}\n{tb}")
                except Exception:
                    pass

    def stop_recording(self):
        self._running = False

    def is_recording(self):
        return self._running

    def resync_row(self, baris_ke):
        """Jangkar jadwal dari pesan firmware 'Scanning baris ke-N' (1-based)."""
        try:
            idx0 = int(baris_ke) - 1
        except (TypeError, ValueError):
            return
        if idx0 < 0:
            return
        with self._sync_lock:
            self._sync_seen = True
            if self._sync_row is None or idx0 > self._sync_row:
                self._sync_row = idx0
                self._sync_time = time.monotonic()

    def _tunggu_sync_baris(self, baris_idx0, est_start):
        with self._sync_lock:
            sync_seen = self._sync_seen
        slack = self.row_sync_slack_s
        if sync_seen:
            slack += self._est_row_duration_s
        deadline = max(est_start, time.monotonic()) + slack
        while self._running:
            with self._sync_lock:
                row, ts = self._sync_row, self._sync_time
            if row is not None:
                if row == baris_idx0:
                    return ts
                if row > baris_idx0:
                    self._warn(
                        f"Baris {baris_idx0 + 1}: firmware sudah mengumumkan "
                        f"baris {row + 1} -- jadwal Python tertinggal, memakai "
                        "estimasi."
                    )
                    return None
            if time.monotonic() >= deadline:
                self._warn(
                    f"Baris {baris_idx0 + 1}: pesan sinkronisasi serial tidak "
                    "diterima -- memakai estimasi jadwal."
                )
                return None
            time.sleep(0.01)
        return None

    def _wait_until(self, target_time):
        while self._running:
            remaining = target_time - time.monotonic()
            if remaining <= 0:
                return -remaining if remaining < 0 else 0.0
            time.sleep(min(remaining, 0.2))
        return 0.0

    def _warn(self, msg):
        if self.on_timing_warning:
            try:
                self.on_timing_warning(msg)
            except Exception:
                pass

    def _measure_point(self):
        """Return (raw, corrected) atau None jika dihentikan."""
        hasil = _capture_avg_spectrum(
            self.audio, self.fft_n, self.n_avg,
            should_continue=lambda: self._running,
        )
        if hasil is None:
            return None
        freqs, mag_avg = hasil
        if freqs is None:
            return 0.0, 0.0

        if self.target_freq_hz is None:
            max_hz = min(AUTO_TARGET_MAX_HZ, self.audio.samplerate / 2.0)
            mask = (freqs >= AUTO_TARGET_MIN_HZ) & (freqs <= max_hz)
            if not mask.any():
                return 0.0, 0.0
            idx_range = np.where(mask)[0]
            idx_peak = idx_range[int(np.argmax(mag_avg[idx_range]))]
            self.target_freq_hz = float(freqs[idx_peak])
            raw = float(mag_avg[idx_peak])
            print(
                f"[SpatialScanRecorder] frekuensi target terdeteksi otomatis: "
                f"{self.target_freq_hz:.1f} Hz (amplitudo {raw:.6g})"
            )
            if self.on_target_detected:
                try:
                    self.on_target_detected(self.target_freq_hz, raw)
                except Exception:
                    pass
        else:
            # f < target = background hitam; objek hanya di sekitar target
            raw = extract_amplitude_object_black_background(
                freqs, mag_avg, self.target_freq_hz, self.freq_tolerance_hz
            )

        noise_floor = estimasi_noise_floor(
            freqs, mag_avg, self.target_freq_hz, self.freq_tolerance_hz,
            sideband_factor=NOISE_SIDEBAND_FACTOR,
        )
        corrected = max(raw - noise_floor, 0.0)
        return raw, corrected

    def _record_loop(self, jumlah_titik, jumlah_baris):
        n_total = jumlah_titik * jumlah_baris
        n_done = 0

        dwell_s = self.break_time_ms / 1000.0
        if dwell_s < self._min_dwell_s:
            self._warn(
                f"BREAK_TIME_MS firmware ({self.break_time_ms} ms) lebih kecil "
                f"dari settling+acquisition ({self._min_dwell_s * 1000:.1f} ms). "
                "Jadwal Python akan molor dari firmware -- pertimbangkan "
                "menaikkan BREAK_TIME_MS di firmware."
            )

        capture_offset_s = max(
            self.settling_time_s,
            (dwell_s - self._acquisition_s) / 2.0,
        )

        travel_point_s = self.point_distance_cm / self.scan_speed_cm_s
        travel_row_s = self.row_distance_cm / self.scan_speed_cm_s

        self._est_row_duration_s = (
            jumlah_titik * dwell_s
            + (jumlah_titik - 1) * travel_point_s
            + travel_row_s
        )

        t_cursor = time.monotonic()

        for baris in range(jumlah_baris):
            kiri_ke_kanan = (baris % 2 == 0)

            anchor = self._tunggu_sync_baris(baris, t_cursor)
            if not self._running:
                return
            if anchor is not None:
                delta_s = anchor - t_cursor
                if abs(delta_s) > 0.05:
                    self._warn(
                        f"Baris {baris + 1}: jadwal digeser {delta_s * 1000:+.0f} ms "
                        "mengikuti pengumuman firmware."
                    )
                t_cursor = anchor

            for i in range(jumlah_titik):
                if not self._running:
                    return

                late_s = self._wait_until(t_cursor + capture_offset_s)
                if not self._running:
                    return
                if late_s > 0.005:
                    self._warn(
                        f"Titik (row={baris}, col={i}) molor {late_s*1000:.1f} ms "
                        "dari jadwal firmware."
                    )

                hasil = self._measure_point()
                if hasil is None:
                    return
                value_raw, value_corrected = hasil

                col = i if kiri_ke_kanan else (jumlah_titik - 1 - i)
                self.matrix_raw[baris, col] = value_raw
                self.matrix[baris, col] = value_corrected
                n_done += 1

                print(
                    f"[SpatialScanRecorder] titik ({baris},{col}) "
                    f"raw={value_raw:.6g} terkoreksi={value_corrected:.6g} "
                    f"({n_done}/{n_total})"
                )

                if self.on_point_captured:
                    self.on_point_captured(
                        col, baris, value_raw, value_corrected, n_done, n_total
                    )
                else:
                    print("[SpatialScanRecorder] PERINGATAN: on_point_captured belum di-set!")

                if i < jumlah_titik - 1:
                    t_cursor += dwell_s + travel_point_s

            if baris < jumlah_baris - 1:
                t_cursor += dwell_s + travel_row_s

        self._running = False
        print(
            "[SpatialScanRecorder] SELESAI. matrix min/max/mean =",
            self.matrix.min(), self.matrix.max(), self.matrix.mean(),
        )
        if self.on_finished:
            self.on_finished(self.matrix)
        else:
            print("[SpatialScanRecorder] PERINGATAN: on_finished belum di-set!")
