"""Build native C++ backend: python setup.py build_ext --inplace"""

from pathlib import Path

import pybind11
from pybind11.setup_helpers import Pybind11Extension, build_ext
from setuptools import setup

ROOT = Path(__file__).parent
NATIVE = ROOT / "native"

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
        ],
        include_dirs=[
            str(NATIVE / "include"),
            pybind11.get_include(),
        ],
        libraries=["portaudio", "fftw3"],
        cxx_std=17,
        extra_compile_args=["-O2"],
    ),
]

setup(
    name="photoacoustic",
    version="0.2.0",
    description="Photoacoustic Imaging — Python UI + C++ backend",
    ext_modules=ext_modules,
    cmdclass={"build_ext": build_ext},
    zip_safe=False,
)
