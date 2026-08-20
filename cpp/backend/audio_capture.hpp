#pragma once

#include <atomic>
#include <complex>
#include <condition_variable>
#include <cstdint>
#include <functional>
#include <mutex>
#include <string>
#include <utility>
#include <vector>

namespace pa {

// Ukuran FFT UI tetap kecil → O(N log N) ringan @ ~30 FPS
constexpr int kUiFftSamples = 4096;

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

  // Salin N sample terakhir ke dst (tanpa alokasi). Return jumlah tersalin.
  int copyLast(float* dst, int n) const;

  // Waveform penuh (jarang dipakai); prefer copyLast di hot path.
  std::vector<float> getWaveform() const;

  // FFT dari buffer dst[n] yang sudah diisi caller (atau internal snapshot).
  void computeFftInto(const float* data, int n, double min_freq, double max_freq,
                      std::vector<double>* freqs_out,
                      std::vector<double>* mag_out) const;

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
  static int paCallbackShim(const void* input, void* output,
                            unsigned long frame_count, const void* time_info,
                            unsigned long status_flags, void* user_data);

  void fftRadix2(std::vector<std::complex<double>>* a) const;
  void ensureScratch(int n) const;

  void* stream_ = nullptr;
  int samplerate_ = 192000;
  int channels_ = 1;
  int device_ = -1;
  int buffer_size_ = 192000;

  // Ring buffer O(1) write — tanpa memmove tiap blok
  mutable std::mutex lock_;
  std::vector<float> ring_;
  int ring_pos_ = 0;  // next write index
  int ring_filled_ = 0;

  std::mutex capture_lock_;
  std::condition_variable capture_cv_;
  bool capture_active_ = false;
  std::vector<float> capture_chunks_;
  int capture_needed_ = 0;
  int capture_collected_ = 0;

  // Scratch FFT (reuse → hemat alokasi)
  mutable std::mutex fft_lock_;
  mutable std::vector<std::complex<double>> fft_buf_;
  mutable std::vector<double> hann_;
  mutable int hann_n_ = 0;

  ErrorCallback on_error_;
  std::atomic<bool> running_{false};
};

}  // namespace pa
