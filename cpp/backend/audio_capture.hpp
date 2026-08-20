#pragma once

#include <atomic>
#include <condition_variable>
#include <cstdint>
#include <functional>
#include <mutex>
#include <string>
#include <utility>
#include <vector>

namespace pa {

class AudioCapture {
 public:
  using ErrorCallback = std::function<void(const std::string&)>;

  explicit AudioCapture(ErrorCallback on_error = nullptr);
  ~AudioCapture();

  static std::vector<std::pair<int, std::string>> listInputDevices(
      bool force_rescan = true);

  std::pair<bool, std::string> start(int device_index, int samplerate = -1,
                                     int channels = 1,
                                     double buffer_seconds = 1.0,
                                     int blocksize = 1024);
  void stop();
  bool isRunning() const { return running_; }

  std::vector<float> getWaveform() const;
  std::pair<std::vector<double>, std::vector<double>> getFft(
      double min_freq = 0.0, double max_freq = -1.0) const;
  std::pair<std::vector<double>, std::vector<double>> computeFft(
      const std::vector<float>& data, double min_freq = 0.0,
      double max_freq = -1.0) const;
  std::pair<double, double> getPeak(double min_freq = 20.0,
                                    double max_freq = -1.0) const;

  std::vector<float> captureSamples(int n, double timeout_s = 2.0);

  int samplerate() const { return samplerate_; }

 private:
  struct PaShim;
  static int paCallbackShim(const void* input, void* output,
                            unsigned long frame_count, const void* time_info,
                            unsigned long status_flags, void* user_data);

  std::pair<std::vector<double>, std::vector<double>> fftCore(
      const std::vector<float>& data, double min_freq, double max_freq) const;

  void* stream_ = nullptr;
  int samplerate_ = 192000;
  int channels_ = 1;
  int device_ = -1;
  int buffer_size_ = 192000;
  mutable std::mutex lock_;
  std::vector<float> buffer_;

  std::mutex capture_lock_;
  std::condition_variable capture_cv_;
  bool capture_active_ = false;
  std::vector<float> capture_chunks_;
  int capture_needed_ = 0;
  int capture_collected_ = 0;

  ErrorCallback on_error_;
  std::atomic<bool> running_{false};
};

}  // namespace pa
