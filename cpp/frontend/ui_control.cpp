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
#include <QTabWidget>
#include <QMessageBox>
#include <QMetaObject>
#include <QRegularExpression>
#include <QTimer>
#include <QDebug>
#include <QSizePolicy>

#include "backend/config.hpp"
#include "backend/control.hpp"
#include "backend/scan_timing.hpp"
#include "frontend/fft_widget.hpp"
#include "frontend/spatial_map_widget.hpp"
#include "frontend/deep_learning_widget.hpp"

namespace pa {
namespace {

QString styleSetArea() {
  return "QPushButton { background:#ffc107; color:black; font-weight:bold; "
         "padding:4px 8px; }";
}
QString styleStart() {
  return "QPushButton { background:#28a745; color:white; font-weight:bold; "
         "padding:4px 8px; }";
}
QString styleStop() {
  return "QPushButton { background:#dc3545; color:white; font-weight:bold; "
         "padding:4px 8px; }";
}

}  // namespace

ScanControlApp::ScanControlApp(QWidget* parent) : QMainWindow(parent) {
  setWindowTitle("Photoacoustic Imaging");
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

  auto* conn = new QGroupBox("Koneksi Serial (Arduino Stepper)");
  auto* connLay = new QGridLayout(conn);
  connLay->addWidget(new QLabel("Port:"), 0, 0);
  cmb_port_ = new QComboBox;
  connLay->addWidget(cmb_port_, 0, 1);
  btn_refresh_port_ = new QPushButton("Refresh");
  connLay->addWidget(btn_refresh_port_, 0, 2);
  btn_connect_ = new QPushButton("Connect");
  connLay->addWidget(btn_connect_, 0, 3);
  lbl_status_ = new QLabel("● Belum terhubung");
  lbl_status_->setStyleSheet("color: red;");
  connLay->addWidget(lbl_status_, 1, 0, 1, 4);
  leftLay->addWidget(conn);
  connect(btn_refresh_port_, &QPushButton::clicked, this,
          &ScanControlApp::refreshPorts);
  connect(btn_connect_, &QPushButton::clicked, this, &ScanControlApp::toggleConnect);

  auto* tabs = new QTabWidget;
  rightLay->addWidget(tabs);
  fft_ = new FftWidget;
  spatial_ = new SpatialMapWidget;
  dl_ = new DeepLearningWidget(spatial_);
  tabs->addTab(fft_, "FFT Fotoakustik");
  tabs->addTab(spatial_, "Citra 2D Fotoakustik");
  tabs->addTab(dl_, "Deep Learning");
  // Hemat CPU: pause plot FFT saat tab lain aktif
  connect(tabs, &QTabWidget::currentChanged, this, [this](int idx) {
    if (fft_) fft_->setPlotActive(idx == 0);
  });

  fft_->mountMicControls(conn);
  fft_->mountFreqPanel(left);
  connect(fft_, &FftWidget::frekuensiDitetapkan, this, &ScanControlApp::onFrekuensi);
  connect(spatial_, &SpatialMapWidget::grayscaleReadyChanged, dl_,
          &DeepLearningWidget::setGrayscaleReady);

  auto* samp = new QGroupBox("Sampling Points");
  auto* sampLay = new QGridLayout(samp);
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
  btn_set_area_->setStyleSheet(styleSetArea());
  // Ukuran tetap agar teks "Set Area" / "Edit" tidak terpotong / mengecil
  btn_set_area_->setMinimumWidth(88);
  btn_set_area_->setFixedHeight(28);
  btn_set_area_->setSizePolicy(QSizePolicy::Fixed, QSizePolicy::Fixed);
  btn_scan_ = new QPushButton("▶ Start");
  btn_scan_->setStyleSheet(styleStart());
  btn_scan_->setMinimumWidth(88);
  btn_scan_->setFixedHeight(28);
  btn_scan_->setSizePolicy(QSizePolicy::Fixed, QSizePolicy::Fixed);
  xy->addWidget(btn_set_area_);
  xy->addWidget(btn_scan_);
  sampLay->addLayout(xy, 0, 0, 1, 2);

  lbl_titik_x_ = new QLabel("X point: 0 / -");
  lbl_icon_x_ = new QLabel(QString::fromUtf8("⚪"));
  lbl_baris_y_ = new QLabel("Y point: 0 / -");
  lbl_icon_y_ = new QLabel(QString::fromUtf8("⚪"));
  lbl_total_ = new QLabel("total point: 0 / -");
  QFont bold = lbl_total_->font();
  bold.setBold(true);
  lbl_total_->setFont(bold);
  lbl_icon_total_ = new QLabel(QString::fromUtf8("⚪"));
  lbl_waktu_ = new QLabel("Waktu target: -");
  lbl_waktu_tempuh_ = new QLabel("Waktu tempuh: -");

  sampLay->addWidget(lbl_titik_x_, 1, 0);
  sampLay->addWidget(lbl_icon_x_, 1, 1, Qt::AlignRight);
  sampLay->addWidget(lbl_baris_y_, 2, 0);
  sampLay->addWidget(lbl_icon_y_, 2, 1, Qt::AlignRight);
  sampLay->addWidget(lbl_total_, 3, 0);
  sampLay->addWidget(lbl_icon_total_, 3, 1, Qt::AlignRight);
  sampLay->addWidget(lbl_waktu_, 4, 0, 1, 2);
  sampLay->addWidget(lbl_waktu_tempuh_, 5, 0, 1, 2);
  leftLay->addWidget(samp);

  connect(entry_x_, &QLineEdit::textChanged, this, &ScanControlApp::updateHitungan);
  connect(entry_y_, &QLineEdit::textChanged, this, &ScanControlApp::updateHitungan);
  connect(btn_set_area_, &QPushButton::clicked, this, &ScanControlApp::toggleArea);
  connect(btn_scan_, &QPushButton::clicked, this, &ScanControlApp::toggleScan);

  timer_tempuh_ = new QTimer(this);
  connect(timer_tempuh_, &QTimer::timeout, this, &ScanControlApp::updateWaktuTempuh);

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
  leftLay->addStretch();
  // Catatan: panel serial monitor dihapus — log hanya ke stdout/qDebug
  pasangTombolJog(btn_maju_, &SerialController::jogMaju);
  pasangTombolJog(btn_mundur_, &SerialController::jogMundur);
  pasangTombolJog(btn_kiri_, &SerialController::jogKiri);
  pasangTombolJog(btn_kanan_, &SerialController::jogKanan);

  spatial_->setProgressCallback([this](int col, int row, int n_done, int n_total) {
    QMetaObject::invokeMethod(this, [this, col, row, n_done, n_total]() {
      updateProgressUi(col, row, n_done, n_total);
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
  if (scanning_) {
    QMessageBox::warning(this, "Scanning",
                         "Tidak bisa Connect/Disconnect saat scan berlangsung.");
    return;
  }
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
  btn_connect_->setEnabled(false);
  cmb_port_->setEnabled(false);
  btn_refresh_port_->setEnabled(false);
  lbl_status_->setText("● Menghubungkan...");
  lbl_status_->setStyleSheet("color: #b8860b;");
  QApplication::processEvents();
  log(QString("Menghubungkan ke %1 ...").arg(port));

  auto [ok, msg] = controller_->connectTo(port, DEFAULT_BAUDRATE);
  btn_connect_->setEnabled(true);
  cmb_port_->setEnabled(true);
  btn_refresh_port_->setEnabled(true);
  log(msg);
  if (!ok) {
    lbl_status_->setText("● Belum terhubung");
    lbl_status_->setStyleSheet("color: red;");
    QMessageBox::critical(this, "Gagal terhubung", msg);
  } else if (fft_->isFrekuensiDitetapkan()) {
    log(controller_->setLaserFreq(fft_->getModulasiHz()).second);
  }
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
    last_tx_ = last_ty_ = 0;
    return;
  }
  last_tx_ = hitung_titik_per_baris(x);
  last_ty_ = hitung_jumlah_baris(y);
  lbl_titik_x_->setText(QString("X point: 0 / %1").arg(last_tx_));
  lbl_baris_y_->setText(QString("Y point: 0 / %1").arg(last_ty_));
  lbl_total_->setText(QString("total point: 0 / %1").arg(last_tx_ * last_ty_));
  lbl_waktu_->setText(
      "Waktu target: " +
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
    // Jangan stop audio FFT live — hanya hentikan scan
    setScanStatus(false);
    return;
  }
  if (!controller_->isConnected()) {
    QMessageBox::warning(this, "Arduino", "Hubungkan Arduino dulu.");
    return;
  }
  if (!fft_->isFrekuensiDitetapkan()) {
    QMessageBox::warning(
        this, "Modulasi",
        "Isi frekuensi modulasi lalu klik Set Modulasi sebelum Start scan.");
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
  log(controller_->setX(x).second);
  log(controller_->setY(y).second);

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
  btn_refresh_port_->setEnabled(!aktif);
  btn_connect_->setEnabled(!aktif);
  btn_maju_->setEnabled(!aktif);
  btn_mundur_->setEnabled(!aktif);
  btn_kiri_->setEnabled(!aktif);
  btn_kanan_->setEnabled(!aktif);
  btn_set_area_->setEnabled(!aktif);
  if (aktif) {
    btn_scan_->setText("■ Stop");
    btn_scan_->setStyleSheet(styleStop());
    resetProgressIcons();
    lbl_waktu_tempuh_->setText("Waktu tempuh: 0 jam 0 menit");
    scan_elapsed_.restart();
    timer_tempuh_->start(1000);
  } else {
    btn_scan_->setText("▶ Start");
    btn_scan_->setStyleSheet(styleStart());
    timer_tempuh_->stop();
  }
}

void ScanControlApp::updateWaktuTempuh() {
  if (!scanning_) return;
  const qint64 sec = scan_elapsed_.elapsed() / 1000;
  const int jam = static_cast<int>(sec / 3600);
  const int menit = static_cast<int>((sec % 3600) / 60);
  lbl_waktu_tempuh_->setText(
      QString("Waktu tempuh: %1 jam %2 menit").arg(jam).arg(menit));
}

void ScanControlApp::resetProgressIcons() {
  lbl_icon_x_->setText(QString::fromUtf8("⚪"));
  lbl_icon_y_->setText(QString::fromUtf8("⚪"));
  lbl_icon_total_->setText(QString::fromUtf8("⚪"));
}

void ScanControlApp::updateProgressUi(int col, int row, int n_done, int n_total) {
  const int tx = last_tx_ > 0 ? last_tx_ : 1;
  const int ty = last_ty_ > 0 ? last_ty_ : 1;
  const int curr_x = col + 1;
  const int curr_y = row + 1;
  lbl_titik_x_->setText(QString("X point: %1 / %2").arg(curr_x).arg(tx));
  lbl_baris_y_->setText(QString("Y point: %1 / %2").arg(curr_y).arg(ty));
  lbl_total_->setText(QString("total point: %1 / %2").arg(n_done).arg(n_total));
  lbl_icon_x_->setText(curr_x >= tx ? QString::fromUtf8("✅")
                                    : QString::fromUtf8("⚪"));
  lbl_icon_y_->setText(curr_y >= ty ? QString::fromUtf8("✅")
                                    : QString::fromUtf8("⚪"));
  lbl_icon_total_->setText(n_done >= n_total ? QString::fromUtf8("✅")
                                             : QString::fromUtf8("⚪"));
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
  // Latar belakang saja (sama prinsip Python print ke konsol)
  qInfo().noquote() << "[SERIAL]" << text;
}

void ScanControlApp::pasangTombolJog(
    QPushButton* tombol,
    std::pair<bool, QString> (SerialController::*fungsi)()) {
  tombol->setAutoRepeat(false);
  connect(tombol, &QPushButton::pressed, this, [this, fungsi]() {
    jogMulai(fungsi);
  });
  connect(tombol, &QPushButton::released, this, [this]() {
    jogBerhenti();
  });
}

void ScanControlApp::jogMulai(
    std::pair<bool, QString> (SerialController::*fungsi)()) {
  if (!controller_->isConnected()) {
    QMessageBox::warning(this, "Belum terhubung",
                         "Hubungkan ke Arduino terlebih dahulu.");
    return;
  }
  if (scanning_) {
    QMessageBox::warning(
        this, "Scanning sedang berlangsung",
        "Kontrol manual (jog) dikunci karena raster scan sedang berproses.");
    return;
  }
  const auto result = (controller_->*fungsi)();
  log(result.first ? result.second
                   : QString("Gagal mengirim perintah jog: %1").arg(result.second));
}

void ScanControlApp::jogBerhenti() {
  if (!controller_->isConnected() || scanning_) return;
  const auto result = controller_->stopScan();
  log(result.first ? result.second
                   : QString("Gagal mengirim stop: %1").arg(result.second));
}

int runApp(int argc, char** argv) {
  QApplication app(argc, argv);
  ScanControlApp win;
  win.show();
  return app.exec();
}

}  // namespace pa
