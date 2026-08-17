#pragma once

#include <atomic>
#include <functional>
#include <mutex>
#include <string>
#include <thread>
#include <utility>
#include <vector>

#ifdef _WIN32
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include <windows.h>
#endif

namespace pa {

struct PortInfo {
    std::string device;
    std::string label;
};

class SerialController {
public:
    using MessageCallback = std::function<void(const std::string&)>;
    using StatusCallback = std::function<void(bool)>;

    SerialController() = default;
    ~SerialController();

    SerialController(const SerialController&) = delete;
    SerialController& operator=(const SerialController&) = delete;

    void set_on_message(MessageCallback cb);
    void set_on_status_change(StatusCallback cb);

    static std::vector<PortInfo> list_ports();

    std::pair<bool, std::string> connect(const std::string& port, int baudrate = 9600,
                                        double timeout_s = 1.0);
    void disconnect();
    bool is_connected() const;

    std::pair<bool, std::string> send(const std::string& command);
    std::pair<bool, std::string> set_x(double cm);
    std::pair<bool, std::string> set_y(double cm);
    std::pair<bool, std::string> start_scan();
    std::pair<bool, std::string> stop_scan();
    std::pair<bool, std::string> jog_kanan();
    std::pair<bool, std::string> jog_kiri();
    std::pair<bool, std::string> jog_maju();
    std::pair<bool, std::string> jog_mundur();

private:
    void read_loop();

    mutable std::mutex io_mutex_;
#ifdef _WIN32
    HANDLE handle_ = INVALID_HANDLE_VALUE;
#else
    int fd_ = -1;
#endif
    std::atomic<bool> running_{false};
    std::thread read_thread_;

    std::mutex cb_mutex_;
    MessageCallback on_message_;
    StatusCallback on_status_change_;
};

}  // namespace pa
