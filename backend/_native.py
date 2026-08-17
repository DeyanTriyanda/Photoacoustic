"""
Jembatan ke ekstensi C++.

Setelah `python setup.py build_ext --inplace`, modul
`backend._native_impl` (.pyd / .so) tersedia dan diimpor di sini.

File ini selalu ada supaya Pylance/import resolver tidak error.
"""

from __future__ import annotations

try:
    from backend._native_impl import *  # noqa: F401,F403
    from backend import _native_impl as _impl
except ImportError as _exc:  # pragma: no cover - hanya saat belum di-build
    _BUILD_HINT = (
        "Modul C++ belum di-build.\n"
        "Jalankan dari root proyek:\n"
        "  pip install pybind11\n"
        "  python setup.py build_ext --inplace\n"
        "Butuh juga PortAudio (portaudio19-dev / library Windows)."
    )

    def __getattr__(name: str):
        raise ImportError(f"{_BUILD_HINT}\n(Saat mengakses: {name})") from _exc

    def __dir__():
        return []

else:
    # Pastikan dir() mencerminkan isi native
    def __dir__():
        return [n for n in dir(_impl) if not n.startswith("_")]
