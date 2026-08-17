#include "../include/fft.hpp"

#include <cmath>
#include <mutex>
#include <vector>

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

// Pakai double agar skala mendekati NumPy/FFTW sebelumnya.
#define kiss_fft_scalar double
#include "../third_party/kissfft/kiss_fft.h"
#include "../third_party/kissfft/kiss_fftr.h"

namespace pa {
namespace {

std::mutex g_fft_mutex;

}  // namespace

std::pair<std::vector<double>, std::vector<double>> compute_rfft(
    const float* data, std::size_t n, double samplerate,
    bool use_hann, double min_freq, double max_freq) {
    std::vector<double> freqs_out;
    std::vector<double> mag_out;
    if (n == 0 || data == nullptr || samplerate <= 0.0) {
        return {freqs_out, mag_out};
    }
    // kiss_fftr membutuhkan n even
    if ((n % 2) != 0) {
        --n;
        if (n == 0) return {freqs_out, mag_out};
    }
    if (max_freq < 0.0) max_freq = samplerate / 2.0;

    std::vector<kiss_fft_scalar> windowed(n);
    double win_sum = 0.0;
    for (std::size_t i = 0; i < n; ++i) {
        double w = 1.0;
        if (use_hann) {
            if (n == 1) {
                w = 1.0;
            } else {
                w = 0.5 - 0.5 * std::cos(2.0 * M_PI * static_cast<double>(i) /
                                         static_cast<double>(n - 1));
            }
        }
        windowed[i] = static_cast<kiss_fft_scalar>(static_cast<double>(data[i]) * w);
        win_sum += w;
    }
    const double window_correction =
        (win_sum > 0.0) ? (static_cast<double>(n) / win_sum) : 1.0;

    const int n_out = static_cast<int>(n / 2) + 1;
    std::vector<kiss_fft_cpx> spectrum(static_cast<std::size_t>(n_out));

    {
        std::lock_guard<std::mutex> lock(g_fft_mutex);
        kiss_fftr_cfg cfg = kiss_fftr_alloc(static_cast<int>(n), 0, nullptr, nullptr);
        if (cfg == nullptr) {
            return {freqs_out, mag_out};
        }
        kiss_fftr(cfg, windowed.data(), spectrum.data());
        kiss_fftr_free(cfg);
    }

    freqs_out.reserve(static_cast<std::size_t>(n_out));
    mag_out.reserve(static_cast<std::size_t>(n_out));
    for (int k = 0; k < n_out; ++k) {
        const double freq = static_cast<double>(k) * samplerate / static_cast<double>(n);
        if (freq < min_freq || freq > max_freq) continue;
        const double re = spectrum[static_cast<std::size_t>(k)].r;
        const double im = spectrum[static_cast<std::size_t>(k)].i;
        double mag = std::sqrt(re * re + im * im) / static_cast<double>(n) * 2.0 *
                     window_correction;
        if (k == 0) mag /= 2.0;
        freqs_out.push_back(freq);
        mag_out.push_back(mag);
    }
    return {freqs_out, mag_out};
}

}  // namespace pa
