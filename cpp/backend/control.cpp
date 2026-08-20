#include "backend/control.hpp"

#include <cmath>

#include <QSerialPortInfo>
#include <QThread>

#include "backend/config.hpp"

namespace pa {

SerialController::SerialController(QObject* parent) : QObject(parent) {}

SerialController::~SerialController() { disconnectPort(); }

std::vector<std::pair<QString, QString>> SerialController::listPorts() {
  std::vector<std::pair<QString, QString>> out;
  for (const QSerialPortInfo& info : QSerialPortInfo::availablePorts()) {
    const QString device = info.portName();
    QString label = device;
    if (!info.description().isEmpty())
      label = device + " - " + info.description();
    out.emplace_back(device, label);
  }
  return out;
}

std::pair<bool, QString> SerialController::connectTo(const QString& port,
                                                     int baudrate) {
  disconnectPort();
  port_ = new QSerialPort(this);
  port_->setPortName(port);
  port_->setBaudRate(baudrate);
  port_->setDataBits(QSerialPort::Data8);
  port_->setParity(QSerialPort::NoParity);
  port_->setStopBits(QSerialPort::OneStop);
  port_->setFlowControl(QSerialPort::NoFlowControl);
  if (!port_->open(QIODevice::ReadWrite)) {
    const QString err = port_->errorString();
    delete port_;
    port_ = nullptr;
    return {false, err};
  }
  // Arduino reset delay (mirip Python time.sleep(2))
  QThread::msleep(2000);
  connect(port_, &QSerialPort::readyRead, this, [this]() {
    while (port_ && port_->canReadLine()) {
      const QByteArray raw = port_->readLine();
      const QString line = QString::fromUtf8(raw).trimmed();
      if (!line.isEmpty()) emit messageReceived(line);
    }
  });
  emit statusChanged(true);
  return {true, QString("Terhubung ke %1 @ %2 baud").arg(port).arg(baudrate)};
}

void SerialController::disconnectPort() {
  if (!port_) return;
  port_->close();
  port_->deleteLater();
  port_ = nullptr;
  emit statusChanged(false);
}

bool SerialController::isConnected() const {
  return port_ && port_->isOpen();
}

std::pair<bool, QString> SerialController::send(const QString& command) {
  if (!isConnected()) return {false, "Belum terhubung ke Arduino"};
  const QByteArray data = (command.trimmed() + "\n").toUtf8();
  const qint64 n = port_->write(data);
  if (n < 0) return {false, port_->errorString()};
  port_->flush();
  return {true, QString("Terkirim: %1").arg(command)};
}

std::pair<bool, QString> SerialController::setX(double cm) {
  return send(QString("x=%1").arg(cm));
}
std::pair<bool, QString> SerialController::setY(double cm) {
  return send(QString("y=%1").arg(cm));
}
std::pair<bool, QString> SerialController::startScan() { return send("start"); }
std::pair<bool, QString> SerialController::stopScan() { return send("stop"); }
std::pair<bool, QString> SerialController::jogKanan() { return send("kanan"); }
std::pair<bool, QString> SerialController::jogKiri() { return send("kiri"); }
std::pair<bool, QString> SerialController::jogMaju() { return send("maju"); }
std::pair<bool, QString> SerialController::jogMundur() { return send("mundur"); }

std::pair<bool, QString> SerialController::setLaserFreq(double hz) {
  if (hz < 0.1 || hz > 20000.0)
    return {false, "Frekuensi laser di luar rentang (0.1 .. 20000 Hz)"};
  QString teks;
  if (std::abs(hz - std::round(hz)) < 1e-9)
    teks = QString::number(static_cast<int>(std::lround(hz)));
  else
    teks = QString::number(hz, 'f', 2);
  return send(QString("f=%1").arg(teks));
}

}  // namespace pa
