#pragma once

#include <atomic>
#include <functional>
#include <mutex>
#include <string>
#include <thread>
#include <vector>

#include "backend/audio_capture.hpp"

namespace pa {

class SpatialScanRecorder {
 public:
  using PointCb = std::function<void(int col, int row, double raw, double corrected,
                                     int n_done, int n_total)>;
  using VoidCb = std::function<void()>;
  using StrCb = std::function<void(const std::string&)>;
  using TargetCb = std::function<void(double freq_hz, double amp)>;

  SpatialScanRecorder(AudioCapture* audio, double point_distance_cm,
                      double row_distance_cm, int scan_step_delay_us,
                      double step_per_cm_x, int break_time_ms,
                      double target_freq_hz, double freq_tolerance_hz = 50.0,
                      int fft_n = 4096, int n_avg = 4,
                      double settling_time_ms = 40.0);

  void startRecording(double x_cm, double y_cm);
  void stop();
  bool isRunning() const { return running_; }

  void notifyRowSync(int row1_based);

  std::vector<double> matrix;      // corrected
  std::vector<double> matrix_raw;  // raw
  int rows = 0;
  int cols = 0;

  PointCb on_point_captured;
  VoidCb on_finished;
  StrCb on_timing_warning;
  StrCb on_error;
  TargetCb on_target_detected;

  double target_freq_hz = -1.0;

 private:
  void recordLoop(int jumlah_titik, int jumlah_baris);
  std::pair<double, double> measurePoint();

  AudioCapture* audio_;
  double point_distance_cm_;
  double row_distance_cm_;
  double scan_speed_cm_s_;
  int break_time_ms_;
  double freq_tolerance_hz_;
  int fft_n_;
  int n_avg_;
  double settling_time_s_;
  double acquisition_s_;
  double min_dwell_s_;

  std::atomic<bool> running_{false};
  std::thread thread_;

  std::mutex sync_lock_;
  int sync_row_ = -1;
};

}  // namespace pa
