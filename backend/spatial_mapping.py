"""Ekstraksi amplitudo + grayscale."""

import sys

if sys.platform == "win32":
    from backend._native_fallback import (
        amplitude_matrix_to_grayscale,
        estimasi_noise_floor,
        extract_amplitude_at_frequency,
    )
else:
    from backend._native import (
        amplitude_matrix_to_grayscale,
        estimasi_noise_floor,
        extract_amplitude_at_frequency,
    )

__all__ = [
    "extract_amplitude_at_frequency",
    "estimasi_noise_floor",
    "amplitude_matrix_to_grayscale",
]
