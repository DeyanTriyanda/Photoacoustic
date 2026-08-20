#include "frontend/spatial_map_widget.hpp"

#include <algorithm>
#include <cmath>
#include <functional>

#include <QVBoxLayout>
#include <QLabel>
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
  lbl_image_ = new QLabel("Citra grayscale akan muncul di sini.");
  lbl_image_->setMinimumHeight(280);
  lbl_image_->setAlignment(Qt::AlignCenter);
  lbl_image_->setStyleSheet("background:#e0e0e0;");
  lay->addWidget(lbl_progress_);
  lay->addWidget(lbl_stats_);
  lay->addWidget(lbl_image_, 1);
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
  captured_mask_.assign(static_cast<size_t>(n_baris_ * n_kolom_), 0);
  corrected_.assign(static_cast<size_t>(n_baris_ * n_kolom_), 0.0);

  recorder_->on_point_captured = [this](int col, int row, double, double corr,
                                        int n_done, int n_total) {
    QMetaObject::invokeMethod(this, [this, col, row, corr, n_done, n_total]() {
      if (row < 0 || col < 0 || row >= n_baris_ || col >= n_kolom_) return;
      const size_t idx = static_cast<size_t>(row * n_kolom_ + col);
      captured_mask_[idx] = 1;
      corrected_[idx] = corr;
      double amin = 0, amax = 0;
      auto gray = amplitude_matrix_to_grayscale(corrected_, n_baris_, n_kolom_,
                                                &captured_mask_, &amin, &amax);
      gray_image_ = QImage(n_kolom_, n_baris_, QImage::Format_Grayscale8);
      for (int r = 0; r < n_baris_; ++r)
        for (int c = 0; c < n_kolom_; ++c)
          gray_image_.setPixel(c, n_baris_ - 1 - r,
                               qRgb(gray[static_cast<size_t>(r * n_kolom_ + c)],
                                    gray[static_cast<size_t>(r * n_kolom_ + c)],
                                    gray[static_cast<size_t>(r * n_kolom_ + c)]));
      lbl_image_->setPixmap(QPixmap::fromImage(gray_image_.scaled(
          lbl_image_->size(), Qt::KeepAspectRatio, Qt::SmoothTransformation)));
      lbl_progress_->setText(
          QString("Merekam... %1/%2 titik selesai").arg(n_done).arg(n_total));
      lbl_stats_->setText(QString("Objek min=%1 max=%2 | Amp tinggi=terang")
                              .arg(amin, 0, 'g', 6)
                              .arg(amax, 0, 'g', 6));
      if (on_progress_) on_progress_(col, row, n_done, n_total);
      if (n_done >= n_total) emit grayscaleReadyChanged(true);
    });
  };

  recorder_->startRecording(x, y);
  return {true, "Perekaman citra dimulai."};
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

}  // namespace pa
