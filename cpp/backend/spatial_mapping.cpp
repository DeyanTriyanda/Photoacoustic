#include "backend/spatial_mapping.hpp"

#include <algorithm>
#include <cmath>
#include <limits>
#include <numeric>

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
  if (freqs.empty() || freqs.size() != magnitude.size()) return 0.0;
  std::vector<double> mag = magnitude;
  for (size_t i = 0; i < freqs.size(); ++i) {
    if (freqs[i] < target_freq_hz) mag[i] = 0.0;
  }
  return extract_amplitude_at_frequency(freqs, mag, target_freq_hz, tolerance_hz);
}

double estimasi_noise_floor(const std::vector<double>& freqs,
                            const std::vector<double>& mag,
                            double target_freq_hz, double tolerance_hz,
                            double sideband_factor) {
  std::vector<double> vals;
  for (size_t i = 0; i < freqs.size(); ++i) {
    const double d = std::abs(freqs[i] - target_freq_hz);
    if (d > tolerance_hz && d <= sideband_factor * tolerance_hz &&
        freqs[i] >= target_freq_hz) {
      vals.push_back(mag[i]);
    }
  }
  if (vals.empty()) return 0.0;
  std::nth_element(vals.begin(), vals.begin() + vals.size() / 2, vals.end());
  return vals[vals.size() / 2];
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

  for (size_t i = 0; i < n; ++i) {
    double norm = (matrix[i] - amin) / (amax - amin);
    norm = std::clamp(norm, 0.0, 1.0);
    if (invert) norm = 1.0 - norm;
    gray[i] = static_cast<std::uint8_t>(std::lround(norm * 255.0));
  }
  return gray;
}

}  // namespace pa
