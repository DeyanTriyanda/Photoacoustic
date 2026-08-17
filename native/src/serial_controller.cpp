#include "serial_controller.hpp"

#include <chrono>
#include <cstring>
#include <filesystem>
#include <sstream>
#include <thread>

#include <errno.h>
#include <fcntl.h>
#include <termios.h>
#include <unistd.h>

namespace pa {
namespace {

speed_t baud_to_flag(int baudrate) {
    switch (baudrate) {
        case 9600: return B9600;
        case 19200: return B19200;
        case 38400: return B38400;
        case 57600: return B57600;
        case 115200: return B115200;
        case 230400: return B230400;
        default: return B115200;
    }
}

}  // namespace

SerialController::~SerialController() { disconnect(); }

void SerialController::set_on_message(MessageCallback cb) {
    std::lock_guard<std::mutex> lock(cb_mutex_);
    on_message_ = std::move(cb);
}

void SerialController::set_on_status_change(StatusCallback cb) {
    std::lock_guard<std::mutex> lock(cb_mutex_);
    on_status_change_ = std::move(cb);
}

std::vector<PortInfo> SerialController::list_ports() {
    std::vector<PortInfo> hasil;
    namespace fs = std::filesystem;
    const fs::path dev{"/dev"};
    if (!fs::exists(dev)) return hasil;
    for (const auto& entry : fs::directory_iterator(dev)) {
        const auto name = entry.path().filename().string();
        if (!(name.rfind("ttyUSB", 0) == 0 || name.rfind("ttyACM", 0) == 0 ||
              name.rfind("ttyAMA", 0) == 0)) {
            continue;
        }
        const std::string device = entry.path().string();
        hasil.push_back(PortInfo{device, device});
    }
    return hasil;
}

std::pair<bool, std::string> SerialController::connect(const std::string& port,
                                                       int baudrate,
                                                       double /*timeout_s*/) {
    disconnect();

    const int fd = ::open(port.c_str(), O_RDWR | O_NOCTTY | O_NONBLOCK);
    if (fd < 0) {
        return {false, std::string("Gagal membuka port: ") + std::strerror(errno)};
    }

    termios tty{};
    if (tcgetattr(fd, &tty) != 0) {
        ::close(fd);
        return {false, std::string("tcgetattr gagal: ") + std::strerror(errno)};
    }

    cfmakeraw(&tty);
    cfsetispeed(&tty, baud_to_flag(baudrate));
    cfsetospeed(&tty, baud_to_flag(baudrate));
    tty.c_cflag |= (CLOCAL | CREAD);
    tty.c_cflag &= ~CSIZE;
    tty.c_cflag |= CS8;
    tty.c_cflag &= ~PARENB;
    tty.c_cflag &= ~CSTOPB;
    tty.c_cflag &= ~CRTSCTS;
    tty.c_cc[VMIN] = 0;
    tty.c_cc[VTIME] = 1;  // 0.1s

    if (tcsetattr(fd, TCSANOW, &tty) != 0) {
        ::close(fd);
        return {false, std::string("tcsetattr gagal: ") + std::strerror(errno)};
    }

    // Mode blocking baca setelah setup.
    int flags = fcntl(fd, F_GETFL, 0);
    fcntl(fd, F_SETFL, flags & ~O_NONBLOCK);

    {
        std::lock_guard<std::mutex> lock(io_mutex_);
        fd_ = fd;
    }

    // Arduino reset setelah port dibuka.
    std::this_thread::sleep_for(std::chrono::seconds(2));

    running_ = true;
    read_thread_ = std::thread(&SerialController::read_loop, this);

    StatusCallback status_cb;
    {
        std::lock_guard<std::mutex> lock(cb_mutex_);
        status_cb = on_status_change_;
    }
    if (status_cb) status_cb(true);

    std::ostringstream oss;
    oss << "Terhubung ke " << port << " @ " << baudrate << " baud";
    return {true, oss.str()};
}

void SerialController::disconnect() {
    running_ = false;
    if (read_thread_.joinable()) {
        read_thread_.join();
    }
    {
        std::lock_guard<std::mutex> lock(io_mutex_);
        if (fd_ >= 0) {
            ::close(fd_);
            fd_ = -1;
        }
    }
    StatusCallback status_cb;
    {
        std::lock_guard<std::mutex> lock(cb_mutex_);
        status_cb = on_status_change_;
    }
    if (status_cb) status_cb(false);
}

bool SerialController::is_connected() const {
    std::lock_guard<std::mutex> lock(io_mutex_);
    return fd_ >= 0;
}

std::pair<bool, std::string> SerialController::send(const std::string& command) {
    std::lock_guard<std::mutex> lock(io_mutex_);
    if (fd_ < 0) return {false, "Belum terhubung ke Arduino"};
    std::string payload = command;
    while (!payload.empty() &&
           (payload.back() == '\n' || payload.back() == '\r' || payload.back() == ' ')) {
        payload.pop_back();
    }
    payload.push_back('\n');
    const ssize_t n = ::write(fd_, payload.data(), payload.size());
    if (n < 0) {
        return {false, std::string("Gagal kirim: ") + std::strerror(errno)};
    }
    return {true, "Terkirim: " + command};
}

std::pair<bool, std::string> SerialController::set_x(double cm) {
    return send("x=" + std::to_string(cm));
}
std::pair<bool, std::string> SerialController::set_y(double cm) {
    return send("y=" + std::to_string(cm));
}
std::pair<bool, std::string> SerialController::start_scan() { return send("start"); }
std::pair<bool, std::string> SerialController::stop_scan() { return send("stop"); }
std::pair<bool, std::string> SerialController::jog_kanan() { return send("kanan"); }
std::pair<bool, std::string> SerialController::jog_kiri() { return send("kiri"); }
std::pair<bool, std::string> SerialController::jog_maju() { return send("maju"); }
std::pair<bool, std::string> SerialController::jog_mundur() { return send("mundur"); }

void SerialController::read_loop() {
    std::string pending;
    char buf[256];
    while (running_.load()) {
        int fd = -1;
        {
            std::lock_guard<std::mutex> lock(io_mutex_);
            fd = fd_;
        }
        if (fd < 0) break;

        const ssize_t n = ::read(fd, buf, sizeof(buf));
        if (n < 0) {
            if (errno == EAGAIN || errno == EWOULDBLOCK) {
                std::this_thread::sleep_for(std::chrono::milliseconds(10));
                continue;
            }
            MessageCallback msg_cb;
            {
                std::lock_guard<std::mutex> lock(cb_mutex_);
                msg_cb = on_message_;
            }
            if (msg_cb) {
                msg_cb(std::string("[ERROR BACA SERIAL] ") + std::strerror(errno));
            }
            break;
        }
        if (n == 0) {
            std::this_thread::sleep_for(std::chrono::milliseconds(10));
            continue;
        }
        pending.append(buf, static_cast<std::size_t>(n));
        std::size_t pos;
        while ((pos = pending.find('\n')) != std::string::npos) {
            std::string line = pending.substr(0, pos);
            pending.erase(0, pos + 1);
            while (!line.empty() && (line.back() == '\r' || line.back() == ' ')) {
                line.pop_back();
            }
            if (line.empty()) continue;
            MessageCallback msg_cb;
            {
                std::lock_guard<std::mutex> lock(cb_mutex_);
                msg_cb = on_message_;
            }
            if (msg_cb) msg_cb(line);
        }
    }
}

}  // namespace pa
