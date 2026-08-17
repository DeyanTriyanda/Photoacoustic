"""
Konstanta firmware -- diekspor dari backend C++ native.

Sumber kebenaran: native/include/pa_config.hpp
"""

from backend._native import (
    AUDIO_SAMPLERATE,
    AUTO_TARGET_MAX_HZ,
    AUTO_TARGET_MIN_HZ,
    BREAK_TIME_MS,
    DEFAULT_BAUDRATE,
    DEFAULT_FREQ_TOLERANCE_HZ,
    JOG_STEP_DELAY_US,
    NOISE_SIDEBAND_FACTOR,
    POINT_DISTANCE_CM,
    ROW_DISTANCE_CM,
    SCAN_STEP_DELAY_US,
    STEP_PER_CM_X,
    STEP_PER_CM_Y,
    TARGET_FREQ_HZ,
)

__all__ = [
    "POINT_DISTANCE_CM",
    "ROW_DISTANCE_CM",
    "DEFAULT_BAUDRATE",
    "STEP_PER_CM_X",
    "STEP_PER_CM_Y",
    "JOG_STEP_DELAY_US",
    "SCAN_STEP_DELAY_US",
    "BREAK_TIME_MS",
    "AUDIO_SAMPLERATE",
    "TARGET_FREQ_HZ",
    "DEFAULT_FREQ_TOLERANCE_HZ",
    "AUTO_TARGET_MIN_HZ",
    "AUTO_TARGET_MAX_HZ",
    "NOISE_SIDEBAND_FACTOR",
]
