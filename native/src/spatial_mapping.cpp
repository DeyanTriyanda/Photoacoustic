#include "spatial_mapping.hpp"

#include <algorithm>
#include <cmath>
#include <limits>
#include <vector>

namespace pa {

double extract_amplitude_at_frequency(const double* freqs, const double* magnitude,
                                      std::size_t n, double target_freq_hz,
                                      double tolerance_hz) {
    if (n == 0 || freqs == nullptr || magnitude == nullptr) return 0.0;
    double best = -std::numeric_limits<double>::infinity();
    bool any = false;
    for (std::size_t i = 0; i < n; ++i) {
        if (std::abs(freqs[i] - target_freq_hz) <= tolerance_hz) {
            any = true;
            best = std::max(best, magnitude[i]);
        }
    }
    return any ? best : 0.0;
}

double estimasi_noise_floor(const double* freqs, const double* mag, std::size_t n,
                            double target_freq_hz, double tolerance_hz,
                            double sideband_factor) {
    if (n == 0 || freqs == nullptr || mag == nullptr) return 0.0;
    std::vector<double> side;
    side.reserve(n);
    for (std::size_t i = 0; i < n; ++i) {
        const double jarak = std::abs(freqs[i] - target_freq_hz);
        if (jarak > tolerance_hz && jarak <= sideband_factor * tolerance_hz) {
            side.push_back(mag[i]);
        }
    }
    if (side.empty()) return 0.0;
    std::nth_element(side.begin(), side.begin() + side.size() / 2, side.end());
    return side[side.size() / 2];
}

GrayScaleResult amplitude_matrix_to_grayscale(
    const double* matrix, int rows, int cols,
    const unsigned char* captured_mask,
    bool has_fixed_range, double amp_min_fixed, double amp_max_fixed) {
    GrayScaleResult out;
    out.rows = rows;
    out.cols = cols;
    const std::size_t n = static_cast<std::size_t>(rows) * static_cast<std::size_t>(cols);
    out.gray.assign(n, 0);

    if (rows <= 0 || cols <= 0 || matrix == nullptr) {
        return out;
    }

    double amp_min = 0.0;
    double amp_max = 0.0;

    if (has_fixed_range) {
        amp_min = amp_min_fixed;
        amp_max = amp_max_fixed;
    } else {
        bool any = false;
        amp_min = std::numeric_limits<double>::infinity();
        amp_max = -std::numeric_limits<double>::infinity();
        for (std::size_t i = 0; i < n; ++i) {
            if (captured_mask != nullptr && captured_mask[i] == 0) continue;
            any = true;
            amp_min = std::min(amp_min, matrix[i]);
            amp_max = std::max(amp_max, matrix[i]);
        }
        if (!any) {
            out.amp_min = 0.0;
            out.amp_max = 0.0;
            return out;
        }
    }

    out.amp_min = amp_min;
    out.amp_max = amp_max;

    if (amp_max <= amp_min) {
        std::fill(out.gray.begin(), out.gray.end(), static_cast<unsigned char>(128));
        return out;
    }

    for (std::size_t i = 0; i < n; ++i) {
        double normalized = (matrix[i] - amp_min) / (amp_max - amp_min);
        if (normalized < 0.0) normalized = 0.0;
        if (normalized > 1.0) normalized = 1.0;
        const int v = static_cast<int>(normalized * 255.0 + 0.5);
        out.gray[i] = static_cast<unsigned char>(std::clamp(v, 0, 255));
    }
    return out;
}

}  // namespace pa
