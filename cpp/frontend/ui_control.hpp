#pragma once

#include <QMainWindow>
#include <QHash>
#include <QElapsedTimer>

class QComboBox;
class QLineEdit;
class QLabel;
class QPushButton;
class QTabWidget;
class QTimer;

namespace pa {

class SerialController;
class FftWidget;
class SpatialMapWidget;
class DeepLearningWidget;

class ScanControlApp : public QMainWindow {
  Q_OBJECT
 public:
  explicit ScanControlApp(QWidget* parent = nullptr);
  ~ScanControlApp() override;

 private slots:
  void refreshPorts();
  void toggleConnect();
  void onFrekuensi(double hz);
  void updateHitungan();
  void toggleArea();
  void toggleScan();
  void onSerialMessage(const QString& line);
  void onSerialStatus(bool connected);
  void updateWaktuTempuh();

 private:
  void buildUi();
  void setScanStatus(bool aktif);
  void log(const QString& text);  // latar belakang saja (stdout)
  bool getXy(double* x, double* y) const;
  void pasangTombolJog(QPushButton* tombol,
                       std::pair<bool, QString> (SerialController::*fungsi)());
  void jogMulai(std::pair<bool, QString> (SerialController::*fungsi)());
  void jogBerhenti();
  void updateProgressUi(int col, int row, int n_done, int n_total);
  void resetProgressIcons();

  SerialController* controller_ = nullptr;
  FftWidget* fft_ = nullptr;
  SpatialMapWidget* spatial_ = nullptr;
  DeepLearningWidget* dl_ = nullptr;

  QComboBox* cmb_port_ = nullptr;
  QPushButton* btn_refresh_port_ = nullptr;
  QPushButton* btn_connect_ = nullptr;
  QLabel* lbl_status_ = nullptr;
  QLineEdit* entry_x_ = nullptr;
  QLineEdit* entry_y_ = nullptr;
  QPushButton* btn_set_area_ = nullptr;
  QPushButton* btn_scan_ = nullptr;
  QLabel* lbl_titik_x_ = nullptr;
  QLabel* lbl_baris_y_ = nullptr;
  QLabel* lbl_total_ = nullptr;
  QLabel* lbl_icon_x_ = nullptr;
  QLabel* lbl_icon_y_ = nullptr;
  QLabel* lbl_icon_total_ = nullptr;
  QLabel* lbl_waktu_ = nullptr;
  QLabel* lbl_waktu_tempuh_ = nullptr;
  QPushButton* btn_maju_ = nullptr;
  QPushButton* btn_mundur_ = nullptr;
  QPushButton* btn_kiri_ = nullptr;
  QPushButton* btn_kanan_ = nullptr;
  QTimer* timer_tempuh_ = nullptr;
  QElapsedTimer scan_elapsed_;

  QHash<QString, QString> port_map_;
  bool scanning_ = false;
  bool area_locked_ = false;
  int last_tx_ = 0;
  int last_ty_ = 0;
};

int runApp(int argc, char** argv);

}  // namespace pa
