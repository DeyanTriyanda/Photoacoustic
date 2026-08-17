#include "../include/audio_capture.hpp"

#include "../include/fft.hpp"

#include <algorithm>
#include <chrono>
#include <cstring>
#include <sstream>
#include <stdexcept>

#include <portaudio.h>

namespace pa {
namespace {

std::once_flag g_pa_once;
std::mutex g_pa_mutex;

void ensure_pa_initialized() {
    std::call_once(g_pa_once, []() {
        Pa_Initialize();
    });
}

int pa_callback(const void* input, void* /*output*/, unsigned long frame_count,
                const PaStreamCallbackTimeInfo* /*time_info*/,
                PaStreamCallbackFlags status_flags, void* user_data) {
    auto* self = static_cast<AudioCapture*>(user_data);
    self->handle_callback(static_cast<const float*>(input), frame_count,
                          static_cast<unsigned long>(status_flags));
    return paContinue;
}

}  // namespace

AudioCapture::~AudioCapture() { stop(); }

std::vector<DeviceInfo> AudioCapture::list_input_devices(bool force_rescan) {
    std::lock_guard<std::mutex> lock(g_pa_mutex);
    ensure_pa_initialized();
    if (force_rescan) {
        Pa_Terminate();
        Pa_Initialize();
    }

    std::vector<DeviceInfo> hasil;
    const int n = Pa_GetDeviceCount();
    if (n < 0) return hasil;
    for (int idx = 0; idx < n; ++idx) {
        const PaDeviceInfo* info = Pa_GetDeviceInfo(idx);
        if (info == nullptr || info->maxInputChannels <= 0) continue;
        std::ostringstream oss;
        oss << idx << ": " << info->name << " (" << info->maxInputChannels
            << "ch, " << static_cast<int>(info->defaultSampleRate) << "Hz)";
        hasil.push_back(DeviceInfo{idx, oss.str()});
    }
    return hasil;
}

void AudioCapture::handle_callback(const float* input, unsigned long frames,
                                   unsigned long status_flags) {
    if (status_flags != 0) {
        std::lock_guard<std::mutex> elock(error_mutex_);
        last_error_ = "PortAudio status flags=" + std::to_string(status_flags);
    }
    if (input == nullptr || frames == 0) return;

    // Ambil channel 0 (interleaved).
    std::vector<float> mono(frames);
    if (channels_ <= 1) {
        std::memcpy(mono.data(), input, frames * sizeof(float));
    } else {
        for (unsigned long i = 0; i < frames; ++i) {
            mono[i] = input[i * static_cast<unsigned long>(channels_)];
        }
    }

    {
        std::lock_guard<std::mutex> lock(buffer_mutex_);
        if (buffer_.size() != buffer_size_) buffer_.assign(buffer_size_, 0.0f);
        const std::size_t n = mono.size();
        if (n >= buffer_size_) {
            std::memcpy(buffer_.data(), mono.data() + (n - buffer_size_),
                        buffer_size_ * sizeof(float));
        } else {
            std::memmove(buffer_.data(), buffer_.data() + n,
                         (buffer_size_ - n) * sizeof(float));
            std::memcpy(buffer_.data() + (buffer_size_ - n), mono.data(),
                        n * sizeof(float));
        }
    }

    {
        std::lock_guard<std::mutex> lock(capture_mutex_);
        if (!capture_active_) return;
        const int remaining = capture_needed_ - capture_collected_;
        if (remaining > 0) {
            const int take = std::min(remaining, static_cast<int>(mono.size()));
            capture_chunks_.insert(capture_chunks_.end(), mono.begin(),
                                   mono.begin() + take);
            capture_collected_ += take;
        }
        if (capture_collected_ >= capture_needed_) {
            capture_active_ = false;
            capture_cv_.notify_all();
        }
    }
}

std::pair<bool, std::string> AudioCapture::start(int device_index, int samplerate,
                                                 int channels, double buffer_seconds,
                                                 int blocksize) {
    if (running_.load()) stop();

    std::lock_guard<std::mutex> lock(g_pa_mutex);
    ensure_pa_initialized();

    device_ = device_index;
    samplerate_ = samplerate;
    channels_ = channels;
    buffer_size_ = static_cast<std::size_t>(std::max(1, static_cast<int>(samplerate * buffer_seconds)));

    {
        std::lock_guard<std::mutex> block(buffer_mutex_);
        buffer_.assign(buffer_size_, 0.0f);
    }
    {
        std::lock_guard<std::mutex> clock(capture_mutex_);
        capture_active_ = false;
        capture_chunks_.clear();
        capture_needed_ = 0;
        capture_collected_ = 0;
    }

    PaStreamParameters params{};
    params.device = device_index;
    params.channelCount = channels;
    params.sampleFormat = paFloat32;
    params.suggestedLatency = Pa_GetDeviceInfo(device_index)
                                  ? Pa_GetDeviceInfo(device_index)->defaultLowInputLatency
                                  : 0.05;
    params.hostApiSpecificStreamInfo = nullptr;

    PaStream* stream = nullptr;
    PaError err = Pa_OpenStream(&stream, &params, nullptr, samplerate, blocksize,
                                paClipOff, pa_callback, this);
    if (err != paNoError) {
        return {false, Pa_GetErrorText(err)};
    }
    err = Pa_StartStream(stream);
    if (err != paNoError) {
        Pa_CloseStream(stream);
        return {false, Pa_GetErrorText(err)};
    }

    stream_ = stream;
    running_ = true;
    std::ostringstream oss;
    oss << "Audio stream dimulai (device " << device_index << ", " << samplerate << " Hz)";
    return {true, oss.str()};
}

void AudioCapture::stop() {
    running_ = false;
    {
        std::lock_guard<std::mutex> lock(capture_mutex_);
        capture_active_ = false;
        capture_cv_.notify_all();
    }

    std::lock_guard<std::mutex> lock(g_pa_mutex);
    if (stream_ != nullptr) {
        PaStream* stream = static_cast<PaStream*>(stream_);
        Pa_StopStream(stream);
        Pa_CloseStream(stream);
        stream_ = nullptr;
    }
}

std::vector<float> AudioCapture::get_waveform() const {
    std::lock_guard<std::mutex> lock(buffer_mutex_);
    return buffer_;
}

std::pair<std::vector<double>, std::vector<double>> AudioCapture::get_fft(
    bool use_hann, double min_freq, double max_freq) const {
    auto wave = get_waveform();
    return compute_rfft(wave.data(), wave.size(), samplerate_, use_hann, min_freq,
                        max_freq);
}

std::pair<std::vector<double>, std::vector<double>> AudioCapture::compute_fft(
    const std::vector<float>& data, bool use_hann, double min_freq,
    double max_freq) const {
    return compute_rfft(data.data(), data.size(), samplerate_, use_hann, min_freq,
                        max_freq);
}

std::pair<double, double> AudioCapture::get_peak(double min_freq,
                                                 double max_freq) const {
    auto [freqs, mag] = get_fft(true, min_freq, max_freq);
    if (mag.empty()) return {0.0, 0.0};
    std::size_t idx = 0;
    for (std::size_t i = 1; i < mag.size(); ++i) {
        if (mag[i] > mag[idx]) idx = i;
    }
    return {freqs[idx], mag[idx]};
}

std::vector<float> AudioCapture::capture_samples(int n, double timeout) {
    if (!running_.load() || stream_ == nullptr) {
        throw std::runtime_error(
            "Audio stream belum berjalan -- panggil start() dulu");
    }

    {
        std::lock_guard<std::mutex> lock(capture_mutex_);
        capture_chunks_.clear();
        capture_needed_ = n;
        capture_collected_ = 0;
        capture_active_ = true;
    }

    std::unique_lock<std::mutex> lock(capture_mutex_);
    const bool ok = capture_cv_.wait_for(
        lock, std::chrono::duration<double>(timeout),
        [&]() { return !capture_active_ || !running_.load(); });

    capture_active_ = false;
    if (!ok || capture_collected_ < capture_needed_) {
        throw std::runtime_error(
            "capture_samples timeout -- cek apakah stream audio masih hidup");
    }

    if (static_cast<int>(capture_chunks_.size()) > capture_needed_) {
        capture_chunks_.resize(static_cast<std::size_t>(capture_needed_));
    }
    return capture_chunks_;
}

std::string AudioCapture::last_error() const {
    std::lock_guard<std::mutex> lock(error_mutex_);
    return last_error_;
}

}  // namespace pa
