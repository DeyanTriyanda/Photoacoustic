#pragma once

#include <cstddef>
#include <utility>
#include <vector>

namespace pa {

double extract_amplitude_at_frequency(const double* freqs, const double* magnitude,
                                      std::size_t n, double target_freq_hz,
                                      double tolerance_hz = 50.0);

double estimasi_noise_floor(const double* freqs, const double* mag, std::size_t n,
                            double target_freq_hz, double tolerance_hz,
                            double sideband_factor = 5.0);

// Return grayscale (row-major uint8), amp_min, amp_max
struct GrayScaleResult {
    std::vector<unsigned char> gray;
    int rows = 0;
    int cols = 0;
    double amp_min = 0.0;
    double amp_max = 0.0;
};

GrayScaleResult amplitude_matrix_to_grayscale(
    const double* matrix, int rows, int cols,
    const unsigned char* captured_mask /* nullable, 0/1 per cell */,
    bool has_fixed_range, double amp_min_fixed, double amp_max_fixed);

}  // namespace pa
