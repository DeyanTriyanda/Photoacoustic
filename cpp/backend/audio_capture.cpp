#include "backend/audio_capture.hpp"

#include <algorithm>
#include <chrono>
#include <cmath>
#include <complex>
#include <cstring>
#include <mutex>
#include <stdexcept>

#include <portaudio.h>

#include "backend/config.hpp"

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

namespace pa {
namespace {

int next_pow2(int n) {
  int p = 1;
  while (p < n) p <<= 1;
  return p;
}

void fft_radix2(std::vector<std::complex<double>>* a) {
  const int n = static_cast<int>(a->size());
  if (n <= 1) return;
  // bit-reverse
  for (int i = 1, j = 0; i < n; ++i) {
    int bit = n >> 1;
    for (; j & bit; bit >>= 1) j ^= bit;
    j ^= bit;
    if (i < j) std::swap((*a)[static_cast<size_t>(i)], (*a)[static_cast<size_t>(j)]);
  }
  for (int len = 2; len <= n; len <<= 1) {
    const double ang = -2.0 * M_PI / len;
    const std::complex<double> wlen(std::cos(ang), std::sin(ang));
    for (int i = 0; i < n; i += len) {
      std::complex<double> w(1.0, 0.0);
      for (int j = 0; j < len / 2; ++j) {
        auto& u = (*a)[static_cast<size_t>(i + j)];
        auto v = (*a)[static_cast<size_t>(i + j + len / 2)] * w;
        (*a)[static_cast<size_t>(i + j + len / 2)] = u - v;
        u += v;
        w *= wlen;
      }
    }
  }
}

}  // namespace

AudioCapture::AudioCapture(ErrorCallback on_error)
    : on_error_(std::move(on_error)) {
  samplerate_ = AUDIO_SAMPLERATE;
  buffer_size_ = samplerate_;
  buffer_.assign(static_cast<size_t>(buffer_size_), 0.0f);
  static std::once_flag once;
  std::call_once(once, []() { Pa_Initialize(); });
}

AudioCapture::~AudioCapture() { stop(); }

std::vector<std::pair<int, std::string>> AudioCapture::listInputDevices(bool) {
  std::vector<std::pair<int, std::string>> out;
  const int n = Pa_GetDeviceCount();
  for (int i = 0; i < n; ++i) {
    const PaDeviceInfo* info = Pa_GetDeviceInfo(i);
    if (!info || info->maxInputChannels <= 0) continue;
    std::string label = std::to_string(i) + ": " + info->name + " (" +
                        std::to_string(info->maxInputChannels) + "ch, " +
                        std::to_string(static_cast<int>(info->defaultSampleRate)) +
                        "Hz)";
    out.emplace_back(i, label);
  }
  return out;
}

int AudioCapture::paCallbackShim(const void* input, void*,
                                 unsigned long frame_count, const void*,
                                 unsigned long statusFlags, void* user_data) {
  auto* self = static_cast<AudioCapture*>(user_data);
  if (statusFlags && self->on_error_) self->on_error_("PortAudio status flag");
  if (!input) return paContinue;
  const float* in = static_cast<const float*>(input);
  const int n = static_cast<int>(frame_count);

  {
    std::lock_guard<std::mutex> g(self->lock_);
    if (n >= self->buffer_size_) {
      for (int i = 0; i < self->buffer_size_; ++i)
        self->buffer_[static_cast<size_t>(i)] =
            in[(n - self->buffer_size_ + i) * self->channels_];
    } else {
      std::memmove(self->buffer_.data(), self->buffer_.data() + n,
                   sizeof(float) * static_cast<size_t>(self->buffer_size_ - n));
      for (int i = 0; i < n; ++i)
        self->buffer_[static_cast<size_t>(self->buffer_size_ - n + i)] =
            in[i * self->channels_];
    }
  }

  {
    std::lock_guard<std::mutex> g(self->capture_lock_);
    if (self->capture_active_) {
      const int remaining = self->capture_needed_ - self->capture_collected_;
      if (remaining > 0) {
        const int take = std::min(remaining, n);
        for (int i = 0; i < take; ++i)
          self->capture_chunks_.push_back(in[i * self->channels_]);
        self->capture_collected_ += take;
      }
    }
    if (self->capture_collected_ >= self->capture_needed_) {
      self->capture_active_ = false;
      self->capture_cv_.notify_all();
    }
  }
  return paContinue;
}

std::pair<bool, std::string> AudioCapture::start(int device_index, int samplerate,
                                                 int channels,
                                                 double buffer_seconds,
                                                 int blocksize) {
  if (running_) stop();
  if (samplerate < 0) samplerate = AUDIO_SAMPLERATE;
  device_ = device_index;
  samplerate_ = samplerate;
  channels_ = channels;
  buffer_size_ = std::max(static_cast<int>(samplerate * buffer_seconds), 1);
  {
    std::lock_guard<std::mutex> g(lock_);
    buffer_.assign(static_cast<size_t>(buffer_size_), 0.0f);
  }
  {
    std::lock_guard<std::mutex> g(capture_lock_);
    capture_active_ = false;
    capture_chunks_.clear();
    capture_needed_ = 0;
    capture_collected_ = 0;
  }

  PaStreamParameters params{};
  params.device = device_index;
  params.channelCount = channels;
  params.sampleFormat = paFloat32;
  params.suggestedLatency =
      Pa_GetDeviceInfo(device_index)
          ? Pa_GetDeviceInfo(device_index)->defaultLowInputLatency
          : 0.05;
  params.hostApiSpecificStreamInfo = nullptr;

  PaStream* stream = nullptr;
  const PaError err2 = Pa_OpenStream(
      &stream, &params, nullptr, samplerate, blocksize, paClipOff,
      [](const void* input, void* output, unsigned long frames,
         const PaStreamCallbackTimeInfo*, PaStreamCallbackFlags flags,
         void* user) -> int {
        return AudioCapture::paCallbackShim(
            input, output, frames, nullptr, static_cast<unsigned long>(flags),
            user);
      },
      this);
  if (err2 != paNoError) return {false, Pa_GetErrorText(err2)};
  if (Pa_StartStream(stream) != paNoError) {
    Pa_CloseStream(stream);
    return {false, "Gagal start PortAudio stream"};
  }
  stream_ = stream;
  running_ = true;
  return {true, "Audio stream dimulai (device " + std::to_string(device_index) +
                    ", " + std::to_string(samplerate) + " Hz)"};
}

void AudioCapture::stop() {
  running_ = false;
  {
    std::lock_guard<std::mutex> g(capture_lock_);
    capture_active_ = false;
    capture_cv_.notify_all();
  }
  if (stream_) {
    Pa_StopStream(static_cast<PaStream*>(stream_));
    Pa_CloseStream(static_cast<PaStream*>(stream_));
    stream_ = nullptr;
  }
}

std::vector<float> AudioCapture::getWaveform() const {
  std::lock_guard<std::mutex> g(lock_);
  return buffer_;
}

std::pair<std::vector<double>, std::vector<double>> AudioCapture::fftCore(
    const std::vector<float>& data, double min_freq, double max_freq) const {
  const int n_in = static_cast<int>(data.size());
  std::vector<double> freqs, mag;
  if (n_in <= 1) return {freqs, mag};

  // Zero-pad ke power-of-2 untuk FFT cepat (mirip resolusi Python penuh)
  const int n = next_pow2(n_in);
  std::vector<std::complex<double>> a(static_cast<size_t>(n), {0.0, 0.0});
  double win_sum = 0.0;
  for (int i = 0; i < n_in; ++i) {
    const double w =
        (n_in == 1) ? 1.0
                    : 0.5 * (1.0 - std::cos(2.0 * M_PI * i / (n_in - 1)));
    win_sum += w;
    a[static_cast<size_t>(i)] = {data[static_cast<size_t>(i)] * w, 0.0};
  }
  const double win_corr = (win_sum > 0) ? (n_in / win_sum) : 1.0;
  fft_radix2(&a);

  const int n_out = n / 2 + 1;
  freqs.resize(static_cast<size_t>(n_out));
  mag.resize(static_cast<size_t>(n_out));
  for (int k = 0; k < n_out; ++k) {
    double m = std::abs(a[static_cast<size_t>(k)]) / n_in * 2.0 * win_corr;
    if (k == 0) m *= 0.5;
    freqs[static_cast<size_t>(k)] = static_cast<double>(k) * samplerate_ / n;
    mag[static_cast<size_t>(k)] = m;
  }

  if (max_freq < 0) max_freq = samplerate_ / 2.0;
  std::vector<double> f2, m2;
  f2.reserve(static_cast<size_t>(n_out));
  m2.reserve(static_cast<size_t>(n_out));
  for (size_t i = 0; i < freqs.size(); ++i) {
    if (freqs[i] >= min_freq && freqs[i] <= max_freq) {
      f2.push_back(freqs[i]);
      m2.push_back(mag[i]);
    }
  }
  return {f2, m2};
}

std::pair<std::vector<double>, std::vector<double>> AudioCapture::getFft(
    double min_freq, double max_freq) const {
  // UI: potong ke max 65536 sample terakhir (resolusi baik, tetap ~60 FPS).
  // Scan/capture memakai computeFft pada blok penuh tanpa batas ini.
  auto wave = getWaveform();
  constexpr int kUiMax = 65536;
  if (static_cast<int>(wave.size()) > kUiMax)
    wave.erase(wave.begin(),
               wave.end() - static_cast<std::ptrdiff_t>(kUiMax));
  return fftCore(wave, min_freq, max_freq);
}

std::pair<std::vector<double>, std::vector<double>> AudioCapture::computeFft(
    const std::vector<float>& data, double min_freq, double max_freq) const {
  return fftCore(data, min_freq, max_freq);
}

std::pair<double, double> AudioCapture::getPeak(double min_freq,
                                                double max_freq) const {
  auto [freqs, mag] = getFft(min_freq, max_freq);
  if (mag.empty()) return {0.0, 0.0};
  size_t idx = 0;
  for (size_t i = 1; i < mag.size(); ++i)
    if (mag[i] > mag[idx]) idx = i;
  return {freqs[idx], mag[idx]};
}

std::vector<float> AudioCapture::captureSamples(int n, double timeout_s) {
  if (!running_ || !stream_)
    throw std::runtime_error("Audio stream belum berjalan");
  {
    std::lock_guard<std::mutex> g(capture_lock_);
    capture_chunks_.clear();
    capture_needed_ = n;
    capture_collected_ = 0;
    capture_active_ = true;
  }
  std::unique_lock<std::mutex> lk(capture_lock_);
  const bool ok = capture_cv_.wait_for(
      lk, std::chrono::duration<double>(timeout_s),
      [&]() { return !capture_active_; });
  capture_active_ = false;
  if (!ok) throw std::runtime_error("captureSamples timeout");
  if (static_cast<int>(capture_chunks_.size()) > n)
    capture_chunks_.resize(static_cast<size_t>(n));
  return capture_chunks_;
}

}  // namespace pa
