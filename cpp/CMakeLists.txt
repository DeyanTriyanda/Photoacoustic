cmake_minimum_required(VERSION 3.16)
project(PhotoacousticCpp LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_AUTOMOC ON)
set(CMAKE_AUTORCC ON)
set(CMAKE_AUTOUIC ON)

find_package(Qt6 REQUIRED COMPONENTS Core Gui Widgets Charts SerialPort)
find_package(PkgConfig REQUIRED)
pkg_check_modules(PORTAUDIO REQUIRED portaudio-2.0)

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
)

target_include_directories(PhotoacousticCpp PRIVATE
  ${CMAKE_CURRENT_SOURCE_DIR}
  ${PORTAUDIO_INCLUDE_DIRS}
)

target_link_libraries(PhotoacousticCpp PRIVATE
  Qt6::Core
  Qt6::Gui
  Qt6::Widgets
  Qt6::Charts
  Qt6::SerialPort
  ${PORTAUDIO_LIBRARIES}
)

target_compile_options(PhotoacousticCpp PRIVATE ${PORTAUDIO_CFLAGS_OTHER})

if (WIN32)
  target_compile_definitions(PhotoacousticCpp PRIVATE NOMINMAX)
endif()
