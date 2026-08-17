"""Build native C++ backend: python setup.py build_ext --inplace"""

from pathlib import Path
import sys

import pybind11
from pybind11.setup_helpers import Pybind11Extension, build_ext
from setuptools import setup

ROOT = Path(__file__).parent
NATIVE = ROOT / "native"
KISS = NATIVE / "third_party" / "kissfft"

# PortAudio: di Linux cukup "portaudio"; di Windows biasanya perlu path manual.
libraries = ["portaudio"]
library_dirs = []
include_dirs = [
    str(NATIVE / "include"),
    str(KISS),
    pybind11.get_include(),
]
extra_compile_args = ["-O2"]
extra_link_args = []

if sys.platform == "win32":
    # MSVC
    extra_compile_args = ["/O2", "/std:c++17"]

ext_modules = [
    Pybind11Extension(
        "backend._native",
        [
            str(NATIVE / "src" / "bindings.cpp"),
            str(NATIVE / "src" / "scan_timing.cpp"),
            str(NATIVE / "src" / "spatial_mapping.cpp"),
            str(NATIVE / "src" / "fft.cpp"),
            str(NATIVE / "src" / "audio_capture.cpp"),
            str(NATIVE / "src" / "serial_controller.cpp"),
            str(KISS / "kiss_fft.c"),
            str(KISS / "kiss_fftr.c"),
        ],
        include_dirs=include_dirs,
        libraries=libraries,
        library_dirs=library_dirs,
        language="c++",
        cxx_std=17,
        extra_compile_args=extra_compile_args,
        extra_link_args=extra_link_args,
        define_macros=[("kiss_fft_scalar", "double")],
    ),
]

setup(
    name="photoacoustic",
    version="0.2.1",
    description="Photoacoustic Imaging — Python UI + C++ backend",
    ext_modules=ext_modules,
    cmdclass={"build_ext": build_ext},
    zip_safe=False,
)
