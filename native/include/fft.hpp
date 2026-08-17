#pragma once

#include <utility>
#include <vector>

namespace pa {

// Real FFT (FFTW) dengan jendela Hann opsional.
// Return freqs (Hz) dan magnitude (skala sama seperti backend Python lama).
std::pair<std::vector<double>, std::vector<double>> compute_rfft(
    const float* data, std::size_t n, double samplerate,
    bool use_hann, double min_freq, double max_freq);

}  // namespace pa
