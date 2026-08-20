#include "backend/spatial_scan_recorder.hpp"

#include <chrono>
#include <cmath>
#include <thread>

#include "backend/config.hpp"
#include "backend/scan_timing.hpp"
#include "backend/spatial_mapping.hpp"

namespace pa {

SpatialScanRecorder::SpatialScanRecorder(
    AudioCapture* audio, double point_distance_cm, double row_distance_cm,
    int scan_step_delay_us, double step_per_cm_x, int break_time_ms,
    double target_freq_hz, double freq_tolerance_hz, int fft_n, int n_avg,
    double settling_time_ms)
    : audio_(audio),
      point_distance_cm_(point_distance_cm),
      row_distance_cm_(row_distance_cm),
      scan_speed_cm_s_(scan_speed_cm_s(scan_step_delay_us, step_per_cm_x)),
      break_time_ms_(break_time_ms),
      freq_tolerance_hz_(freq_tolerance_hz),
      fft_n_(fft_n),
      n_avg_(std::max(n_avg, 1)),
      settling_time_s_(settling_time_ms / 1000.0),
      target_freq_hz(target_freq_hz) {
  acquisition_s_ = (n_avg_ * fft_n_) / static_cast<double>(audio_->samplerate());
  min_dwell_s_ = settling_time_s_ + acquisition_s_;
}

void SpatialScanRecorder::startRecording(double x_cm, double y_cm) {
  const int jumlah_titik =
      static_cast<int>(std::llround(x_cm / point_distance_cm_)) + 1;
  const int jumlah_baris =
      static_cast<int>(std::llround(y_cm / row_distance_cm_)) + 1;
  if (jumlah_titik < 1 || jumlah_baris < 1) return;

  rows = jumlah_baris;
  cols = jumlah_titik;
  matrix.assign(static_cast<size_t>(rows * cols), 0.0);
  matrix_raw.assign(static_cast<size_t>(rows * cols), 0.0);
  running_ = true;
  if (thread_.joinable()) thread_.join();
  thread_ = std::thread([this, jumlah_titik, jumlah_baris]() {
    try {
      recordLoop(jumlah_titik, jumlah_baris);
    } catch (const std::exception& e) {
      if (on_error) on_error(e.what());
    }
    running_ = false;
    if (on_finished) on_finished();
  });
}

void SpatialScanRecorder::stop() {
  running_ = false;
  if (thread_.joinable()) thread_.join();
}

void SpatialScanRecorder::notifyRowSync(int row1_based) {
  std::lock_guard<std::mutex> g(sync_lock_);
  sync_row_ = row1_based;
}

std::pair<double, double> SpatialScanRecorder::measurePoint() {
  std::vector<double> freqs;
  std::vector<double> mag_sum;
  for (int i = 0; i < n_avg_ && running_; ++i) {
    auto samples = audio_->captureSamples(fft_n_);
    auto [f, m] = audio_->computeFft(samples);
    if (f.empty()) continue;
    if (mag_sum.empty()) {
      freqs = f;
      mag_sum.assign(m.begin(), m.end());
    } else {
      for (size_t k = 0; k < mag_sum.size() && k < m.size(); ++k)
        mag_sum[k] += m[k];
    }
  }
  if (freqs.empty()) return {0.0, 0.0};
  for (double& v : mag_sum) v /= n_avg_;

  double raw = 0.0;
  if (target_freq_hz <= 0) {
    double best = -1.0;
    double best_f = TARGET_FREQ_HZ;
    for (size_t i = 0; i < freqs.size(); ++i) {
      if (freqs[i] < AUTO_TARGET_MIN_HZ || freqs[i] > AUTO_TARGET_MAX_HZ)
        continue;
      if (mag_sum[i] > best) {
        best = mag_sum[i];
        best_f = freqs[i];
      }
    }
    target_freq_hz = best_f;
    raw = best > 0 ? best : 0.0;
    if (on_target_detected) on_target_detected(target_freq_hz, raw);
  } else {
    raw = extract_amplitude_object_black_background(
        freqs, mag_sum, target_freq_hz, freq_tolerance_hz_);
  }
  const double noise = estimasi_noise_floor(
      freqs, mag_sum, target_freq_hz, freq_tolerance_hz_, NOISE_SIDEBAND_FACTOR);
  const double corrected = std::max(raw - noise, 0.0);
  return {raw, corrected};
}

void SpatialScanRecorder::recordLoop(int jumlah_titik, int jumlah_baris) {
  const int n_total = jumlah_titik * jumlah_baris;
  int n_done = 0;
  const double dwell_s = break_time_ms_ / 1000.0;
  if (dwell_s < min_dwell_s_ && on_timing_warning) {
    on_timing_warning(
        "BREAK_TIME_MS lebih kecil dari settling+acquisition; jadwal bisa molor.");
  }

  for (int row = 0; row < jumlah_baris && running_; ++row) {
    const bool reverse = (row % 2) == 1;
    for (int i = 0; i < jumlah_titik && running_; ++i) {
      const int col = reverse ? (jumlah_titik - 1 - i) : i;
      const auto t0 = std::chrono::steady_clock::now();
      std::this_thread::sleep_for(
          std::chrono::duration<double>(settling_time_s_));
      auto [raw, corrected] = measurePoint();
      matrix_raw[static_cast<size_t>(row * cols + col)] = raw;
      matrix[static_cast<size_t>(row * cols + col)] = corrected;
      ++n_done;
      if (on_point_captured)
        on_point_captured(col, row, raw, corrected, n_done, n_total);

      const auto elapsed = std::chrono::steady_clock::now() - t0;
      const double elapsed_s =
          std::chrono::duration<double>(elapsed).count();
      const double remain = dwell_s - elapsed_s;
      if (remain > 0)
        std::this_thread::sleep_for(std::chrono::duration<double>(remain));

      if (i + 1 < jumlah_titik) {
        const double travel = point_distance_cm_ / scan_speed_cm_s_;
        std::this_thread::sleep_for(std::chrono::duration<double>(travel));
      }
    }
    if (row + 1 < jumlah_baris) {
      const double travel = row_distance_cm_ / scan_speed_cm_s_;
      std::this_thread::sleep_for(std::chrono::duration<double>(travel));
    }
  }
}

}  // namespace pa
