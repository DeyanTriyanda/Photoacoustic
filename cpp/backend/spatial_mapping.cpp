#include "backend/spatial_mapping.hpp"

#include <algorithm>
#include <cmath>
#include <limits>

namespace pa {

double extract_amplitude_at_frequency(const std::vector<double>& freqs,
                                      const std::vector<double>& magnitude,
                                      double target_freq_hz,
                                      double tolerance_hz) {
  if (freqs.empty() || freqs.size() != magnitude.size()) return 0.0;
  double best = 0.0;
  bool any = false;
  for (size_t i = 0; i < freqs.size(); ++i) {
    if (std::abs(freqs[i] - target_freq_hz) <= tolerance_hz) {
      if (!any || magnitude[i] > best) {
        best = magnitude[i];
        any = true;
      }
    }
  }
  return any ? best : 0.0;
}

double extract_amplitude_object_black_background(
    const std::vector<double>& freqs, const std::vector<double>& magnitude,
    double target_freq_hz, double tolerance_hz) {
  // Tanpa clone vector: abaikan bin < target (background hitam)
  if (freqs.empty() || freqs.size() != magnitude.size()) return 0.0;
  double best = 0.0;
  bool any = false;
  for (size_t i = 0; i < freqs.size(); ++i) {
    if (freqs[i] < target_freq_hz) continue;
    if (std::abs(freqs[i] - target_freq_hz) <= tolerance_hz) {
      if (!any || magnitude[i] > best) {
        best = magnitude[i];
        any = true;
      }
    }
  }
  return any ? best : 0.0;
}

double estimasi_noise_floor(const std::vector<double>& freqs,
                            const std::vector<double>& mag,
                            double target_freq_hz, double tolerance_hz,
                            double sideband_factor) {
  // Median tanpa vector dinamis besar: kumpulkan ke buffer stack kecil / partial
  constexpr int kMax = 512;
  double buf[kMax];
  int n = 0;
  for (size_t i = 0; i < freqs.size(); ++i) {
    const double d = std::abs(freqs[i] - target_freq_hz);
    if (d > tolerance_hz && d <= sideband_factor * tolerance_hz &&
        freqs[i] >= target_freq_hz) {
      if (n < kMax) buf[n++] = mag[i];
    }
  }
  if (n == 0) return 0.0;
  std::nth_element(buf, buf + n / 2, buf + n);
  return buf[n / 2];
}

std::vector<std::uint8_t> amplitude_matrix_to_grayscale(
    const std::vector<double>& matrix, int rows, int cols,
    const std::vector<std::uint8_t>* captured_mask, double* amp_min_out,
    double* amp_max_out, bool invert) {
  const size_t n = static_cast<size_t>(rows) * static_cast<size_t>(cols);
  std::vector<std::uint8_t> gray(n, 0);
  if (matrix.size() < n) {
    if (amp_min_out) *amp_min_out = 0;
    if (amp_max_out) *amp_max_out = 0;
    return gray;
  }

  double amin = std::numeric_limits<double>::infinity();
  double amax = -std::numeric_limits<double>::infinity();
  bool any = false;
  for (size_t i = 0; i < n; ++i) {
    if (captured_mask && i < captured_mask->size() && !(*captured_mask)[i])
      continue;
    amin = std::min(amin, matrix[i]);
    amax = std::max(amax, matrix[i]);
    any = true;
  }
  if (!any) {
    if (amp_min_out) *amp_min_out = 0;
    if (amp_max_out) *amp_max_out = 0;
    return gray;
  }
  if (amp_min_out) *amp_min_out = amin;
  if (amp_max_out) *amp_max_out = amax;

  if (amax <= amin) {
    const std::uint8_t v = (amax <= 0.0) ? 0 : 128;
    std::fill(gray.begin(), gray.end(), v);
    return gray;
  }

  const double inv = 1.0 / (amax - amin);
  for (size_t i = 0; i < n; ++i) {
    if (captured_mask && i < captured_mask->size() && !(*captured_mask)[i]) {
      gray[i] = 0;
      continue;
    }
    double norm = (matrix[i] - amin) * inv;
    if (norm < 0.0) norm = 0.0;
    else if (norm > 1.0) norm = 1.0;
    if (invert) norm = 1.0 - norm;
    gray[i] = static_cast<std::uint8_t>(std::lround(norm * 255.0));
  }
  return gray;
}

}  // namespace pa
