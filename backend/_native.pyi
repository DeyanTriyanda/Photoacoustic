"""Stub tipe untuk backend._native (jembatan ke _native_impl C++)."""

from __future__ import annotations

from typing import Any, Callable, Optional, Sequence, Tuple

import numpy as np
from numpy.typing import NDArray

POINT_DISTANCE_CM: float
ROW_DISTANCE_CM: float
DEFAULT_BAUDRATE: int
STEP_PER_CM_X: float
STEP_PER_CM_Y: float
JOG_STEP_DELAY_US: int
SCAN_STEP_DELAY_US: int
BREAK_TIME_MS: int
AUDIO_SAMPLERATE: int
TARGET_FREQ_HZ: float
DEFAULT_FREQ_TOLERANCE_HZ: float
AUTO_TARGET_MIN_HZ: float
AUTO_TARGET_MAX_HZ: float
NOISE_SIDEBAND_FACTOR: float

def scan_speed_cm_s(
    scan_step_delay_us: int = ...,
    step_per_cm_x: float = ...,
) -> float: ...

def jog_speed_cm_s(
    jog_step_delay_us: int,
    step_per_cm_x: float = ...,
) -> float: ...

def hitung_titik_per_baris(
    panjang_cm: float,
    point_distance_cm: float = ...,
) -> int: ...

def hitung_jumlah_baris(
    lebar_cm: float,
    row_distance_cm: float = ...,
) -> int: ...

def hitung_estimasi_durasi_s(
    x_cm: float,
    y_cm: float,
    point_distance_cm: float = ...,
    row_distance_cm: float = ...,
    scan_step_delay_us: int = ...,
    step_per_cm_x: float = ...,
    break_time_ms: int = ...,
) -> float: ...

def format_jam_menit(detik: float, bulatkan_ke_atas: bool = ...) -> str: ...

def extract_amplitude_at_frequency(
    freqs: NDArray[np.floating[Any]],
    magnitude: NDArray[np.floating[Any]],
    target_freq_hz: float,
    tolerance_hz: float = ...,
) -> float: ...

def estimasi_noise_floor(
    freqs: NDArray[np.floating[Any]],
    mag: NDArray[np.floating[Any]],
    target_freq_hz: float,
    tolerance_hz: float,
    sideband_factor: float = ...,
) -> float: ...

def amplitude_matrix_to_grayscale(
    matrix: NDArray[np.floating[Any]],
    captured_mask: Optional[NDArray[np.bool_]] = ...,
    amp_min_fixed: Optional[float] = ...,
    amp_max_fixed: Optional[float] = ...,
) -> Tuple[NDArray[np.uint8], float, float]: ...

class AudioCaptureNative:
    def __init__(self) -> None: ...
    @staticmethod
    def list_input_devices(force_rescan: bool = ...) -> Sequence[Tuple[int, str]]: ...
    def start(
        self,
        device_index: int,
        samplerate: int = ...,
        channels: int = ...,
        buffer_seconds: float = ...,
        blocksize: int = ...,
    ) -> Tuple[bool, str]: ...
    def stop(self) -> None: ...
    def is_running(self) -> bool: ...
    @property
    def samplerate(self) -> int: ...
    def get_waveform(self) -> NDArray[np.float32]: ...
    def get_fft(
        self,
        window: str = ...,
        min_freq: float = ...,
        max_freq: Optional[float] = ...,
    ) -> Tuple[NDArray[np.floating[Any]], NDArray[np.floating[Any]]]: ...
    def compute_fft(
        self,
        data: NDArray[np.float32],
        window: str = ...,
        min_freq: float = ...,
        max_freq: Optional[float] = ...,
    ) -> Tuple[NDArray[np.floating[Any]], NDArray[np.floating[Any]]]: ...
    def get_peak(
        self,
        min_freq: float = ...,
        max_freq: Optional[float] = ...,
    ) -> Tuple[float, float]: ...
    def capture_samples(self, n: int, timeout: float = ...) -> NDArray[np.float32]: ...
    def last_error(self) -> str: ...

class SerialControllerNative:
    def __init__(self) -> None: ...
    def set_on_message(self, cb: Optional[Callable[[str], None]]) -> None: ...
    def set_on_status_change(self, cb: Optional[Callable[[bool], None]]) -> None: ...
    @staticmethod
    def list_ports() -> Sequence[Tuple[str, str]]: ...
    def connect(
        self,
        port: str,
        baudrate: int = ...,
        timeout: float = ...,
    ) -> Tuple[bool, str]: ...
    def disconnect(self) -> None: ...
    def is_connected(self) -> bool: ...
    def send(self, command: str) -> Tuple[bool, str]: ...
    def set_x(self, cm: float) -> Tuple[bool, str]: ...
    def set_y(self, cm: float) -> Tuple[bool, str]: ...
    def start_scan(self) -> Tuple[bool, str]: ...
    def stop_scan(self) -> Tuple[bool, str]: ...
    def jog_kanan(self) -> Tuple[bool, str]: ...
    def jog_kiri(self) -> Tuple[bool, str]: ...
    def jog_maju(self) -> Tuple[bool, str]: ...
    def jog_mundur(self) -> Tuple[bool, str]: ...
