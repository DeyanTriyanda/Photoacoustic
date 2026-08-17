#include "fft.hpp"

#include <cmath>
#include <mutex>
#include <vector>

#include <fftw3.h>

namespace pa {
namespace {

std::mutex g_fftw_mutex;

}  // namespace

std::pair<std::vector<double>, std::vector<double>> compute_rfft(
    const float* data, std::size_t n, double samplerate,
    bool use_hann, double min_freq, double max_freq) {
    std::vector<double> freqs_out;
    std::vector<double> mag_out;
    if (n == 0 || data == nullptr || samplerate <= 0.0) {
        return {freqs_out, mag_out};
    }
    if (max_freq < 0.0) max_freq = samplerate / 2.0;

    std::vector<double> windowed(n);
    double win_sum = 0.0;
    for (std::size_t i = 0; i < n; ++i) {
        double w = 1.0;
        if (use_hann) {
            // Samakan dengan numpy.hanning(n)
            if (n == 1) {
                w = 1.0;
            } else {
                w = 0.5 - 0.5 * std::cos(2.0 * M_PI * static_cast<double>(i) /
                                         static_cast<double>(n - 1));
            }
        }
        windowed[i] = static_cast<double>(data[i]) * w;
        win_sum += w;
    }
    // Python: window_correction = 1/mean(win) = n/sum(win)
    const double window_correction = (win_sum > 0.0)
                                         ? (static_cast<double>(n) / win_sum)
                                         : 1.0;

    const int n_out = static_cast<int>(n / 2) + 1;
    std::vector<fftw_complex> spectrum(static_cast<std::size_t>(n_out));

    {
        std::lock_guard<std::mutex> lock(g_fftw_mutex);
        fftw_plan plan = fftw_plan_dft_r2c_1d(
            static_cast<int>(n), windowed.data(), spectrum.data(), FFTW_ESTIMATE);
        if (plan == nullptr) {
            return {freqs_out, mag_out};
        }
        fftw_execute(plan);
        fftw_destroy_plan(plan);
    }

    freqs_out.reserve(static_cast<std::size_t>(n_out));
    mag_out.reserve(static_cast<std::size_t>(n_out));
    for (int k = 0; k < n_out; ++k) {
        const double freq = static_cast<double>(k) * samplerate / static_cast<double>(n);
        if (freq < min_freq || freq > max_freq) continue;
        const double re = spectrum[static_cast<std::size_t>(k)][0];
        const double im = spectrum[static_cast<std::size_t>(k)][1];
        double mag = std::sqrt(re * re + im * im) / static_cast<double>(n) * 2.0 *
                     window_correction;
        if (k == 0) mag /= 2.0;
        freqs_out.push_back(freq);
        mag_out.push_back(mag);
    }
    return {freqs_out, mag_out};
}

}  // namespace pa
