#include "../include/scan_timing.hpp"

#include <sstream>

namespace pa {
namespace {

// Implementasi sendiri agar tidak bentrok overload std::lround/ceil/floor
// (sering muncul di IntelliSense MSVC / Windows).
inline int round_to_int(double x) {
    return static_cast<int>(x >= 0.0 ? x + 0.5 : x - 0.5);
}

inline double floor_d(double x) {
    const double t = static_cast<double>(static_cast<long long>(x));
    if (t == x) return t;
    return (x >= 0.0) ? t : t - 1.0;
}

inline double ceil_d(double x) {
    const double f = floor_d(x);
    return (x > f) ? f + 1.0 : f;
}

}  // namespace

double scan_speed_cm_s(int scan_step_delay_us, double step_per_cm_x) {
    return 1000000.0 / (2.0 * static_cast<double>(scan_step_delay_us)) / step_per_cm_x;
}

double jog_speed_cm_s(int jog_step_delay_us, double step_per_cm_x) {
    return 1000000.0 / (2.0 * static_cast<double>(jog_step_delay_us)) / step_per_cm_x;
}

int hitung_titik_per_baris(double panjang_cm, double point_distance_cm) {
    if (panjang_cm <= 0.0) return 0;
    return round_to_int(panjang_cm / point_distance_cm) + 1;
}

int hitung_jumlah_baris(double lebar_cm, double row_distance_cm) {
    if (lebar_cm <= 0.0) return 0;
    return round_to_int(lebar_cm / row_distance_cm) + 1;
}

double hitung_estimasi_durasi_s(double x_cm, double y_cm,
                                double point_distance_cm,
                                double row_distance_cm,
                                int scan_step_delay_us,
                                double step_per_cm_x,
                                int break_time_ms) {
    const int titik = hitung_titik_per_baris(x_cm, point_distance_cm);
    const int baris = hitung_jumlah_baris(y_cm, row_distance_cm);
    if (titik <= 0 || baris <= 0) return 0.0;

    const double dwell_s = static_cast<double>(break_time_ms) / 1000.0;
    const double speed = scan_speed_cm_s(scan_step_delay_us, step_per_cm_x);
    const double travel_point_s = point_distance_cm / speed;
    const double travel_row_s = row_distance_cm / speed;

    const double total_diam = static_cast<double>(baris * titik) * dwell_s;
    const double total_gerak =
        static_cast<double>(baris * (titik - 1)) * travel_point_s +
        static_cast<double>(baris - 1) * travel_row_s;
    return total_diam + total_gerak;
}

std::string format_jam_menit(double detik, bool bulatkan_ke_atas) {
    if (detik < 0.0) detik = 0.0;
    double menit_total = detik / 60.0;
    menit_total = bulatkan_ke_atas ? ceil_d(menit_total) : floor_d(menit_total);
    const int total = static_cast<int>(menit_total);
    const int jam = total / 60;
    const int menit = total % 60;
    std::ostringstream oss;
    oss << jam << " jam " << menit << " menit";
    return oss.str();
}

}  // namespace pa
