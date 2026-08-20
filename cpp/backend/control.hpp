#pragma once

#include <atomic>
#include <functional>
#include <mutex>
#include <string>
#include <thread>
#include <utility>
#include <vector>

#include <QObject>
#include <QSerialPort>

namespace pa {

class SerialController : public QObject {
  Q_OBJECT
 public:
  explicit SerialController(QObject* parent = nullptr);
  ~SerialController() override;

  static std::vector<std::pair<QString, QString>> listPorts();

  std::pair<bool, QString> connectTo(const QString& port, int baudrate);
  void disconnectPort();
  bool isConnected() const;

  std::pair<bool, QString> send(const QString& command);
  std::pair<bool, QString> setX(double cm);
  std::pair<bool, QString> setY(double cm);
  std::pair<bool, QString> startScan();
  std::pair<bool, QString> stopScan();
  std::pair<bool, QString> jogKanan();
  std::pair<bool, QString> jogKiri();
  std::pair<bool, QString> jogMaju();
  std::pair<bool, QString> jogMundur();
  std::pair<bool, QString> setLaserFreq(double hz);

 signals:
  void messageReceived(const QString& line);
  void statusChanged(bool connected);

 private:
  QSerialPort* port_ = nullptr;
};

}  // namespace pa
