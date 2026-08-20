#pragma once
#include "backend/config.hpp"

#include <cmath>
#include <string>

namespace pa {

inline double scan_speed_cm_s(int scan_step_delay_us = SCAN_STEP_DELAY_US,
                              double step_per_cm_x = STEP_PER_CM_X) {
  return 1'000'000.0 / (2.0 * scan_step_delay_us) / step_per_cm_x;
}

inline double jog_speed_cm_s(int jog_step_delay_us,
                             double step_per_cm_x = STEP_PER_CM_X) {
  return 1'000'000.0 / (2.0 * jog_step_delay_us) / step_per_cm_x;
}

inline int hitung_titik_per_baris(double panjang_cm,
                                  double point_distance_cm = POINT_DISTANCE_CM) {
  if (panjang_cm <= 0) return 0;
  return static_cast<int>(std::llround(panjang_cm / point_distance_cm)) + 1;
}

inline int hitung_jumlah_baris(double lebar_cm,
                               double row_distance_cm = ROW_DISTANCE_CM) {
  if (lebar_cm <= 0) return 0;
  return static_cast<int>(std::llround(lebar_cm / row_distance_cm)) + 1;
}

inline double hitung_estimasi_durasi_s(
    double x_cm, double y_cm,
    double point_distance_cm = POINT_DISTANCE_CM,
    double row_distance_cm = ROW_DISTANCE_CM,
    int scan_step_delay_us = SCAN_STEP_DELAY_US,
    double step_per_cm_x = STEP_PER_CM_X,
    int break_time_ms = BREAK_TIME_MS) {
  const int titik = hitung_titik_per_baris(x_cm, point_distance_cm);
  const int baris = hitung_jumlah_baris(y_cm, row_distance_cm);
  if (titik <= 0 || baris <= 0) return 0.0;

  const double dwell_s = break_time_ms / 1000.0;
  const double speed = scan_speed_cm_s(scan_step_delay_us, step_per_cm_x);
  const double travel_point_s = point_distance_cm / speed;
  const double travel_row_s = row_distance_cm / speed;

  const double total_diam = baris * titik * dwell_s;
  const double total_gerak =
      baris * (titik - 1) * travel_point_s + (baris - 1) * travel_row_s;
  return total_diam + total_gerak;
}

inline std::string format_jam_menit(double detik, bool bulatkan_ke_atas = false) {
  if (detik < 0) detik = 0;
  double menit_total = detik / 60.0;
  if (bulatkan_ke_atas)
    menit_total = std::ceil(menit_total);
  else
    menit_total = std::floor(menit_total);
  const int total = static_cast<int>(menit_total);
  const int jam = total / 60;
  const int menit = total % 60;
  return std::to_string(jam) + " jam " + std::to_string(menit) + " menit";
}

}  // namespace pa
