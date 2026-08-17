#pragma once

#include <string>

#include "pa_config.hpp"

namespace pa {

double scan_speed_cm_s(int scan_step_delay_us = SCAN_STEP_DELAY_US,
                       double step_per_cm_x = STEP_PER_CM_X);

double jog_speed_cm_s(int jog_step_delay_us,
                      double step_per_cm_x = STEP_PER_CM_X);

int hitung_titik_per_baris(double panjang_cm,
                           double point_distance_cm = POINT_DISTANCE_CM);

int hitung_jumlah_baris(double lebar_cm,
                        double row_distance_cm = ROW_DISTANCE_CM);

double hitung_estimasi_durasi_s(
    double x_cm, double y_cm,
    double point_distance_cm = POINT_DISTANCE_CM,
    double row_distance_cm = ROW_DISTANCE_CM,
    int scan_step_delay_us = SCAN_STEP_DELAY_US,
    double step_per_cm_x = STEP_PER_CM_X,
    int break_time_ms = BREAK_TIME_MS);

std::string format_jam_menit(double detik, bool bulatkan_ke_atas = false);

}  // namespace pa
