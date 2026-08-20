#pragma once

#include <QMainWindow>
#include <QHash>

class QComboBox;
class QLineEdit;
class QLabel;
class QPushButton;
class QTextEdit;
class QTabWidget;

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

 private:
  void buildUi();
  void setScanStatus(bool aktif);
  void log(const QString& text);
  bool getXy(double* x, double* y) const;
  void pasangTombolJog(QPushButton* tombol,
                       std::pair<bool, QString> (SerialController::*fungsi)());
  void jogMulai(std::pair<bool, QString> (SerialController::*fungsi)());
  void jogBerhenti();

  SerialController* controller_ = nullptr;
  FftWidget* fft_ = nullptr;
  SpatialMapWidget* spatial_ = nullptr;
  DeepLearningWidget* dl_ = nullptr;

  QComboBox* cmb_port_ = nullptr;
  QPushButton* btn_connect_ = nullptr;
  QLabel* lbl_status_ = nullptr;
  QLineEdit* entry_x_ = nullptr;
  QLineEdit* entry_y_ = nullptr;
  QPushButton* btn_set_area_ = nullptr;
  QPushButton* btn_scan_ = nullptr;
  QLabel* lbl_titik_x_ = nullptr;
  QLabel* lbl_baris_y_ = nullptr;
  QLabel* lbl_total_ = nullptr;
  QLabel* lbl_waktu_ = nullptr;
  QPushButton* btn_maju_ = nullptr;
  QPushButton* btn_mundur_ = nullptr;
  QPushButton* btn_kiri_ = nullptr;
  QPushButton* btn_kanan_ = nullptr;
  QTextEdit* log_ = nullptr;

  QHash<QString, QString> port_map_;
  bool scanning_ = false;
  bool area_locked_ = false;
};

int runApp(int argc, char** argv);

}  // namespace pa
