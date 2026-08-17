"""
Jembatan ke backend native.

Windows: default pakai Python fallback (aman).
C++ (_native_impl) hanya dicoba jika:
  - bukan Windows, atau
  - env PA_FORCE_NATIVE=1
"""

from __future__ import annotations

import os
import sys

_USING_FALLBACK = False
_IMPORT_ERROR = None
_impl = None

_force_native = os.environ.get("PA_FORCE_NATIVE", "").strip() in ("1", "true", "True")
_try_native = _force_native or sys.platform != "win32"

if _try_native:
    try:
        from backend import _native_impl as _impl
        _USING_FALLBACK = False
    except Exception as e:
        _IMPORT_ERROR = e
        from backend import _native_fallback as _impl
        _USING_FALLBACK = True
        print(
            "[INFO] Memakai backend Python fallback.\n"
            f"       Alasan: {e}\n"
            "       Hapus backend\\_native_impl*.pyd jika file itu rusak.\n"
            "       (Opsional C++) PA_FORCE_NATIVE=1 lalu build_ext --inplace"
        )
else:
    from backend import _native_fallback as _impl
    _USING_FALLBACK = True
    print(
        "[INFO] Windows: memakai backend Python fallback.\n"
        "       Hapus backend\\_native_impl*.pyd / *.so jika ada file rusak.\n"
        "       (Opsional C++) set PA_FORCE_NATIVE=1 lalu: python setup.py build_ext --inplace"
    )

# Ekspor semua simbol publik dari implementasi terpilih
for _name in dir(_impl):
    if not _name.startswith("_"):
        globals()[_name] = getattr(_impl, _name)
del _name


def __dir__():
    return [n for n in dir(_impl) if not n.startswith("_")]
