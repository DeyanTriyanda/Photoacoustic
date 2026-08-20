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
#include <QtCharts/QScatterSeries>
#include <QtCharts/QValueAxis>

#include "backend/config.hpp"

namespace pa {
namespace {
constexpr int kMaxWavePts = 400;
constexpr int kMaxFftPts = 400;
}  // namespace

FftWidget::FftWidget(QWidget* parent) : QWidget(parent), audio_(nullptr) {
  applied_fmin_ = TARGET_FREQ_HZ;
  snap_.resize(static_cast<size_t>(kUiFftSamples));
  auto* lay = new QVBoxLayout(this);

  chk_log_ = new QCheckBox("Skala Log (dB)");
  lay->addWidget(chk_log_);

  series_wave_ = new QLineSeries();
  chart_wave_ = new QChart();
  chart_wave_->legend()->hide();
  chart_wave_->addSeries(series_wave_);
  chart_wave_->setTitle("1. Waveform (Domain Waktu)");
  chart_wave_->setAnimationOptions(QChart::NoAnimation);
  chart_wave_->setBackgroundRoundness(0);
  auto* axXw = new QValueAxis();
  axXw->setRange(0, 1);
  axXw->setTitleText("Waktu (s)");
  axXw->setTickCount(5);
  auto* axYw = new QValueAxis();
  axYw->setRange(-1.05, 1.05);
  axYw->setTitleText("Amplitudo");
  axYw->setTickCount(5);
  chart_wave_->addAxis(axXw, Qt::AlignBottom);
  chart_wave_->addAxis(axYw, Qt::AlignLeft);
  series_wave_->attachAxis(axXw);
  series_wave_->attachAxis(axYw);
  view_wave_ = new QChartView(chart_wave_);
  view_wave_->setRenderHint(QPainter::Antialiasing, false);
  lay->addWidget(view_wave_, 1);

  series_fft_ = new QLineSeries();
  series_peak_ = new QScatterSeries();
  series_peak_->setMarkerSize(8.0);
  series_peak_->setColor(Qt::red);
  chart_fft_ = new QChart();
  chart_fft_->legend()->hide();
  chart_fft_->addSeries(series_fft_);
  chart_fft_->addSeries(series_peak_);
  chart_fft_->setTitle("2. FFT (Domain Frekuensi)");
  chart_fft_->setAnimationOptions(QChart::NoAnimation);
  chart_fft_->setBackgroundRoundness(0);
  ax_x_fft_ = new QValueAxis();
  ax_x_fft_->setRange(TARGET_FREQ_HZ, FFT_MAX_FREQ_HZ);
  ax_x_fft_->setTitleText("Frekuensi (Hz)");
  ax_x_fft_->setTickCount(6);
  ax_y_fft_ = new QValueAxis();
  ax_y_fft_->setRange(0, 0.01);
  ax_y_fft_->setTitleText("Amplitudo");
  ax_y_fft_->setTickCount(5);
  chart_fft_->addAxis(ax_x_fft_, Qt::AlignBottom);
  chart_fft_->addAxis(ax_y_fft_, Qt::AlignLeft);
  series_fft_->attachAxis(ax_x_fft_);
  series_fft_->attachAxis(ax_y_fft_);
  series_peak_->attachAxis(ax_x_fft_);
  series_peak_->attachAxis(ax_y_fft_);
  view_fft_ = new QChartView(chart_fft_);
  view_fft_->setRenderHint(QPainter::Antialiasing, false);
  lay->addWidget(view_fft_, 1);

  auto* out = new QGroupBox("3. Nilai Hasil (Output)");
  auto* outLay = new QHBoxLayout(out);
  lbl_peak_f_ = new QLabel("Frekuensi Puncak: - Hz");
  lbl_peak_a_ = new QLabel("Amplitudo Puncak: -");
  QFont bold = lbl_peak_f_->font();
  bold.setBold(true);
  lbl_peak_f_->setFont(bold);
  lbl_peak_a_->setFont(bold);
  outLay->addWidget(lbl_peak_f_);
  outLay->addWidget(lbl_peak_a_);
  lay->addWidget(out);

  timer_ = new QTimer(this);
  timer_->setTimerType(Qt::CoarseTimer);
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
  const QString prev = confirmed_label_;
  cmb_device_->clear();
  int prefer = -1;
  const auto devices = AudioCapture::listInputDevices(true);
  for (int i = 0; i < static_cast<int>(devices.size()); ++i) {
    const auto& [idx, label] = devices[static_cast<size_t>(i)];
    const QString q = QString::fromStdString(label);
    cmb_device_->addItem(q, idx);
    const QString low = q.toLower();
    if (prefer < 0 && (low.contains("umc") || low.contains("usb"))) prefer = i;
  }
  if (cmb_device_->count() > 0)
    cmb_device_->setCurrentIndex(prefer >= 0 ? prefer : 0);
  if (!prev.isEmpty()) {
    bool found = false;
    for (int i = 0; i < cmb_device_->count(); ++i) {
      if (cmb_device_->itemText(i) == prev) {
        found = true;
        cmb_device_->setCurrentIndex(i);
        break;
      }
    }
    if (!found) {
      mic_connected_ = false;
      confirmed_device_ = -1;
      confirmed_label_.clear();
      stopAudio();
      if (lbl_mic_) {
        lbl_mic_->setText("● Mic belum aktif");
        lbl_mic_->setStyleSheet("color: red;");
      }
    }
  }
}

void FftWidget::connectMic() {
  if (!cmb_device_ || cmb_device_->count() == 0) {
    QMessageBox::warning(this, "Mic belum dipilih",
                         "Pilih device mic dari dropdown terlebih dahulu.");
    return;
  }
  confirmed_device_ = cmb_device_->currentData().toInt();
  confirmed_label_ = cmb_device_->currentText();
  mic_connected_ = true;
  auto [ok, msg] = ensureAudioStarted();
  if (!ok) {
    QMessageBox::warning(this, "Audio", msg);
    mic_connected_ = false;
    return;
  }
  lbl_mic_->setText("● Mic aktif");
  lbl_mic_->setStyleSheet("color: green;");
}

std::pair<bool, QString> FftWidget::ensureAudioStarted() {
  if (audio_.isRunning()) {
    if (plot_active_ && !timer_->isActive())
      timer_->start(FFT_UPDATE_INTERVAL_MS);
    return {true, "Audio sudah aktif."};
  }
  if (!mic_connected_ || confirmed_device_ < 0)
    return {false, "Mic belum terhubung. Klik Connect Mic dulu."};
  auto [ok, msg] = audio_.start(confirmed_device_, AUDIO_SAMPLERATE, 1);
  if (ok && plot_active_) timer_->start(FFT_UPDATE_INTERVAL_MS);
  if (ok && lbl_mic_) {
    lbl_mic_->setText("● Mic aktif");
    lbl_mic_->setStyleSheet("color: green;");
  }
  return {ok, QString::fromStdString(msg)};
}

void FftWidget::stopAudio() {
  timer_->stop();
  audio_.stop();
}

void FftWidget::setPlotActive(bool active) {
  plot_active_ = active;
  if (!active) {
    timer_->stop();
    return;
  }
  if (audio_.isRunning() && !timer_->isActive())
    timer_->start(FFT_UPDATE_INTERVAL_MS);
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

void FftWidget::restoreFreqEntry() {
  if (!entry_freq_) return;
  const double f = applied_fmin_;
  if (std::abs(f - std::round(f)) < 1e-9)
    entry_freq_->setText(QString::number(static_cast<int>(std::lround(f))));
  else
    entry_freq_->setText(QString::number(f));
}

void FftWidget::setFrekuensi() {
  if (btn_set_freq_ && !btn_set_freq_->isEnabled()) return;
  bool ok = false;
  const double nilai =
      entry_freq_->text().trimmed().replace(',', '.').toDouble(&ok);
  if (!ok || nilai <= 0 || nilai > FFT_MAX_FREQ_HZ) {
    QMessageBox::warning(this, "Peringatan Frekuensi",
                         "Nilai valid: > 0 dan maksimal 20000 Hz.");
    restoreFreqEntry();
    return;
  }
  applied_fmin_ = nilai;
  freq_set_ = true;
  restoreFreqEntry();
  emit frekuensiDitetapkan(nilai);
}

void FftWidget::updatePlots() {
  if (!audio_.isRunning() || !plot_active_) return;

  // Satu snapshot ringkas (bukan 2× copy 192k)
  const int n = audio_.copyLast(snap_.data(), kUiFftSamples);
  if (n <= 0) return;

  wave_pts_.clear();
  const int step_w = std::max(1, n / kMaxWavePts);
  const double inv_sr = 1.0 / audio_.samplerate();
  wave_pts_.reserve(n / step_w + 1);
  for (int i = 0; i < n; i += step_w)
    wave_pts_.append(QPointF(i * inv_sr, snap_[static_cast<size_t>(i)]));
  series_wave_->replace(wave_pts_);

  const double fmin = getFftMinHz();
  const double fmax = getFftMaxHz();
  const bool is_log = chk_log_->isChecked();

  if (is_log != (last_logscale_ == 1) || fmin != last_fmin_ || fmax != last_fmax_) {
    last_logscale_ = is_log ? 1 : 0;
    last_fmin_ = fmin;
    last_fmax_ = fmax;
    ax_x_fft_->setRange(fmin, fmax);
    ax_y_fft_->setTitleText(is_log ? "Amplitudo (dB)" : "Amplitudo");
    ax_y_fft_->setLabelFormat(is_log ? "%.0f" : "%.3f");
    axis_hold_ = 0;
  }

  audio_.computeFftInto(snap_.data(), n, fmin, fmax, &freqs_, &mag_);

  fft_pts_.clear();
  const int n_f = static_cast<int>(freqs_.size());
  const int step_f = std::max(1, n_f / kMaxFftPts);
  fft_pts_.reserve(n_f / step_f + 1);
  double ymin = 0, ymax = 0;
  bool first = true;
  for (int i = 0; i < n_f; i += step_f) {
    double y = mag_[static_cast<size_t>(i)];
    if (is_log) y = 20.0 * std::log10(std::max(y, 1e-12));
    fft_pts_.append(QPointF(freqs_[static_cast<size_t>(i)], y));
    if (first) {
      ymin = ymax = y;
      first = false;
    } else {
      ymin = std::min(ymin, y);
      ymax = std::max(ymax, y);
    }
  }
  series_fft_->replace(fft_pts_);

  if (!fft_pts_.isEmpty()) {
    double y0, y1;
    if (is_log) {
      const double margin = (ymax > ymin) ? (ymax - ymin) * 0.1 : 5.0;
      y0 = ymin - margin;
      y1 = ymax + margin;
    } else {
      y0 = 0.0;
      y1 = std::max(ymax * 1.15, 0.01);
    }
    if (axis_hold_ <= 0 || std::abs(y0 - last_ymin_) > 2.0 ||
        std::abs(y1 - last_ymax_) > 2.0) {
      ax_y_fft_->setRange(y0, y1);
      last_ymin_ = y0;
      last_ymax_ = y1;
      axis_hold_ = 6;
    } else {
      --axis_hold_;
    }
  }

  double pf = 0, pa = 0;
  if (!mag_.empty()) {
    size_t idx = 0;
    for (size_t i = 1; i < mag_.size(); ++i)
      if (mag_[i] > mag_[idx]) idx = i;
    pf = freqs_[idx];
    pa = mag_[idx];
  }
  if (label_hold_ <= 0 || std::abs(pf - last_pf_) > 1.0 ||
      std::abs(pa - last_pa_) > 1e-6) {
    lbl_peak_f_->setText(QString("Frekuensi Puncak: %1 Hz").arg(pf, 0, 'f', 1));
    lbl_peak_a_->setText(QString("Amplitudo Puncak: %1").arg(pa, 0, 'f', 6));
    last_pf_ = pf;
    last_pa_ = pa;
    label_hold_ = 3;
  } else {
    --label_hold_;
  }

  peak_pts_.clear();
  if (!freqs_.empty()) {
    const double py = is_log ? 20.0 * std::log10(std::max(pa, 1e-12)) : pa;
    peak_pts_.append(QPointF(pf, py));
  }
  series_peak_->replace(peak_pts_);
}

}  // namespace pa
