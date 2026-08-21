cmake_minimum_required(VERSION 3.16)
project(PhotoacousticCpp LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_AUTOMOC ON)
set(CMAKE_AUTORCC ON)
set(CMAKE_AUTOUIC ON)

# Qt6: set -DCMAKE_PREFIX_PATH="C:/Qt/6.x.x/msvc2019_64" on Windows
find_package(Qt6 REQUIRED COMPONENTS Core Gui Widgets PrintSupport SerialPort)

# PortAudio: pkg-config (Linux) or manual find (Windows)
set(PORTAUDIO_FOUND FALSE)
find_package(PkgConfig QUIET)
if (PkgConfig_FOUND)
  pkg_check_modules(PORTAUDIO QUIET portaudio-2.0)
  if (PORTAUDIO_FOUND)
    set(PORTAUDIO_FOUND TRUE)
  endif()
endif()

if (NOT PORTAUDIO_FOUND)
  find_path(PORTAUDIO_INCLUDE_DIR portaudio.h
    HINTS
      "$ENV{PORTAUDIO_DIR}/include"
      "$ENV{PORTAUDIO_ROOT}/include"
      "C:/portaudio/include"
      "C:/Program Files/portaudio/include"
  )
  find_library(PORTAUDIO_LIBRARY
    NAMES portaudio portaudio_x64 portaudio_x86
    HINTS
      "$ENV{PORTAUDIO_DIR}/lib"
      "$ENV{PORTAUDIO_ROOT}/lib"
      "C:/portaudio/lib"
      "C:/Program Files/portaudio/lib"
  )
  if (PORTAUDIO_INCLUDE_DIR AND PORTAUDIO_LIBRARY)
    set(PORTAUDIO_FOUND TRUE)
    set(PORTAUDIO_INCLUDE_DIRS "${PORTAUDIO_INCLUDE_DIR}")
    set(PORTAUDIO_LIBRARIES "${PORTAUDIO_LIBRARY}")
  endif()
endif()

if (NOT PORTAUDIO_FOUND)
  message(FATAL_ERROR
    "PortAudio tidak ditemukan.\n"
    "Linux: sudo apt install portaudio19-dev\n"
    "Windows: install PortAudio, lalu set PORTAUDIO_DIR atau "
    "-DPORTAUDIO_INCLUDE_DIR=... -DPORTAUDIO_LIBRARY=...")
endif()

add_executable(PhotoacousticCpp
  main.cpp
  backend/audio_capture.cpp
  backend/control.cpp
  backend/scan_timing.cpp
  backend/spatial_mapping.cpp
  backend/spatial_scan_recorder.cpp
  backend/deep_learning.cpp
  frontend/fft_widget.cpp
  frontend/spatial_map_widget.cpp
  frontend/deep_learning_widget.cpp
  frontend/ui_control.cpp
  third_party/qcustomplot/qcustomplot.cpp
)

target_include_directories(PhotoacousticCpp PRIVATE
  ${CMAKE_CURRENT_SOURCE_DIR}
  ${PORTAUDIO_INCLUDE_DIRS}
)

target_link_libraries(PhotoacousticCpp PRIVATE
  Qt6::Core
  Qt6::Gui
  Qt6::Widgets
  Qt6::PrintSupport
  Qt6::SerialPort
  ${PORTAUDIO_LIBRARIES}
)

if (PORTAUDIO_CFLAGS_OTHER)
  target_compile_options(PhotoacousticCpp PRIVATE ${PORTAUDIO_CFLAGS_OTHER})
endif()

if (WIN32)
  target_compile_definitions(PhotoacousticCpp PRIVATE NOMINMAX)
endif()

# Bantu IntelliSense VS Code / Cursor (setelah cmake configure)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)
