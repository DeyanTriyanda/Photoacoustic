"""
Utilitas jadwal/grid raster scan -- dipakai bersama oleh
SpatialScanRecorder dan ui_control.
"""

from backend.config import (
    BREAK_TIME_MS,
    POINT_DISTANCE_CM,
    ROW_DISTANCE_CM,
    SCAN_STEP_DELAY_US,
    STEP_PER_CM_X,
)


def scan_speed_cm_s(scan_step_delay_us=SCAN_STEP_DELAY_US,
                    step_per_cm_x=STEP_PER_CM_X):
    return 1_000_000 / (2 * scan_step_delay_us) / step_per_cm_x


def jog_speed_cm_s(jog_step_delay_us, step_per_cm_x=STEP_PER_CM_X):
    return 1_000_000 / (2 * jog_step_delay_us) / step_per_cm_x


def hitung_titik_per_baris(panjang_cm, point_distance_cm=POINT_DISTANCE_CM):
    if panjang_cm <= 0:
        return 0
    return round(panjang_cm / point_distance_cm) + 1


def hitung_jumlah_baris(lebar_cm, row_distance_cm=ROW_DISTANCE_CM):
    if lebar_cm <= 0:
        return 0
    return round(lebar_cm / row_distance_cm) + 1


def hitung_estimasi_durasi_s(
    x_cm,
    y_cm,
    point_distance_cm=POINT_DISTANCE_CM,
    row_distance_cm=ROW_DISTANCE_CM,
    scan_step_delay_us=SCAN_STEP_DELAY_US,
    step_per_cm_x=STEP_PER_CM_X,
    break_time_ms=BREAK_TIME_MS,
):
    titik = hitung_titik_per_baris(x_cm, point_distance_cm)
    baris = hitung_jumlah_baris(y_cm, row_distance_cm)
    if titik <= 0 or baris <= 0:
        return 0.0

    dwell_s = break_time_ms / 1000.0
    speed = scan_speed_cm_s(scan_step_delay_us, step_per_cm_x)
    travel_point_s = point_distance_cm / speed
    travel_row_s = row_distance_cm / speed

    total_diam = baris * titik * dwell_s
    total_gerak = baris * (titik - 1) * travel_point_s + (baris - 1) * travel_row_s
    return total_diam + total_gerak


def format_jam_menit(detik, bulatkan_ke_atas=False):
    if detik < 0:
        detik = 0
    menit_total = detik / 60.0
    menit_total = -(-menit_total // 1) if bulatkan_ke_atas else menit_total // 1
    jam, menit = divmod(int(menit_total), 60)
    return f"{jam} jam {menit} menit"
