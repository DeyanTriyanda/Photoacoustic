#pragma once

#include <utility>

#include <QWidget>
#include <QString>
#include <QVector>
#include <QPointF>

#include "backend/audio_capture.hpp"

class QComboBox;
class QLineEdit;
class QLabel;
class QPushButton;
class QCheckBox;
class QTimer;
class QChartView;
class QLineSeries;
class QScatterSeries;
class QChart;
class QValueAxis;

namespace pa {

// Target refresh ~60 FPS (16 ms); Python memakai 50 ms.
constexpr int FFT_UPDATE_INTERVAL_MS = 16;

class FftWidget : public QWidget {
  Q_OBJECT
 public:
  explicit FftWidget(QWidget* parent = nullptr);

  void mountMicControls(QWidget* parentRow);
  void mountFreqPanel(QWidget* parentCol);

  AudioCapture& audio() { return audio_; }
  bool isMicConnected() const { return mic_connected_; }
  bool isFrekuensiDitetapkan() const { return freq_set_; }
  double getModulasiHz() const { return applied_fmin_; }
  double getFftMinHz() const;
  double getFftMaxHz() const { return 20000.0; }

  std::pair<bool, QString> ensureAudioStarted();
  void stopAudio();
  void setDeviceLock(bool locked);
  void setFreqLock(bool locked);

 signals:
  void frekuensiDitetapkan(double hz);

 private slots:
  void refreshDevices();
  void connectMic();
  void setFrekuensi();
  void updatePlots();

 private:
  void restoreFreqEntry();

  AudioCapture audio_;
  bool mic_connected_ = false;
  bool freq_set_ = false;
  double applied_fmin_ = 17000.0;
  int confirmed_device_ = -1;
  QString confirmed_label_;

  double last_fmin_ = -1.0;
  double last_fmax_ = -1.0;
  int last_logscale_ = -1;

  QComboBox* cmb_device_ = nullptr;
  QPushButton* btn_refresh_ = nullptr;
  QPushButton* btn_connect_mic_ = nullptr;
  QLabel* lbl_mic_ = nullptr;
  QLineEdit* entry_freq_ = nullptr;
  QPushButton* btn_set_freq_ = nullptr;
  QCheckBox* chk_log_ = nullptr;
  QLabel* lbl_peak_f_ = nullptr;
  QLabel* lbl_peak_a_ = nullptr;

  QChart* chart_wave_ = nullptr;
  QChart* chart_fft_ = nullptr;
  QLineSeries* series_wave_ = nullptr;
  QLineSeries* series_fft_ = nullptr;
  QScatterSeries* series_peak_ = nullptr;
  QValueAxis* ax_x_fft_ = nullptr;
  QValueAxis* ax_y_fft_ = nullptr;
  QChartView* view_wave_ = nullptr;
  QChartView* view_fft_ = nullptr;
  QTimer* timer_ = nullptr;
};

}  // namespace pa
