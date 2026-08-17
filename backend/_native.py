"""
Jembatan ke ekstensi C++.

Setelah `python setup.py build_ext --inplace`, modul
`backend._native_impl` (.pyd / .so) tersedia dan diimpor di sini.

File ini selalu ada supaya Pylance/import resolver tidak error.
"""

from __future__ import annotations

_BUILD_HINT = (
    "Modul C++ belum di-build (backend._native_impl).\n"
    "Jalankan dari root proyek:\n"
    "  pip install pybind11\n"
    "  python setup.py build_ext --inplace\n"
    "Butuh juga PortAudio untuk audio."
)

try:
    from backend._native_impl import *  # noqa: F401,F403
    from backend import _native_impl as _impl
except ImportError as e:  # pragma: no cover - hanya saat belum di-build
    # Simpan exception di luar blok except (di Python 3, nama 'e' dihapus
    # setelah except selesai — itu yang bikin NameError sebelumnya).
    _IMPORT_ERROR: BaseException | None = e

    def __getattr__(name: str):
        raise ImportError(
            f"{_BUILD_HINT}\n(Saat mengakses: {name})"
        ) from _IMPORT_ERROR

    def __dir__():
        return []

else:
    _IMPORT_ERROR = None

    def __dir__():
        return [n for n in dir(_impl) if not n.startswith("_")]
