#include "frontend/spatial_map_widget.hpp"

#include <algorithm>
#include <cmath>
#include <fstream>
#include <functional>

#include <QHBoxLayout>
#include <QVBoxLayout>
#include <QLabel>
#include <QPushButton>
#include <QScrollArea>
#include <QFileDialog>
#include <QMessageBox>
#include <QMetaObject>
#include <QPixmap>
#include <QVariant>

#include "backend/audio_capture.hpp"
#include "backend/spatial_mapping.hpp"
#include "backend/spatial_scan_recorder.hpp"
#include "backend/config.hpp"

namespace pa {

SpatialMapWidget::SpatialMapWidget(QWidget* parent) : QWidget(parent) {
  scanParams.insert("point_distance_cm", POINT_DISTANCE_CM);
  scanParams.insert("row_distance_cm", ROW_DISTANCE_CM);
  scanParams.insert("scan_step_delay_us", SCAN_STEP_DELAY_US);
  scanParams.insert("step_per_cm_x", STEP_PER_CM_X);
  scanParams.insert("break_time_ms", BREAK_TIME_MS);
  scanParams.insert("target_freq_hz", TARGET_FREQ_HZ);
  scanParams.insert("freq_tolerance_hz", DEFAULT_FREQ_TOLERANCE_HZ);

  auto* lay = new QVBoxLayout(this);
  lbl_progress_ = new QLabel("Siap scan citra 2D.");
  lbl_stats_ = new QLabel("");
  lay->addWidget(lbl_progress_);
  lay->addWidget(lbl_stats_);

  auto* tools = new QHBoxLayout;
  btn_zoom_in_ = new QPushButton("Zoom +");
  btn_zoom_out_ = new QPushButton("Zoom −");
  btn_zoom_reset_ = new QPushButton("Reset");
  btn_save_png_ = new QPushButton("Simpan Citra (PNG)");
  btn_save_csv_amp_ = new QPushButton("Simpan CSV Amp");
  btn_save_csv_gray_ = new QPushButton("Simpan CSV Gray");
  tools->addWidget(btn_zoom_in_);
  tools->addWidget(btn_zoom_out_);
  tools->addWidget(btn_zoom_reset_);
  tools->addStretch();
  tools->addWidget(btn_save_csv_amp_);
  tools->addWidget(btn_save_csv_gray_);
  tools->addWidget(btn_save_png_);
  lay->addLayout(tools);

  scroll_ = new QScrollArea;
  scroll_->setWidgetResizable(true);
  scroll_->setAlignment(Qt::AlignCenter);
  lbl_image_ = new QLabel("Citra grayscale akan muncul di sini.");
  lbl_image_->setMinimumHeight(280);
  lbl_image_->setAlignment(Qt::AlignCenter);
  lbl_image_->setStyleSheet("background:#e0e0e0;");
  scroll_->setWidget(lbl_image_);
  lay->addWidget(scroll_, 1);

  connect(btn_zoom_in_, &QPushButton::clicked, this, &SpatialMapWidget::zoomIn);
  connect(btn_zoom_out_, &QPushButton::clicked, this, &SpatialMapWidget::zoomOut);
  connect(btn_zoom_reset_, &QPushButton::clicked, this, &SpatialMapWidget::zoomReset);
  connect(btn_save_png_, &QPushButton::clicked, this, &SpatialMapWidget::savePng);
  connect(btn_save_csv_amp_, &QPushButton::clicked, this, &SpatialMapWidget::saveCsvAmp);
  connect(btn_save_csv_gray_, &QPushButton::clicked, this, &SpatialMapWidget::saveCsvGray);
}

std::pair<bool, QString> SpatialMapWidget::startCapture(AudioCapture* audio) {
  stopCapture();
  const double x = scanParams.value("x_cm", 0.0).toDouble();
  const double y = scanParams.value("y_cm", 0.0).toDouble();
  if (x <= 0 || y <= 0) return {false, "X/Y area belum valid."};

  const double target = scanParams.value("target_freq_hz").toDouble();
  recorder_ = new SpatialScanRecorder(
      audio, scanParams.value("point_distance_cm").toDouble(),
      scanParams.value("row_distance_cm").toDouble(),
      scanParams.value("scan_step_delay_us").toInt(),
      scanParams.value("step_per_cm_x").toDouble(),
      scanParams.value("break_time_ms").toInt(), target,
      scanParams.value("freq_tolerance_hz").toDouble());

  n_kolom_ = static_cast<int>(std::llround(x / POINT_DISTANCE_CM)) + 1;
  n_baris_ = static_cast<int>(std::llround(y / ROW_DISTANCE_CM)) + 1;
  const size_t n = static_cast<size_t>(n_baris_ * n_kolom_);
  captured_mask_.assign(n, 0);
  corrected_.assign(n, 0.0);
  raw_amp_.assign(n, 0.0);
  gray_vals_.assign(n, 0);
  zoom_ = 1.0;
  emit grayscaleReadyChanged(false);

  recorder_->on_point_captured = [this](int col, int row, double raw, double corr,
                                        int n_done, int n_total) {
    QMetaObject::invokeMethod(
        this, [this, col, row, raw, corr, n_done, n_total]() {
          if (row < 0 || col < 0 || row >= n_baris_ || col >= n_kolom_) return;
          const size_t idx = static_cast<size_t>(row * n_kolom_ + col);
          captured_mask_[idx] = 1;
          corrected_[idx] = corr;
          raw_amp_[idx] = raw;
          double amin = 0, amax = 0;
          gray_vals_ = amplitude_matrix_to_grayscale(
              corrected_, n_baris_, n_kolom_, &captured_mask_, &amin, &amax);
          gray_image_ = QImage(n_kolom_, n_baris_, QImage::Format_Grayscale8);
          for (int r = 0; r < n_baris_; ++r)
            for (int c = 0; c < n_kolom_; ++c) {
              const auto g =
                  gray_vals_[static_cast<size_t>(r * n_kolom_ + c)];
              gray_image_.setPixel(c, n_baris_ - 1 - r, qRgb(g, g, g));
            }
          redrawImage();
          lbl_progress_->setText(
              QString("Merekam... %1/%2 titik selesai").arg(n_done).arg(n_total));
          lbl_stats_->setText(
              QString("Objek (terkoreksi) min=%1, max=%2  |  "
                      "Amp tinggi=terang, amp rendah=gelap  |  "
                      "Titik selesai: %3/%4")
                  .arg(amin, 0, 'g', 6)
                  .arg(amax, 0, 'g', 6)
                  .arg(n_done)
                  .arg(n_total));
          if (on_progress_) on_progress_(col, row, n_done, n_total);
          if (n_done >= n_total) emit grayscaleReadyChanged(true);
        });
  };

  const QString msg =
      QString("Perekaman citra: objek %1 Hz, background hitam < %1 Hz.")
          .arg(target, 0, 'f', 0);
  recorder_->startRecording(x, y);
  return {true, msg};
}

void SpatialMapWidget::stopCapture() {
  if (recorder_) {
    recorder_->stop();
    delete recorder_;
    recorder_ = nullptr;
  }
}

void SpatialMapWidget::resyncRow(int row1_based) {
  if (recorder_) recorder_->notifyRowSync(row1_based);
}

bool SpatialMapWidget::isGrayscaleComplete() const {
  if (captured_mask_.empty()) return false;
  return std::all_of(captured_mask_.begin(), captured_mask_.end(),
                     [](std::uint8_t v) { return v != 0; });
}

void SpatialMapWidget::redrawImage() {
  if (gray_image_.isNull()) return;
  const int w = std::max(1, static_cast<int>(gray_image_.width() * 8 * zoom_));
  const int h = std::max(1, static_cast<int>(gray_image_.height() * 8 * zoom_));
  const QPixmap px = QPixmap::fromImage(
      gray_image_.scaled(w, h, Qt::KeepAspectRatio, Qt::FastTransformation));
  lbl_image_->setPixmap(px);
  lbl_image_->resize(px.size());
}

void SpatialMapWidget::zoomIn() {
  zoom_ = std::min(8.0, zoom_ * 1.25);
  redrawImage();
}
void SpatialMapWidget::zoomOut() {
  zoom_ = std::max(0.25, zoom_ / 1.25);
  redrawImage();
}
void SpatialMapWidget::zoomReset() {
  zoom_ = 1.0;
  redrawImage();
}

void SpatialMapWidget::savePng() {
  if (gray_image_.isNull()) {
    QMessageBox::warning(this, "Simpan", "Belum ada citra.");
    return;
  }
  const QString path = QFileDialog::getSaveFileName(
      this, "Simpan Citra PNG", "citra_pa.png", "PNG (*.png)");
  if (path.isEmpty()) return;
  if (!gray_image_.save(path))
    QMessageBox::warning(this, "Simpan", "Gagal menyimpan PNG.");
}

void SpatialMapWidget::saveCsvAmp() {
  if (raw_amp_.empty() || n_baris_ <= 0) {
    QMessageBox::warning(this, "Simpan", "Belum ada data amplitudo.");
    return;
  }
  const QString path = QFileDialog::getSaveFileName(
      this, "Simpan CSV Amplitudo", "amplitudo.csv", "CSV (*.csv)");
  if (path.isEmpty()) return;
  std::ofstream f(path.toStdString());
  if (!f) {
    QMessageBox::warning(this, "Simpan", "Gagal menulis file.");
    return;
  }
  for (int r = 0; r < n_baris_; ++r) {
    for (int c = 0; c < n_kolom_; ++c) {
      if (c) f << ',';
      f << raw_amp_[static_cast<size_t>(r * n_kolom_ + c)];
    }
    f << '\n';
  }
}

void SpatialMapWidget::saveCsvGray() {
  if (gray_vals_.empty() || n_baris_ <= 0) {
    QMessageBox::warning(this, "Simpan", "Belum ada data grayscale.");
    return;
  }
  const QString path = QFileDialog::getSaveFileName(
      this, "Simpan CSV Grayscale", "grayscale.csv", "CSV (*.csv)");
  if (path.isEmpty()) return;
  std::ofstream f(path.toStdString());
  if (!f) {
    QMessageBox::warning(this, "Simpan", "Gagal menulis file.");
    return;
  }
  for (int r = 0; r < n_baris_; ++r) {
    for (int c = 0; c < n_kolom_; ++c) {
      if (c) f << ',';
      f << static_cast<int>(gray_vals_[static_cast<size_t>(r * n_kolom_ + c)]);
    }
    f << '\n';
  }
}

}  // namespace pa
