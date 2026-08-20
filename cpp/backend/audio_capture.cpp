#include "backend/audio_capture.hpp"

#include <algorithm>
#include <chrono>
#include <cmath>
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

}  // namespace

AudioCapture::AudioCapture(ErrorCallback on_error)
    : on_error_(std::move(on_error)) {
  samplerate_ = AUDIO_SAMPLERATE;
  buffer_size_ = samplerate_;
  ring_.assign(static_cast<size_t>(buffer_size_), 0.0f);
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
    out.emplace_back(i, std::to_string(i) + ": " + info->name + " (" +
                            std::to_string(info->maxInputChannels) + "ch, " +
                            std::to_string(static_cast<int>(info->defaultSampleRate)) +
                            "Hz)");
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
  const int ch = self->channels_;
  const int cap = self->buffer_size_;

  {
    std::lock_guard<std::mutex> g(self->lock_);
    for (int i = 0; i < n; ++i) {
      self->ring_[static_cast<size_t>(self->ring_pos_)] = in[i * ch];
      self->ring_pos_ = (self->ring_pos_ + 1) % cap;
      if (self->ring_filled_ < cap) ++self->ring_filled_;
    }
  }

  {
    std::lock_guard<std::mutex> g(self->capture_lock_);
    if (self->capture_active_) {
      const int remaining = self->capture_needed_ - self->capture_collected_;
      if (remaining > 0) {
        const int take = std::min(remaining, n);
        const size_t old = self->capture_chunks_.size();
        self->capture_chunks_.resize(old + static_cast<size_t>(take));
        for (int i = 0; i < take; ++i)
          self->capture_chunks_[old + static_cast<size_t>(i)] = in[i * ch];
        self->capture_collected_ += take;
      }
      if (self->capture_collected_ >= self->capture_needed_) {
        self->capture_active_ = false;
        self->capture_cv_.notify_all();
      }
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
    ring_.assign(static_cast<size_t>(buffer_size_), 0.0f);
    ring_pos_ = 0;
    ring_filled_ = 0;
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
  const PaError err = Pa_OpenStream(
      &stream, &params, nullptr, samplerate, blocksize, paClipOff,
      [](const void* input, void* output, unsigned long frames,
         const PaStreamCallbackTimeInfo*, PaStreamCallbackFlags flags,
         void* user) -> int {
        return AudioCapture::paCallbackShim(
            input, output, frames, nullptr, static_cast<unsigned long>(flags),
            user);
      },
      this);
  if (err != paNoError) return {false, Pa_GetErrorText(err)};
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

int AudioCapture::copyLast(float* dst, int n) const {
  if (!dst || n <= 0) return 0;
  std::lock_guard<std::mutex> g(lock_);
  const int avail = ring_filled_;
  const int take = std::min(n, avail);
  if (take <= 0) return 0;
  const int cap = buffer_size_;
  // Sample tertua di antara yang diambil: ring_pos_ - take (mod)
  int start = ring_pos_ - take;
  if (start < 0) start += cap;
  for (int i = 0; i < take; ++i)
    dst[i] = ring_[static_cast<size_t>((start + i) % cap)];
  return take;
}

std::vector<float> AudioCapture::getWaveform() const {
  std::vector<float> out(static_cast<size_t>(buffer_size_));
  const int n = copyLast(out.data(), buffer_size_);
  out.resize(static_cast<size_t>(n));
  return out;
}

void AudioCapture::fftRadix2(std::vector<std::complex<double>>* a) const {
  const int n = static_cast<int>(a->size());
  if (n <= 1) return;
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

void AudioCapture::ensureScratch(int n) const {
  if (static_cast<int>(fft_buf_.size()) != n) {
    fft_buf_.assign(static_cast<size_t>(n), {0.0, 0.0});
  }
  if (hann_n_ != n) {
    hann_.resize(static_cast<size_t>(n));
    for (int i = 0; i < n; ++i)
      hann_[static_cast<size_t>(i)] =
          (n == 1) ? 1.0
                   : 0.5 * (1.0 - std::cos(2.0 * M_PI * i / (n - 1)));
    hann_n_ = n;
  }
}

void AudioCapture::computeFftInto(const float* data, int n_in, double min_freq,
                                  double max_freq, std::vector<double>* freqs_out,
                                  std::vector<double>* mag_out) const {
  freqs_out->clear();
  mag_out->clear();
  if (!data || n_in <= 1) return;

  const int n = next_pow2(n_in);
  std::lock_guard<std::mutex> g(fft_lock_);
  ensureScratch(n);
  std::fill(fft_buf_.begin(), fft_buf_.end(), std::complex<double>{0.0, 0.0});

  double win_sum = 0.0;
  // Hann untuk panjang n_in (bukan n padded)
  for (int i = 0; i < n_in; ++i) {
    const double w =
        (n_in == 1) ? 1.0
                    : 0.5 * (1.0 - std::cos(2.0 * M_PI * i / (n_in - 1)));
    win_sum += w;
    fft_buf_[static_cast<size_t>(i)] = {data[i] * w, 0.0};
  }
  const double win_corr = (win_sum > 0) ? (n_in / win_sum) : 1.0;
  fftRadix2(&fft_buf_);

  if (max_freq < 0) max_freq = samplerate_ / 2.0;
  const int n_out = n / 2 + 1;
  const int k0 = std::max(0, static_cast<int>(std::ceil(min_freq * n / samplerate_)));
  const int k1 = std::min(n_out - 1,
                          static_cast<int>(std::floor(max_freq * n / samplerate_)));
  const int count = std::max(0, k1 - k0 + 1);
  freqs_out->resize(static_cast<size_t>(count));
  mag_out->resize(static_cast<size_t>(count));
  for (int k = k0; k <= k1; ++k) {
    double m = std::abs(fft_buf_[static_cast<size_t>(k)]) / n_in * 2.0 * win_corr;
    if (k == 0) m *= 0.5;
    const int j = k - k0;
    (*freqs_out)[static_cast<size_t>(j)] =
        static_cast<double>(k) * samplerate_ / n;
    (*mag_out)[static_cast<size_t>(j)] = m;
  }
}

std::pair<std::vector<double>, std::vector<double>> AudioCapture::getFft(
    double min_freq, double max_freq) const {
  std::vector<float> snap(static_cast<size_t>(kUiFftSamples));
  const int n = copyLast(snap.data(), kUiFftSamples);
  snap.resize(static_cast<size_t>(n));
  std::vector<double> f, m;
  computeFftInto(snap.data(), n, min_freq, max_freq, &f, &m);
  return {std::move(f), std::move(m)};
}

std::pair<std::vector<double>, std::vector<double>> AudioCapture::computeFft(
    const std::vector<float>& data, double min_freq, double max_freq) const {
  std::vector<double> f, m;
  computeFftInto(data.data(), static_cast<int>(data.size()), min_freq, max_freq,
                 &f, &m);
  return {std::move(f), std::move(m)};
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
    capture_chunks_.reserve(static_cast<size_t>(n));
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
