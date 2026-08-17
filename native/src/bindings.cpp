#include <algorithm>
#include <cstring>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

#include <pybind11/functional.h>
#include <pybind11/numpy.h>
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include "../include/audio_capture.hpp"
#include "../include/pa_config.hpp"
#include "../include/scan_timing.hpp"
#include "../include/serial_controller.hpp"
#include "../include/spatial_mapping.hpp"

namespace py = pybind11;

namespace {

py::tuple fft_to_numpy(const std::pair<std::vector<double>, std::vector<double>>& fft) {
    const auto& freqs = fft.first;
    const auto& mag = fft.second;
    auto f = py::array_t<double>(freqs.size());
    auto m = py::array_t<double>(mag.size());
    auto* fptr = f.mutable_data();
    auto* mptr = m.mutable_data();
    for (std::size_t i = 0; i < freqs.size(); ++i) fptr[i] = freqs[i];
    for (std::size_t i = 0; i < mag.size(); ++i) mptr[i] = mag[i];
    return py::make_tuple(f, m);
}

}  // namespace

PYBIND11_MODULE(_native_impl, m) {
    m.doc() = "Photoacoustic native C++ backend (pybind11)";

    m.attr("POINT_DISTANCE_CM") = pa::POINT_DISTANCE_CM;
    m.attr("ROW_DISTANCE_CM") = pa::ROW_DISTANCE_CM;
    m.attr("DEFAULT_BAUDRATE") = pa::DEFAULT_BAUDRATE;
    m.attr("STEP_PER_CM_X") = pa::STEP_PER_CM_X;
    m.attr("STEP_PER_CM_Y") = pa::STEP_PER_CM_Y;
    m.attr("JOG_STEP_DELAY_US") = pa::JOG_STEP_DELAY_US;
    m.attr("SCAN_STEP_DELAY_US") = pa::SCAN_STEP_DELAY_US;
    m.attr("BREAK_TIME_MS") = pa::BREAK_TIME_MS;
    m.attr("AUDIO_SAMPLERATE") = pa::AUDIO_SAMPLERATE;
    m.attr("TARGET_FREQ_HZ") = pa::TARGET_FREQ_HZ;
    m.attr("DEFAULT_FREQ_TOLERANCE_HZ") = pa::DEFAULT_FREQ_TOLERANCE_HZ;
    m.attr("AUTO_TARGET_MIN_HZ") = pa::AUTO_TARGET_MIN_HZ;
    m.attr("AUTO_TARGET_MAX_HZ") = pa::AUTO_TARGET_MAX_HZ;
    m.attr("NOISE_SIDEBAND_FACTOR") = pa::NOISE_SIDEBAND_FACTOR;

    m.def("scan_speed_cm_s", &pa::scan_speed_cm_s,
          py::arg("scan_step_delay_us") = pa::SCAN_STEP_DELAY_US,
          py::arg("step_per_cm_x") = pa::STEP_PER_CM_X);
    m.def("jog_speed_cm_s", &pa::jog_speed_cm_s, py::arg("jog_step_delay_us"),
          py::arg("step_per_cm_x") = pa::STEP_PER_CM_X);
    m.def("hitung_titik_per_baris", &pa::hitung_titik_per_baris, py::arg("panjang_cm"),
          py::arg("point_distance_cm") = pa::POINT_DISTANCE_CM);
    m.def("hitung_jumlah_baris", &pa::hitung_jumlah_baris, py::arg("lebar_cm"),
          py::arg("row_distance_cm") = pa::ROW_DISTANCE_CM);
    m.def("hitung_estimasi_durasi_s", &pa::hitung_estimasi_durasi_s, py::arg("x_cm"),
          py::arg("y_cm"), py::arg("point_distance_cm") = pa::POINT_DISTANCE_CM,
          py::arg("row_distance_cm") = pa::ROW_DISTANCE_CM,
          py::arg("scan_step_delay_us") = pa::SCAN_STEP_DELAY_US,
          py::arg("step_per_cm_x") = pa::STEP_PER_CM_X,
          py::arg("break_time_ms") = pa::BREAK_TIME_MS);
    m.def("format_jam_menit", &pa::format_jam_menit, py::arg("detik"),
          py::arg("bulatkan_ke_atas") = false);

    m.def(
        "extract_amplitude_at_frequency",
        [](py::array_t<double, py::array::c_style | py::array::forcecast> freqs,
           py::array_t<double, py::array::c_style | py::array::forcecast> magnitude,
           double target_freq_hz, double tolerance_hz) {
            auto f = freqs.unchecked<1>();
            auto mag = magnitude.unchecked<1>();
            const auto n = static_cast<std::size_t>(std::min(f.shape(0), mag.shape(0)));
            std::vector<double> fv(n), mv(n);
            for (std::size_t i = 0; i < n; ++i) {
                fv[i] = f(i);
                mv[i] = mag(i);
            }
            return pa::extract_amplitude_at_frequency(fv.data(), mv.data(), n,
                                                      target_freq_hz, tolerance_hz);
        },
        py::arg("freqs"), py::arg("magnitude"), py::arg("target_freq_hz"),
        py::arg("tolerance_hz") = 50.0);

    m.def(
        "estimasi_noise_floor",
        [](py::array_t<double, py::array::c_style | py::array::forcecast> freqs,
           py::array_t<double, py::array::c_style | py::array::forcecast> mag,
           double target_freq_hz, double tolerance_hz, double sideband_factor) {
            auto f = freqs.unchecked<1>();
            auto marr = mag.unchecked<1>();
            const auto n = static_cast<std::size_t>(std::min(f.shape(0), marr.shape(0)));
            std::vector<double> fv(n), mv(n);
            for (std::size_t i = 0; i < n; ++i) {
                fv[i] = f(i);
                mv[i] = marr(i);
            }
            return pa::estimasi_noise_floor(fv.data(), mv.data(), n, target_freq_hz,
                                            tolerance_hz, sideband_factor);
        },
        py::arg("freqs"), py::arg("mag"), py::arg("target_freq_hz"),
        py::arg("tolerance_hz"), py::arg("sideband_factor") = 5.0);

    m.def(
        "amplitude_matrix_to_grayscale",
        [](py::array_t<double, py::array::c_style | py::array::forcecast> matrix,
           py::object captured_mask, py::object amp_min_fixed,
           py::object amp_max_fixed) {
            if (matrix.ndim() != 2) {
                throw std::runtime_error("matrix harus 2D");
            }
            const int rows = static_cast<int>(matrix.shape(0));
            const int cols = static_cast<int>(matrix.shape(1));
            auto mat = matrix.unchecked<2>();
            std::vector<double> flat(static_cast<std::size_t>(rows * cols));
            for (int r = 0; r < rows; ++r) {
                for (int c = 0; c < cols; ++c) {
                    flat[static_cast<std::size_t>(r * cols + c)] = mat(r, c);
                }
            }

            std::vector<unsigned char> mask;
            const unsigned char* mask_ptr = nullptr;
            if (!captured_mask.is_none()) {
                auto mask_arr =
                    py::array_t<bool, py::array::c_style | py::array::forcecast>::ensure(
                        captured_mask);
                if (!mask_arr || mask_arr.ndim() != 2) {
                    throw std::runtime_error("captured_mask harus 2D bool");
                }
                auto ma = mask_arr.unchecked<2>();
                mask.resize(static_cast<std::size_t>(rows * cols));
                for (int r = 0; r < rows; ++r) {
                    for (int c = 0; c < cols; ++c) {
                        mask[static_cast<std::size_t>(r * cols + c)] =
                            ma(r, c) ? 1 : 0;
                    }
                }
                mask_ptr = mask.data();
            }

            bool has_fixed = !amp_min_fixed.is_none() && !amp_max_fixed.is_none();
            double amin_f = has_fixed ? amp_min_fixed.cast<double>() : 0.0;
            double amax_f = has_fixed ? amp_max_fixed.cast<double>() : 0.0;

            auto result = pa::amplitude_matrix_to_grayscale(
                flat.data(), rows, cols, mask_ptr, has_fixed, amin_f, amax_f);

            auto gray = py::array_t<uint8_t>({rows, cols});
            auto g = gray.mutable_unchecked<2>();
            for (int r = 0; r < rows; ++r) {
                for (int c = 0; c < cols; ++c) {
                    g(r, c) = result.gray[static_cast<std::size_t>(r * cols + c)];
                }
            }
            return py::make_tuple(gray, result.amp_min, result.amp_max);
        },
        py::arg("matrix"), py::arg("captured_mask") = py::none(),
        py::arg("amp_min_fixed") = py::none(), py::arg("amp_max_fixed") = py::none());

    py::class_<pa::AudioCapture>(m, "AudioCaptureNative")
        .def(py::init<>())
        .def_static(
            "list_input_devices",
            [](bool force_rescan) {
                py::list out;
                for (const auto& d : pa::AudioCapture::list_input_devices(force_rescan)) {
                    out.append(py::make_tuple(d.index, d.label));
                }
                return out;
            },
            py::arg("force_rescan") = true)
        .def(
            "start",
            [](pa::AudioCapture& self, int device_index, int samplerate, int channels,
               double buffer_seconds, int blocksize) {
                py::gil_scoped_release release;
                auto [ok, msg] =
                    self.start(device_index, samplerate, channels, buffer_seconds, blocksize);
                return py::make_tuple(ok, msg);
            },
            py::arg("device_index"), py::arg("samplerate") = 96000,
            py::arg("channels") = 1, py::arg("buffer_seconds") = 1.0,
            py::arg("blocksize") = 1024)
        .def("stop", &pa::AudioCapture::stop, py::call_guard<py::gil_scoped_release>())
        .def("is_running", &pa::AudioCapture::is_running)
        .def_property_readonly("samplerate", &pa::AudioCapture::samplerate)
        .def(
            "get_waveform",
            [](const pa::AudioCapture& self) {
                std::vector<float> wave;
                {
                    py::gil_scoped_release release;
                    wave = self.get_waveform();
                }
                auto arr = py::array_t<float>(wave.size());
                if (!wave.empty()) {
                    std::memcpy(arr.mutable_data(), wave.data(),
                                wave.size() * sizeof(float));
                }
                return arr;
            })
        .def(
            "get_fft",
            [](const pa::AudioCapture& self, const std::string& window, double min_freq,
               py::object max_freq) {
                const bool hann = (window == "hann");
                double mf = max_freq.is_none() ? -1.0 : max_freq.cast<double>();
                std::pair<std::vector<double>, std::vector<double>> fft;
                {
                    py::gil_scoped_release release;
                    fft = self.get_fft(hann, min_freq, mf);
                }
                return fft_to_numpy(fft);
            },
            py::arg("window") = "hann", py::arg("min_freq") = 0.0,
            py::arg("max_freq") = py::none())
        .def(
            "compute_fft",
            [](const pa::AudioCapture& self, py::array_t<float> data,
               const std::string& window, double min_freq, py::object max_freq) {
                auto buf = data.request();
                std::vector<float> v(static_cast<std::size_t>(buf.size));
                std::memcpy(v.data(), buf.ptr, v.size() * sizeof(float));
                const bool hann = (window == "hann");
                double mf = max_freq.is_none() ? -1.0 : max_freq.cast<double>();
                std::pair<std::vector<double>, std::vector<double>> fft;
                {
                    py::gil_scoped_release release;
                    fft = self.compute_fft(v, hann, min_freq, mf);
                }
                return fft_to_numpy(fft);
            },
            py::arg("data"), py::arg("window") = "hann", py::arg("min_freq") = 0.0,
            py::arg("max_freq") = py::none())
        .def(
            "get_peak",
            [](const pa::AudioCapture& self, double min_freq, py::object max_freq) {
                double mf = max_freq.is_none() ? -1.0 : max_freq.cast<double>();
                py::gil_scoped_release release;
                auto [f, a] = self.get_peak(min_freq, mf);
                return py::make_tuple(f, a);
            },
            py::arg("min_freq") = 20.0, py::arg("max_freq") = py::none())
        .def(
            "capture_samples",
            [](pa::AudioCapture& self, int n, double timeout) {
                std::vector<float> data;
                {
                    py::gil_scoped_release release;
                    data = self.capture_samples(n, timeout);
                }
                auto arr = py::array_t<float>(data.size());
                if (!data.empty()) {
                    std::memcpy(arr.mutable_data(), data.data(),
                                data.size() * sizeof(float));
                }
                return arr;
            },
            py::arg("n"), py::arg("timeout") = 2.0)
        .def("last_error", &pa::AudioCapture::last_error);

    py::class_<pa::SerialController>(m, "SerialControllerNative")
        .def(py::init<>())
        .def("set_on_message",
             [](pa::SerialController& self, py::object cb) {
                 if (cb.is_none()) {
                     self.set_on_message(nullptr);
                     return;
                 }
                 self.set_on_message([cb](const std::string& line) {
                     py::gil_scoped_acquire acquire;
                     cb(line);
                 });
             })
        .def("set_on_status_change",
             [](pa::SerialController& self, py::object cb) {
                 if (cb.is_none()) {
                     self.set_on_status_change(nullptr);
                     return;
                 }
                 self.set_on_status_change([cb](bool connected) {
                     py::gil_scoped_acquire acquire;
                     cb(connected);
                 });
             })
        .def_static(
            "list_ports",
            []() {
                py::list out;
                for (const auto& p : pa::SerialController::list_ports()) {
                    out.append(py::make_tuple(p.device, p.label));
                }
                return out;
            })
        .def(
            "connect",
            [](pa::SerialController& self, const std::string& port, int baudrate,
               double timeout) {
                py::gil_scoped_release release;
                auto [ok, msg] = self.connect(port, baudrate, timeout);
                return py::make_tuple(ok, msg);
            },
            py::arg("port"), py::arg("baudrate") = 9600, py::arg("timeout") = 1.0)
        .def("disconnect", &pa::SerialController::disconnect,
             py::call_guard<py::gil_scoped_release>())
        .def("is_connected", &pa::SerialController::is_connected)
        .def("send", &pa::SerialController::send, py::arg("command"))
        .def("set_x", &pa::SerialController::set_x, py::arg("cm"))
        .def("set_y", &pa::SerialController::set_y, py::arg("cm"))
        .def("start_scan", &pa::SerialController::start_scan)
        .def("stop_scan", &pa::SerialController::stop_scan)
        .def("jog_kanan", &pa::SerialController::jog_kanan)
        .def("jog_kiri", &pa::SerialController::jog_kiri)
        .def("jog_maju", &pa::SerialController::jog_maju)
        .def("jog_mundur", &pa::SerialController::jog_mundur);
}
