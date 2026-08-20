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
#include <QOpenGLWidget>
#include <QtCharts/QChart>
#include <QtCharts/QChartView>
#include <QtCharts/QLineSeries>
#include <QtCharts/QScatterSeries>
#include <QtCharts/QValueAxis>

#include "backend/config.hpp"

namespace pa {

namespace {
constexpr int kMaxWavePts = 800;
constexpr int kMaxFftPts = 600;
}  // namespace

FftWidget::FftWidget(QWidget* parent) : QWidget(parent), audio_([](const std::string&) {}) {
  applied_fmin_ = TARGET_FREQ_HZ;
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
  auto* axYw = new QValueAxis();
  axYw->setRange(-1.05, 1.05);
  axYw->setTitleText("Amplitudo");
  chart_wave_->addAxis(axXw, Qt::AlignBottom);
  chart_wave_->addAxis(axYw, Qt::AlignLeft);
  series_wave_->attachAxis(axXw);
  series_wave_->attachAxis(axYw);
  view_wave_ = new QChartView(chart_wave_);
  setupChartAcceleration(view_wave_, series_wave_);
  lay->addWidget(view_wave_, 1);

  series_fft_ = new QLineSeries();
  series_peak_ = new QScatterSeries();
  series_peak_->setMarkerSize(9.0);
  series_peak_->setColor(Qt::red);
  series_peak_->setBorderColor(Qt::darkRed);
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
  ax_y_fft_ = new QValueAxis();
  ax_y_fft_->setRange(0, 0.01);
  ax_y_fft_->setTitleText("Amplitudo");
  chart_fft_->addAxis(ax_x_fft_, Qt::AlignBottom);
  chart_fft_->addAxis(ax_y_fft_, Qt::AlignLeft);
  series_fft_->attachAxis(ax_x_fft_);
  series_fft_->attachAxis(ax_y_fft_);
  series_peak_->attachAxis(ax_x_fft_);
  series_peak_->attachAxis(ax_y_fft_);
  view_fft_ = new QChartView(chart_fft_);
  setupChartAcceleration(view_fft_, series_fft_);
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
  timer_->setTimerType(Qt::PreciseTimer);
  connect(timer_, &QTimer::timeout, this, &FftWidget::updatePlots);
}

void FftWidget::setupChartAcceleration(QChartView* view, QLineSeries* series) {
  view->setRenderHint(QPainter::Antialiasing, false);
  view->setRubberBand(QChartView::NoRubberBand);
  // OpenGL: jauh lebih smooth daripada software raster Qt Charts
  view->setViewport(new QOpenGLWidget(view));
  series->setUseOpenGL(true);
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
                         "Pilih device mic dari dropdown terlebih dahulu, lalu klik "
                         "'Connect Mic'.");
    return;
  }
  confirmed_device_ = cmb_device_->currentData().toInt();
  confirmed_label_ = cmb_device_->currentText();
  mic_connected_ = true;
  // Langsung stream agar grafik FFT hidup & smooth tanpa menunggu Start scan
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
    if (!timer_->isActive()) timer_->start(FFT_UPDATE_INTERVAL_MS);
    return {true, "Audio sudah aktif."};
  }
  if (!mic_connected_ || confirmed_device_ < 0)
    return {false,
            "Mic belum terhubung. Pilih Device di panel Koneksi Serial lalu klik "
            "'Connect Mic' terlebih dahulu."};
  auto [ok, msg] = audio_.start(confirmed_device_, AUDIO_SAMPLERATE, 1);
  if (ok) {
    if (lbl_mic_) {
      lbl_mic_->setText("● Mic aktif");
      lbl_mic_->setStyleSheet("color: green;");
    }
    timer_->start(FFT_UPDATE_INTERVAL_MS);
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
  const QString raw = entry_freq_->text().trimmed().replace(',', '.');
  const double nilai = raw.toDouble(&ok);
  if (!ok) {
    QMessageBox::warning(this, "Peringatan Frekuensi",
                         "Isi frekuensi modulasi dengan angka.\n"
                         "Nilai valid: lebih dari 0 dan maksimal 20000 Hz.");
    restoreFreqEntry();
    return;
  }
  if (nilai <= 0) {
    QMessageBox::warning(this, "Peringatan Frekuensi",
                         "Frekuensi tidak boleh 0 atau negatif.\n"
                         "Set Modulasi dibatalkan.");
    restoreFreqEntry();
    return;
  }
  if (nilai > FFT_MAX_FREQ_HZ) {
    QMessageBox::warning(
        this, "Peringatan Frekuensi",
        QString("Frekuensi tidak boleh lebih dari %1 Hz.\nSet Modulasi dibatalkan.")
            .arg(static_cast<int>(FFT_MAX_FREQ_HZ)));
    restoreFreqEntry();
    return;
  }
  applied_fmin_ = nilai;
  freq_set_ = true;
  restoreFreqEntry();
  emit frekuensiDitetapkan(nilai);
}

void FftWidget::updatePlots() {
  if (!audio_.isRunning()) return;

  const auto wave = audio_.getWaveform();
  const int n = static_cast<int>(wave.size());
  QVector<QPointF> wave_pts;
  if (n > 0) {
    const int step = std::max(1, n / kMaxWavePts);
    wave_pts.reserve(n / step + 1);
    const double inv_sr = 1.0 / audio_.samplerate();
    for (int i = 0; i < n; i += step)
      wave_pts.append(QPointF(i * inv_sr, wave[static_cast<size_t>(i)]));
  }
  series_wave_->replace(wave_pts);

  const double fmin = getFftMinHz();
  const double fmax = getFftMaxHz();
  const bool is_log = chk_log_->isChecked();

  if (is_log != (last_logscale_ == 1) || fmin != last_fmin_ || fmax != last_fmax_) {
    last_logscale_ = is_log ? 1 : 0;
    last_fmin_ = fmin;
    last_fmax_ = fmax;
    if (ax_x_fft_) ax_x_fft_->setRange(fmin, fmax);
    if (ax_y_fft_) {
      ax_y_fft_->setTitleText(is_log ? "Amplitudo (dB)" : "Amplitudo");
      ax_y_fft_->setLabelFormat(is_log ? "%.0f" : "%.3f");
    }
    axis_hold_ = 0;
  }

  auto [freqs, mag] = audio_.getFft(fmin, fmax);
  const int n_f = static_cast<int>(freqs.size());
  const int step_f = std::max(1, n_f / kMaxFftPts);
  QVector<QPointF> fft_pts;
  fft_pts.reserve(n_f / step_f + 1);
  double ymin = 0.0, ymax = 0.0;
  bool first = true;
  for (int i = 0; i < n_f; i += step_f) {
    double y = mag[static_cast<size_t>(i)];
    if (is_log) y = 20.0 * std::log10(std::max(y, 1e-12));
    fft_pts.append(QPointF(freqs[static_cast<size_t>(i)], y));
    if (first) {
      ymin = ymax = y;
      first = false;
    } else {
      ymin = std::min(ymin, y);
      ymax = std::max(ymax, y);
    }
  }
  series_fft_->replace(fft_pts);

  // Jangan ubah Y-axis tiap frame (penyebab stutter) — update berkala / jika berubah jauh
  if (ax_y_fft_ && !fft_pts.isEmpty()) {
    double y0, y1;
    if (is_log) {
      const double margin = (ymax > ymin) ? (ymax - ymin) * 0.1 : 5.0;
      y0 = ymin - margin;
      y1 = ymax + margin;
    } else {
      y0 = 0.0;
      y1 = std::max(ymax * 1.15, 0.01);
    }
    const bool big_change =
        (std::abs(y0 - last_ymin_) > 1.0) || (std::abs(y1 - last_ymax_) > 1.0);
    if (axis_hold_ <= 0 || big_change) {
      ax_y_fft_->setRange(y0, y1);
      last_ymin_ = y0;
      last_ymax_ = y1;
      axis_hold_ = 8;  // tahan ~8 frame
    } else {
      --axis_hold_;
    }
  }

  // Peak dari data penuh (bukan yang di-decimate)
  double pf = 0.0, pa = 0.0;
  if (!mag.empty()) {
    size_t idx = 0;
    for (size_t i = 1; i < mag.size(); ++i)
      if (mag[i] > mag[idx]) idx = i;
    pf = freqs[idx];
    pa = mag[idx];
  }
  lbl_peak_f_->setText(QString("Frekuensi Puncak: %1 Hz").arg(pf, 0, 'f', 1));
  lbl_peak_a_->setText(QString("Amplitudo Puncak: %1").arg(pa, 0, 'f', 6));

  QVector<QPointF> peak_pts;
  if (!freqs.empty()) {
    const double py = is_log ? 20.0 * std::log10(std::max(pa, 1e-12)) : pa;
    peak_pts.append(QPointF(pf, py));
  }
  series_peak_->replace(peak_pts);
}

}  // namespace pa
