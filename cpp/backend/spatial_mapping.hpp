#pragma once
#include <cstdint>
#include <vector>

namespace pa {

double extract_amplitude_at_frequency(const std::vector<double>& freqs,
                                      const std::vector<double>& magnitude,
                                      double target_freq_hz,
                                      double tolerance_hz = 50.0);

double extract_amplitude_object_black_background(
    const std::vector<double>& freqs, const std::vector<double>& magnitude,
    double target_freq_hz, double tolerance_hz = 50.0);

double estimasi_noise_floor(const std::vector<double>& freqs,
                            const std::vector<double>& mag,
                            double target_freq_hz, double tolerance_hz,
                            double sideband_factor = 5.0);

// Returns grayscale row-major HxW, plus amp_min/amp_max via out params.
std::vector<std::uint8_t> amplitude_matrix_to_grayscale(
    const std::vector<double>& matrix, int rows, int cols,
    const std::vector<std::uint8_t>* captured_mask, double* amp_min_out,
    double* amp_max_out, bool invert = false);

}  // namespace pa
