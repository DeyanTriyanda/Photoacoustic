#pragma once

#include <atomic>
#include <condition_variable>
#include <cstddef>
#include <mutex>
#include <string>
#include <utility>
#include <vector>

namespace pa {

struct DeviceInfo {
    int index = -1;
    std::string label;
};

class AudioCapture {
public:
    AudioCapture() = default;
    ~AudioCapture();

    AudioCapture(const AudioCapture&) = delete;
    AudioCapture& operator=(const AudioCapture&) = delete;

    static std::vector<DeviceInfo> list_input_devices(bool force_rescan = true);

    std::pair<bool, std::string> start(int device_index, int samplerate = 96000,
                                       int channels = 1, double buffer_seconds = 1.0,
                                       int blocksize = 1024);
    void stop();
    bool is_running() const { return running_.load(); }

    std::vector<float> get_waveform() const;
    std::pair<std::vector<double>, std::vector<double>> get_fft(
        bool use_hann = true, double min_freq = 0.0, double max_freq = -1.0) const;
    std::pair<std::vector<double>, std::vector<double>> compute_fft(
        const std::vector<float>& data, bool use_hann = true,
        double min_freq = 0.0, double max_freq = -1.0) const;
    std::pair<double, double> get_peak(double min_freq = 20.0,
                                       double max_freq = -1.0) const;

    std::vector<float> capture_samples(int n, double timeout = 2.0);

    int samplerate() const { return samplerate_; }
    std::string last_error() const;

    // Dipakai PortAudio callback di .cpp
    void handle_callback(const float* input, unsigned long frames,
                         unsigned long status_flags);

private:
    mutable std::mutex buffer_mutex_;
    std::vector<float> buffer_;
    std::size_t buffer_size_ = 0;

    std::mutex capture_mutex_;
    std::condition_variable capture_cv_;
    bool capture_active_ = false;
    int capture_needed_ = 0;
    int capture_collected_ = 0;
    std::vector<float> capture_chunks_;

    mutable std::mutex error_mutex_;
    std::string last_error_;

    void* stream_ = nullptr;  // PaStream*
    int samplerate_ = 96000;
    int channels_ = 1;
    int device_ = -1;
    std::atomic<bool> running_{false};
};

}  // namespace pa
