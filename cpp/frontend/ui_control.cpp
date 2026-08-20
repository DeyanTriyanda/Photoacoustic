#include "frontend/ui_control.hpp"

#include <QApplication>
#include <QWidget>
#include <QHBoxLayout>
#include <QVBoxLayout>
#include <QGridLayout>
#include <QGroupBox>
#include <QComboBox>
#include <QLineEdit>
#include <QLabel>
#include <QPushButton>
#include <QTextEdit>
#include <QTabWidget>
#include <QMessageBox>
#include <QMetaObject>
#include <QRegularExpression>

#include "backend/config.hpp"
#include "backend/control.hpp"
#include "backend/scan_timing.hpp"
#include "frontend/fft_widget.hpp"
#include "frontend/spatial_map_widget.hpp"
#include "frontend/deep_learning_widget.hpp"

namespace pa {

ScanControlApp::ScanControlApp(QWidget* parent) : QMainWindow(parent) {
  setWindowTitle("Photoacoustic Imaging (C++)");
  controller_ = new SerialController(this);
  connect(controller_, &SerialController::messageReceived, this,
          &ScanControlApp::onSerialMessage);
  connect(controller_, &SerialController::statusChanged, this,
          &ScanControlApp::onSerialStatus);
  buildUi();
  refreshPorts();
  showMaximized();
}

ScanControlApp::~ScanControlApp() {
  if (fft_) fft_->stopAudio();
  if (spatial_) spatial_->stopCapture();
}

void ScanControlApp::buildUi() {
  auto* central = new QWidget(this);
  setCentralWidget(central);
  auto* root = new QHBoxLayout(central);

  auto* left = new QWidget;
  auto* leftLay = new QVBoxLayout(left);
  left->setMaximumWidth(360);
  root->addWidget(left);

  auto* right = new QWidget;
  auto* rightLay = new QVBoxLayout(right);
  root->addWidget(right, 1);

  // 1. Koneksi Serial
  auto* conn = new QGroupBox("Koneksi Serial (Arduino Stepper)");
  auto* connLay = new QGridLayout(conn);
  connLay->addWidget(new QLabel("Port:"), 0, 0);
  cmb_port_ = new QComboBox;
  connLay->addWidget(cmb_port_, 0, 1);
  auto* btn_refresh = new QPushButton("Refresh");
  connLay->addWidget(btn_refresh, 0, 2);
  btn_connect_ = new QPushButton("Connect");
  connLay->addWidget(btn_connect_, 0, 3);
  lbl_status_ = new QLabel("● Belum terhubung");
  lbl_status_->setStyleSheet("color: red;");
  connLay->addWidget(lbl_status_, 1, 0, 1, 4);
  leftLay->addWidget(conn);
  connect(btn_refresh, &QPushButton::clicked, this, &ScanControlApp::refreshPorts);
  connect(btn_connect_, &QPushButton::clicked, this, &ScanControlApp::toggleConnect);

  auto* tabs = new QTabWidget;
  rightLay->addWidget(tabs);
  fft_ = new FftWidget;
  spatial_ = new SpatialMapWidget;
  dl_ = new DeepLearningWidget(spatial_);
  tabs->addTab(fft_, "FFT Fotoakustik");
  tabs->addTab(spatial_, "Citra 2D Fotoakustik");
  tabs->addTab(dl_, "Deep Learning");

  fft_->mountMicControls(conn);
  fft_->mountFreqPanel(left);
  connect(fft_, &FftWidget::frekuensiDitetapkan, this, &ScanControlApp::onFrekuensi);
  connect(spatial_, &SpatialMapWidget::grayscaleReadyChanged, dl_,
          &DeepLearningWidget::setGrayscaleReady);

  // 3. Sampling Points
  auto* samp = new QGroupBox("Sampling Points");
  auto* sampLay = new QVBoxLayout(samp);
  auto* xy = new QHBoxLayout;
  xy->addWidget(new QLabel("X:"));
  entry_x_ = new QLineEdit;
  entry_x_->setMaximumWidth(60);
  xy->addWidget(entry_x_);
  xy->addWidget(new QLabel("cm"));
  xy->addWidget(new QLabel("Y:"));
  entry_y_ = new QLineEdit;
  entry_y_->setMaximumWidth(60);
  xy->addWidget(entry_y_);
  xy->addWidget(new QLabel("cm"));
  btn_set_area_ = new QPushButton("Set Area");
  btn_scan_ = new QPushButton("▶ Start");
  xy->addWidget(btn_set_area_);
  xy->addWidget(btn_scan_);
  sampLay->addLayout(xy);
  lbl_titik_x_ = new QLabel("X point: 0 / -");
  lbl_baris_y_ = new QLabel("Y point: 0 / -");
  lbl_total_ = new QLabel("total point: 0 / -");
  lbl_waktu_ = new QLabel("Waktu target: -");
  sampLay->addWidget(lbl_titik_x_);
  sampLay->addWidget(lbl_baris_y_);
  sampLay->addWidget(lbl_total_);
  sampLay->addWidget(lbl_waktu_);
  leftLay->addWidget(samp);
  connect(entry_x_, &QLineEdit::textChanged, this, &ScanControlApp::updateHitungan);
  connect(entry_y_, &QLineEdit::textChanged, this, &ScanControlApp::updateHitungan);
  connect(btn_set_area_, &QPushButton::clicked, this, &ScanControlApp::toggleArea);
  connect(btn_scan_, &QPushButton::clicked, this, &ScanControlApp::toggleScan);

  // 4. Position Adjustment
  auto* jog = new QGroupBox("Position Adjustment");
  auto* jogLay = new QGridLayout(jog);
  btn_maju_ = new QPushButton("▲ Y+");
  btn_mundur_ = new QPushButton("▼ Y-");
  btn_kiri_ = new QPushButton("◀ X-");
  btn_kanan_ = new QPushButton("▶ X+");
  jogLay->addWidget(btn_maju_, 0, 1);
  jogLay->addWidget(btn_kiri_, 1, 0);
  jogLay->addWidget(btn_kanan_, 1, 2);
  jogLay->addWidget(btn_mundur_, 2, 1);
  leftLay->addWidget(jog);
  connect(btn_maju_, &QPushButton::clicked, this,
          [this]() { log(controller_->jogMaju().second); });
  connect(btn_mundur_, &QPushButton::clicked, this,
          [this]() { log(controller_->jogMundur().second); });
  connect(btn_kiri_, &QPushButton::clicked, this,
          [this]() { log(controller_->jogKiri().second); });
  connect(btn_kanan_, &QPushButton::clicked, this,
          [this]() { log(controller_->jogKanan().second); });

  log_ = new QTextEdit;
  log_->setReadOnly(true);
  log_->setMaximumHeight(140);
  leftLay->addWidget(log_);
  leftLay->addStretch();

  spatial_->setProgressCallback([this](int, int, int n_done, int n_total) {
    QMetaObject::invokeMethod(this, [this, n_done, n_total]() {
      double x = 0, y = 0;
      getXy(&x, &y);
      const int tx = hitung_titik_per_baris(x);
      const int ty = hitung_jumlah_baris(y);
      lbl_total_->setText(QString("total point: %1 / %2").arg(n_done).arg(n_total));
      Q_UNUSED(tx);
      Q_UNUSED(ty);
    });
  });
}

void ScanControlApp::refreshPorts() {
  cmb_port_->clear();
  port_map_.clear();
  for (const auto& [dev, label] : SerialController::listPorts()) {
    cmb_port_->addItem(label);
    port_map_.insert(label, dev);
  }
}

void ScanControlApp::toggleConnect() {
  if (controller_->isConnected()) {
    controller_->disconnectPort();
    log("Terputus dari Arduino.");
    return;
  }
  if (cmb_port_->currentText().isEmpty()) {
    QMessageBox::warning(this, "Port", "Pilih port serial dulu.");
    return;
  }
  const QString port = port_map_.value(cmb_port_->currentText(), cmb_port_->currentText());
  auto [ok, msg] = controller_->connectTo(port, DEFAULT_BAUDRATE);
  log(msg);
  if (!ok) QMessageBox::critical(this, "Gagal terhubung", msg);
  else if (fft_->isFrekuensiDitetapkan())
    log(controller_->setLaserFreq(fft_->getModulasiHz()).second);
}

void ScanControlApp::onFrekuensi(double hz) {
  spatial_->scanParams["target_freq_hz"] = hz;
  log(QString("Frekuensi modulasi %1 Hz → FFT min, target citra, Arduino laser.")
          .arg(hz));
  if (controller_->isConnected())
    log(controller_->setLaserFreq(hz).second);
}

void ScanControlApp::updateHitungan() {
  double x = 0, y = 0;
  if (!getXy(&x, &y)) {
    lbl_titik_x_->setText("X point: 0 / -");
    lbl_baris_y_->setText("Y point: 0 / -");
    lbl_total_->setText("total point: 0 / -");
    lbl_waktu_->setText("Waktu target: -");
    return;
  }
  const int tx = hitung_titik_per_baris(x);
  const int ty = hitung_jumlah_baris(y);
  lbl_titik_x_->setText(QString("X point: 0 / %1").arg(tx));
  lbl_baris_y_->setText(QString("Y point: 0 / %1").arg(ty));
  lbl_total_->setText(QString("total point: 0 / %1").arg(tx * ty));
  lbl_waktu_->setText("Waktu target: " +
                      QString::fromStdString(format_jam_menit(hitung_estimasi_durasi_s(x, y))));
}

bool ScanControlApp::getXy(double* x, double* y) const {
  bool okx = false, oky = false;
  *x = entry_x_->text().trimmed().replace(',', '.').toDouble(&okx);
  *y = entry_y_->text().trimmed().replace(',', '.').toDouble(&oky);
  return okx && oky && *x > 0 && *y > 0;
}

void ScanControlApp::toggleArea() {
  if (area_locked_) {
    area_locked_ = false;
    entry_x_->setEnabled(true);
    entry_y_->setEnabled(true);
    btn_set_area_->setText("Set Area");
    log("Mode Edit area.");
    return;
  }
  double x = 0, y = 0;
  if (!getXy(&x, &y)) {
    QMessageBox::warning(this, "Area", "Isi X dan Y > 0.");
    return;
  }
  if (!controller_->isConnected()) {
    QMessageBox::warning(this, "Arduino", "Hubungkan Arduino dulu.");
    return;
  }
  auto rx = controller_->setX(x);
  auto ry = controller_->setY(y);
  log(rx.second);
  log(ry.second);
  if (rx.first && ry.first) {
    area_locked_ = true;
    entry_x_->setEnabled(false);
    entry_y_->setEnabled(false);
    btn_set_area_->setText("Edit");
  }
}

void ScanControlApp::toggleScan() {
  if (scanning_) {
    controller_->stopScan();
    spatial_->stopCapture();
    fft_->stopAudio();
    setScanStatus(false);
    return;
  }
  if (!controller_->isConnected()) {
    QMessageBox::warning(this, "Arduino", "Hubungkan Arduino dulu.");
    return;
  }
  if (!fft_->isFrekuensiDitetapkan()) {
    QMessageBox::warning(this, "Modulasi", "Set Modulasi dulu.");
    return;
  }
  double x = 0, y = 0;
  if (!getXy(&x, &y)) {
    QMessageBox::warning(this, "Area", "Isi X/Y > 0.");
    return;
  }
  auto [ok_audio, msg_audio] = fft_->ensureAudioStarted();
  if (!ok_audio) {
    QMessageBox::warning(this, "Audio", msg_audio);
    return;
  }
  spatial_->scanParams["x_cm"] = x;
  spatial_->scanParams["y_cm"] = y;
  spatial_->scanParams["target_freq_hz"] = fft_->getModulasiHz();
  auto [ok_cap, msg_cap] = spatial_->startCapture(&fft_->audio());
  log(msg_cap);
  if (!ok_cap) return;
  log(controller_->startScan().second);
  setScanStatus(true);
}

void ScanControlApp::setScanStatus(bool aktif) {
  scanning_ = aktif;
  fft_->setDeviceLock(aktif);
  fft_->setFreqLock(aktif);
  cmb_port_->setEnabled(!aktif);
  btn_connect_->setEnabled(!aktif);
  btn_maju_->setEnabled(!aktif);
  btn_mundur_->setEnabled(!aktif);
  btn_kiri_->setEnabled(!aktif);
  btn_kanan_->setEnabled(!aktif);
  btn_set_area_->setEnabled(!aktif);
  if (aktif) {
    btn_scan_->setText("■ Stop");
  } else {
    btn_scan_->setText("▶ Start");
  }
}

void ScanControlApp::onSerialMessage(const QString& line) {
  log(line);
  const QString low = line.toLower();
  static const QRegularExpression re("scanning baris ke-(\\d+)");
  const auto m = re.match(low);
  if (m.hasMatch()) spatial_->resyncRow(m.captured(1).toInt());
  if (low.contains("selesai")) setScanStatus(false);
}

void ScanControlApp::onSerialStatus(bool connected) {
  if (connected) {
    lbl_status_->setText("● Terhubung");
    lbl_status_->setStyleSheet("color: green;");
    btn_connect_->setText("Disconnect");
  } else {
    lbl_status_->setText("● Belum terhubung");
    lbl_status_->setStyleSheet("color: red;");
    btn_connect_->setText("Connect");
  }
}

void ScanControlApp::log(const QString& text) {
  log_->append(text);
}

int runApp(int argc, char** argv) {
  QApplication app(argc, argv);
  ScanControlApp win;
  win.show();
  return app.exec();
}

}  // namespace pa
