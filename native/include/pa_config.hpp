#pragma once

// Konstanta yang WAJIB sama dengan #define firmware Arduino.
// Satu sumber kebenaran untuk native backend.

namespace pa {

constexpr double POINT_DISTANCE_CM = 0.05;
constexpr double ROW_DISTANCE_CM = 0.05;
constexpr int DEFAULT_BAUDRATE = 115200;

constexpr double STEP_PER_CM_X = 1000.0;
constexpr double STEP_PER_CM_Y = 1000.0;
constexpr int JOG_STEP_DELAY_US = 300;
constexpr int SCAN_STEP_DELAY_US = 800;
constexpr int BREAK_TIME_MS = 1000;

constexpr int AUDIO_SAMPLERATE = 96000;

constexpr double TARGET_FREQ_HZ = 17000.0;
constexpr double DEFAULT_FREQ_TOLERANCE_HZ = 100.0;

constexpr double AUTO_TARGET_MIN_HZ = 100.0;
constexpr double AUTO_TARGET_MAX_HZ = 20000.0;

constexpr double NOISE_SIDEBAND_FACTOR = 5.0;

}  // namespace pa
