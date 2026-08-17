"""
Jembatan ke ekstensi C++.

Urutan load:
  1. backend._native_impl  (.pyd / .so) — jika berhasil di-build
  2. backend._native_fallback — Python murni (Windows aman tanpa compile C++)

File ini selalu ada supaya Pylance/import resolver tidak error.
"""

from __future__ import annotations

_USING_FALLBACK = False
_IMPORT_ERROR = None

try:
    from backend._native_impl import *  # noqa: F401,F403
    from backend import _native_impl as _impl
except Exception as e:  # ImportError, DLL load failed, dll.
    _IMPORT_ERROR = e
    _USING_FALLBACK = True
    from backend._native_fallback import *  # noqa: F401,F403
    from backend import _native_fallback as _impl
    print(
        "[INFO] Native C++ tidak tersedia — memakai backend Python fallback.\n"
        f"       Alasan: {e}\n"
        "       (Opsional) Build C++: python setup.py build_ext --inplace"
    )


def __dir__():
    return [n for n in dir(_impl) if not n.startswith("_")]
