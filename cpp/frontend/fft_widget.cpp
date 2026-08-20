#include "frontend/fft_widget.hpp"

#include <algorithm>
#include <cmath>

#include <QVBoxLayout>
#include <QHBoxLayout>
#include <QGridLayout>
#include <QComboBox>
#include <QLineEdit>
#include <QLabel>
#include <QPushButton>
#include <QCheckBox>
#include <QGroupBox>
#include <QTimer>
#include <QMessageBox>
#include <QPainter>
#include <QtCharts/QChart>
#include <QtCharts/QChartView>
#include <QtCharts/QLineSeries>
#include <QtCharts/QValueAxis>

#include "backend/config.hpp"

namespace pa {

FftWidget::FftWidget(QWidget* parent) : QWidget(parent), audio_([this](const std::string& m) {
  Q_UNUSED(m);
}) {
  applied_fmin_ = TARGET_FREQ_HZ;
  auto* lay = new QVBoxLayout(this);

  chk_log_ = new QCheckBox("Skala Log (dB)");
  lay->addWidget(chk_log_);

  series_wave_ = new QLineSeries();
  chart_wave_ = new QChart();
  chart_wave_->legend()->hide();
  chart_wave_->addSeries(series_wave_);
  chart_wave_->setTitle("1. Waveform (Domain Waktu)");
  auto* axXw = new QValueAxis();
  axXw->setRange(0, 1);
  axXw->setTitleText("Waktu (s)");
  auto* axYw = new QValueAxis();
  axYw->setRange(-1.05, 1.05);
  axYw->setTitleText("Amplitudo");
  chart_wave_->addAxis(axXw, Qt::AlignBottom);
  chart_wave_->addAxis(axYw, Qt::AlignLeft);
  series_wave_->attachAxis(axXw);
  series_wave_->attachAxis(axYw);
  view_wave_ = new QChartView(chart_wave_);
  view_wave_->setRenderHint(QPainter::Antialiasing);
  lay->addWidget(view_wave_, 1);

  series_fft_ = new QLineSeries();
  chart_fft_ = new QChart();
  chart_fft_->legend()->hide();
  chart_fft_->addSeries(series_fft_);
  chart_fft_->setTitle("2. FFT (Domain Frekuensi)");
  auto* axXf = new QValueAxis();
  axXf->setRange(TARGET_FREQ_HZ, FFT_MAX_FREQ_HZ);
  axXf->setTitleText("Frekuensi (Hz)");
  auto* axYf = new QValueAxis();
  axYf->setRange(0, 0.01);
  axYf->setTitleText("Amplitudo");
  chart_fft_->addAxis(axXf, Qt::AlignBottom);
  chart_fft_->addAxis(axYf, Qt::AlignLeft);
  series_fft_->attachAxis(axXf);
  series_fft_->attachAxis(axYf);
  view_fft_ = new QChartView(chart_fft_);
  view_fft_->setRenderHint(QPainter::Antialiasing);
  lay->addWidget(view_fft_, 1);

  auto* out = new QGroupBox("3. Nilai Hasil (Output)");
  auto* outLay = new QHBoxLayout(out);
  lbl_peak_f_ = new QLabel("Frekuensi Puncak: - Hz");
  lbl_peak_a_ = new QLabel("Amplitudo Puncak: -");
  QFont bold = lbl_peak_f_->font();
  bold.setBold(true);
  bold.setPointSize(bold.pointSize() + 1);
  lbl_peak_f_->setFont(bold);
  lbl_peak_a_->setFont(bold);
  outLay->addWidget(lbl_peak_f_);
  outLay->addWidget(lbl_peak_a_);
  lay->addWidget(out);

  timer_ = new QTimer(this);
  connect(timer_, &QTimer::timeout, this, &FftWidget::updatePlots);
}

void FftWidget::mountMicControls(QWidget* parentRow) {
  auto* grid = qobject_cast<QGridLayout*>(parentRow->layout());
  if (!grid) return;
  const int row = grid->rowCount();
  grid->addWidget(new QLabel("Device:"), row, 0);
  cmb_device_ = new QComboBox;
  grid->addWidget(cmb_device_, row, 1);
  btn_refresh_ = new QPushButton("Refresh");
  grid->addWidget(btn_refresh_, row, 2);
  btn_connect_mic_ = new QPushButton("Connect Mic");
  grid->addWidget(btn_connect_mic_, row, 3);
  lbl_mic_ = new QLabel("● Mic belum aktif");
  lbl_mic_->setStyleSheet("color: red;");
  grid->addWidget(lbl_mic_, row + 1, 0, 1, 4);
  connect(btn_refresh_, &QPushButton::clicked, this, &FftWidget::refreshDevices);
  connect(btn_connect_mic_, &QPushButton::clicked, this, &FftWidget::connectMic);
  refreshDevices();
}

void FftWidget::mountFreqPanel(QWidget* parentCol) {
  auto* box = new QGroupBox("Frekuensi Modulasi Laser (Hz)", parentCol);
  auto* lay = qobject_cast<QVBoxLayout*>(parentCol->layout());
  if (lay) lay->addWidget(box);
  auto* root = new QVBoxLayout(box);
  auto* row = new QHBoxLayout;
  entry_freq_ = new QLineEdit(QString::number(static_cast<int>(TARGET_FREQ_HZ)));
  btn_set_freq_ = new QPushButton("Set Modulasi");
  row->addWidget(entry_freq_);
  row->addWidget(btn_set_freq_);
  root->addLayout(row);
  auto* hint = new QLabel(
      "Set Modulasi: objek di frekuensi itu; < frekuensi itu = background hitam di citra");
  hint->setWordWrap(true);
  hint->setStyleSheet("color: #555;");
  root->addWidget(hint);
  connect(btn_set_freq_, &QPushButton::clicked, this, &FftWidget::setFrekuensi);
  connect(entry_freq_, &QLineEdit::returnPressed, this, &FftWidget::setFrekuensi);
}

double FftWidget::getFftMinHz() const {
  double fmin = applied_fmin_;
  if (fmin >= FFT_MAX_FREQ_HZ) fmin = FFT_MAX_FREQ_HZ - 1.0;
  return fmin;
}

void FftWidget::refreshDevices() {
  if (!cmb_device_) return;
  cmb_device_->clear();
  for (const auto& [idx, label] : AudioCapture::listInputDevices(true)) {
    cmb_device_->addItem(QString::fromStdString(label), idx);
  }
}

void FftWidget::connectMic() {
  if (!cmb_device_ || cmb_device_->count() == 0) {
    QMessageBox::warning(this, "Mic", "Pilih device mic dulu.");
    return;
  }
  confirmed_device_ = cmb_device_->currentData().toInt();
  confirmed_label_ = cmb_device_->currentText();
  mic_connected_ = true;
  lbl_mic_->setText("● Mic aktif");
  lbl_mic_->setStyleSheet("color: green;");
}

std::pair<bool, QString> FftWidget::ensureAudioStarted() {
  if (audio_.isRunning()) return {true, "Audio sudah aktif."};
  if (!mic_connected_ || confirmed_device_ < 0)
    return {false, "Mic belum terhubung. Klik Connect Mic dulu."};
  auto [ok, msg] = audio_.start(confirmed_device_, AUDIO_SAMPLERATE, 1);
  if (ok) {
    lbl_mic_->setText("● Mic aktif");
    lbl_mic_->setStyleSheet("color: green;");
    timer_->start(50);
  }
  return {ok, QString::fromStdString(msg)};
}

void FftWidget::stopAudio() {
  timer_->stop();
  audio_.stop();
}

void FftWidget::setDeviceLock(bool locked) {
  if (!cmb_device_) return;
  cmb_device_->setEnabled(!locked);
  btn_refresh_->setEnabled(!locked);
  btn_connect_mic_->setEnabled(!locked);
}

void FftWidget::setFreqLock(bool locked) {
  if (!entry_freq_) return;
  entry_freq_->setEnabled(!locked);
  btn_set_freq_->setEnabled(!locked);
}

void FftWidget::setFrekuensi() {
  bool ok = false;
  const double nilai = entry_freq_->text().trimmed().replace(',', '.').toDouble(&ok);
  if (!ok || nilai <= 0 || nilai > FFT_MAX_FREQ_HZ) {
    QMessageBox::warning(this, "Frekuensi",
                         "Nilai valid: > 0 dan maksimal 20000 Hz.");
    entry_freq_->setText(QString::number(applied_fmin_));
    return;
  }
  applied_fmin_ = nilai;
  freq_set_ = true;
  entry_freq_->setText(QString::number(nilai));
  emit frekuensiDitetapkan(nilai);
}

void FftWidget::updatePlots() {
  if (!audio_.isRunning()) return;
  const auto wave = audio_.getWaveform();
  series_wave_->clear();
  const int n = static_cast<int>(wave.size());
  const int step = std::max(1, n / 1000);
  for (int i = 0; i < n; i += step) {
    const double t = static_cast<double>(i) / audio_.samplerate();
    series_wave_->append(t, wave[static_cast<size_t>(i)]);
  }

  const double fmin = getFftMinHz();
  const double fmax = getFftMaxHz();
  auto* axXf = qobject_cast<QValueAxis*>(chart_fft_->axes(Qt::Horizontal).value(0));
  if (axXf) axXf->setRange(fmin, fmax);

  auto [freqs, mag] = audio_.getFft(fmin, fmax);
  series_fft_->clear();
  double ymax = 0.01;
  const bool is_log = chk_log_->isChecked();
  for (size_t i = 0; i < freqs.size(); ++i) {
    double y = mag[i];
    if (is_log) y = 20.0 * std::log10(std::max(y, 1e-12));
    series_fft_->append(freqs[i], y);
    ymax = std::max(ymax, y);
  }
  auto* axYf = qobject_cast<QValueAxis*>(chart_fft_->axes(Qt::Vertical).value(0));
  if (axYf) {
    if (is_log)
      axYf->setRange(ymax - 60, ymax + 5);
    else
      axYf->setRange(0, ymax * 1.15);
  }

  auto [pf, pa] = audio_.getPeak(fmin, fmax);
  lbl_peak_f_->setText(QString("Frekuensi Puncak: %1 Hz").arg(pf, 0, 'f', 1));
  lbl_peak_a_->setText(QString("Amplitudo Puncak: %1").arg(pa, 0, 'f', 6));
}

}  // namespace pa
