#include "frontend/spatial_map_widget.hpp"

#include <algorithm>
#include <cmath>
#include <fstream>

#include <QHBoxLayout>
#include <QVBoxLayout>
#include <QLabel>
#include <QPushButton>
#include <QScrollArea>
#include <QSplitter>
#include <QGroupBox>
#include <QTableWidget>
#include <QTableWidgetItem>
#include <QHeaderView>
#include <QAbstractItemView>
#include <QFileDialog>
#include <QMessageBox>
#include <QMetaObject>
#include <QPixmap>
#include <QVariant>
#include <QColor>
#include <QBrush>
#include <QFont>

#include "backend/audio_capture.hpp"
#include "backend/spatial_mapping.hpp"
#include "backend/spatial_scan_recorder.hpp"
#include "backend/config.hpp"

namespace pa {
namespace {
constexpr int kCell = 48;
}  // namespace

SpatialMapWidget::SpatialMapWidget(QWidget* parent) : QWidget(parent) {
  scanParams.insert("point_distance_cm", POINT_DISTANCE_CM);
  scanParams.insert("row_distance_cm", ROW_DISTANCE_CM);
  scanParams.insert("scan_step_delay_us", SCAN_STEP_DELAY_US);
  scanParams.insert("step_per_cm_x", STEP_PER_CM_X);
  scanParams.insert("break_time_ms", BREAK_TIME_MS);
  scanParams.insert("target_freq_hz", TARGET_FREQ_HZ);
  scanParams.insert("freq_tolerance_hz", DEFAULT_FREQ_TOLERANCE_HZ);

  auto* lay = new QVBoxLayout(this);
  lbl_progress_ = new QLabel("Belum ada data scan.");
  lbl_stats_ = new QLabel("");
  lay->addWidget(lbl_progress_);
  lay->addWidget(lbl_stats_);

  auto* split_h = new QSplitter(Qt::Horizontal);
  auto* split_v = new QSplitter(Qt::Vertical);

  auto* frame1 = new QGroupBox("1. Amplitudo per Titik (nilai fisik)");
  auto* f1lay = new QVBoxLayout(frame1);
  btn_save_csv_amp_ = new QPushButton("Simpan CSV");
  btn_save_csv_amp_->setFixedWidth(100);
  auto* f1top = new QHBoxLayout;
  f1top->addStretch();
  f1top->addWidget(btn_save_csv_amp_);
  f1lay->addLayout(f1top);
  table_amp_ = new QTableWidget;
  table_amp_->setEditTriggers(QAbstractItemView::NoEditTriggers);
  table_amp_->setSelectionMode(QAbstractItemView::NoSelection);
  table_amp_->horizontalHeader()->setSectionResizeMode(QHeaderView::Fixed);
  table_amp_->verticalHeader()->setSectionResizeMode(QHeaderView::Fixed);
  table_amp_->horizontalHeader()->setDefaultSectionSize(kCell);
  table_amp_->verticalHeader()->setDefaultSectionSize(kCell);
  table_amp_->setFont(QFont("Consolas", 8));
  f1lay->addWidget(table_amp_);

  auto* frame2 = new QGroupBox("2. Matrix Grayscale (0-255)");
  auto* f2lay = new QVBoxLayout(frame2);
  btn_save_csv_gray_ = new QPushButton("Simpan CSV");
  btn_save_csv_gray_->setFixedWidth(100);
  auto* f2top = new QHBoxLayout;
  f2top->addStretch();
  f2top->addWidget(btn_save_csv_gray_);
  f2lay->addLayout(f2top);
  table_gray_ = new QTableWidget;
  table_gray_->setEditTriggers(QAbstractItemView::NoEditTriggers);
  table_gray_->setSelectionMode(QAbstractItemView::NoSelection);
  table_gray_->horizontalHeader()->setSectionResizeMode(QHeaderView::Fixed);
  table_gray_->verticalHeader()->setSectionResizeMode(QHeaderView::Fixed);
  table_gray_->horizontalHeader()->setDefaultSectionSize(kCell);
  table_gray_->verticalHeader()->setDefaultSectionSize(kCell);
  table_gray_->setFont(QFont("Consolas", 8, QFont::Bold));
  f2lay->addWidget(table_gray_);

  split_v->addWidget(frame1);
  split_v->addWidget(frame2);

  auto* frame3 = new QGroupBox("3. Citra Grayscale (Hasil Akhir)");
  auto* f3lay = new QVBoxLayout(frame3);
  scroll_img_ = new QScrollArea;
  scroll_img_->setWidgetResizable(true);
  scroll_img_->setAlignment(Qt::AlignCenter);
  lbl_image_ = new QLabel("Citra grayscale akan muncul di sini.");
  lbl_image_->setMinimumHeight(240);
  lbl_image_->setAlignment(Qt::AlignCenter);
  lbl_image_->setStyleSheet("background:#e0e0e0;");
  scroll_img_->setWidget(lbl_image_);
  f3lay->addWidget(scroll_img_, 1);
  auto* zoom = new QHBoxLayout;
  btn_zoom_out_ = new QPushButton("− Zoom Out");
  btn_zoom_in_ = new QPushButton("+ Zoom In");
  btn_zoom_reset_ = new QPushButton("Reset Zoom");
  btn_save_png_ = new QPushButton("Simpan Citra (PNG)");
  zoom->addWidget(btn_zoom_out_);
  zoom->addWidget(btn_zoom_in_);
  zoom->addWidget(btn_zoom_reset_);
  zoom->addStretch();
  zoom->addWidget(btn_save_png_);
  f3lay->addLayout(zoom);

  split_h->addWidget(split_v);
  split_h->addWidget(frame3);
  split_h->setStretchFactor(0, 1);
  split_h->setStretchFactor(1, 1);
  lay->addWidget(split_h, 1);

  connect(btn_zoom_in_, &QPushButton::clicked, this, &SpatialMapWidget::zoomIn);
  connect(btn_zoom_out_, &QPushButton::clicked, this, &SpatialMapWidget::zoomOut);
  connect(btn_zoom_reset_, &QPushButton::clicked, this, &SpatialMapWidget::zoomReset);
  connect(btn_save_png_, &QPushButton::clicked, this, &SpatialMapWidget::savePng);
  connect(btn_save_csv_amp_, &QPushButton::clicked, this, &SpatialMapWidget::saveCsvAmp);
  connect(btn_save_csv_gray_, &QPushButton::clicked, this, &SpatialMapWidget::saveCsvGray);
}

int SpatialMapWidget::tableRowForDataRow(int data_row) const {
  return n_baris_ - 1 - data_row;
}

void SpatialMapWidget::buildEmptyGrids(int n_baris, int n_kolom) {
  n_baris_ = n_baris;
  n_kolom_ = n_kolom;
  const double dx = scanParams.value("point_distance_cm").toDouble();
  const double dy = scanParams.value("row_distance_cm").toDouble();

  for (QTableWidget* t : {table_amp_, table_gray_}) {
    t->clear();
    t->setRowCount(n_baris);
    t->setColumnCount(n_kolom);
    QStringList hlabels, vlabels;
    hlabels.reserve(n_kolom);
    vlabels.reserve(n_baris);
    for (int c = 0; c < n_kolom; ++c)
      hlabels << QString::number(c * dx, 'f', 2);
    for (int r = 0; r < n_baris; ++r) {
      const int data_r = n_baris - 1 - r;
      vlabels << QString::number(data_r * dy, 'f', 2);
    }
    t->setHorizontalHeaderLabels(hlabels);
    t->setVerticalHeaderLabels(vlabels);
    for (int r = 0; r < n_baris; ++r) {
      for (int c = 0; c < n_kolom; ++c) {
        auto* item = new QTableWidgetItem("-");
        item->setTextAlignment(Qt::AlignCenter);
        item->setForeground(QBrush(QColor("#bbbbbb")));
        item->setBackground(QBrush(Qt::white));
        t->setItem(r, c, item);
      }
    }
  }
}

void SpatialMapWidget::updatePointCell(int col, int row, double raw, int gray) {
  const int tr = tableRowForDataRow(row);
  if (auto* a = table_amp_->item(tr, col)) {
    a->setText(QString::number(raw, 'g', 3));
    a->setForeground(QBrush(Qt::black));
    a->setBackground(QBrush(QColor("#fff7d6")));
  }
  if (auto* g = table_gray_->item(tr, col)) {
    g->setText(QString::number(gray));
    g->setBackground(QBrush(QColor(gray, gray, gray)));
    g->setForeground(QBrush(gray < 128 ? Qt::white : Qt::black));
  }
}

void SpatialMapWidget::refreshAllGrayCells() {
  for (int r = 0; r < n_baris_; ++r) {
    for (int c = 0; c < n_kolom_; ++c) {
      const size_t i = static_cast<size_t>(r * n_kolom_ + c);
      if (!captured_mask_[i]) continue;
      const int gv = static_cast<int>(gray_vals_[i]);
      const int tr = tableRowForDataRow(r);
      if (auto* item = table_gray_->item(tr, c)) {
        item->setText(QString::number(gv));
        item->setBackground(QBrush(QColor(gv, gv, gv)));
        item->setForeground(QBrush(gv < 128 ? Qt::white : Qt::black));
      }
    }
  }
}

void SpatialMapWidget::rebuildImageFast() {
  gray_image_ = QImage(n_kolom_, n_baris_, QImage::Format_Grayscale8);
  for (int r = 0; r < n_baris_; ++r) {
    uchar* line = gray_image_.scanLine(n_baris_ - 1 - r);
    for (int c = 0; c < n_kolom_; ++c)
      line[c] = gray_vals_[static_cast<size_t>(r * n_kolom_ + c)];
  }
  redrawImage();
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
  running_amin_ = 0;
  running_amax_ = 0;
  has_amp_range_ = false;
  buildEmptyGrids(n_baris_, n_kolom_);
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

          // Update rentang min/max inkremental O(1)
          bool range_changed = false;
          if (!has_amp_range_) {
            running_amin_ = running_amax_ = corr;
            has_amp_range_ = true;
            range_changed = true;
          } else {
            if (corr < running_amin_) {
              running_amin_ = corr;
              range_changed = true;
            }
            if (corr > running_amax_) {
              running_amax_ = corr;
              range_changed = true;
            }
          }

          double amin = 0, amax = 0;
          if (range_changed || (n_done % 8 == 0) || n_done >= n_total) {
            // Recompute penuh hanya saat range berubah / tiap 8 titik / selesai
            gray_vals_ = amplitude_matrix_to_grayscale(
                corrected_, n_baris_, n_kolom_, &captured_mask_, &amin, &amax);
            running_amin_ = amin;
            running_amax_ = amax;
            refreshAllGrayCells();
            rebuildImageFast();
          } else {
            // O(1): hitung gray lokal dari running range
            amin = running_amin_;
            amax = running_amax_;
            int g = 128;
            if (amax > amin) {
              double norm = (corr - amin) / (amax - amin);
              if (norm < 0) norm = 0;
              if (norm > 1) norm = 1;
              g = static_cast<int>(std::lround(norm * 255.0));
            } else if (amax <= 0) {
              g = 0;
            }
            gray_vals_[idx] = static_cast<std::uint8_t>(g);
            updatePointCell(col, row, raw, g);
            // Update 1 pixel di image tanpa rebuild penuh
            if (!gray_image_.isNull() && gray_image_.width() == n_kolom_ &&
                gray_image_.height() == n_baris_) {
              gray_image_.scanLine(n_baris_ - 1 - row)[col] =
                  static_cast<uchar>(g);
              redrawImage();
            } else {
              rebuildImageFast();
            }
          }

          // Selalu update sel amplitudo titik ini
          updatePointCell(col, row, raw,
                          static_cast<int>(gray_vals_[idx]));

          lbl_progress_->setText(
              QString("Merekam... %1/%2 titik selesai").arg(n_done).arg(n_total));
          lbl_stats_->setText(
              QString("Objek min=%1 max=%2 | Amp tinggi=terang | %3/%4")
                  .arg(running_amin_, 0, 'g', 6)
                  .arg(running_amax_, 0, 'g', 6)
                  .arg(n_done)
                  .arg(n_total));
          if (on_progress_) on_progress_(col, row, n_done, n_total);
          if (n_done >= n_total) emit grayscaleReadyChanged(true);
        });
  };

  const double tol = scanParams.value("freq_tolerance_hz").toDouble();
  lbl_progress_->setText("Merekam... 0 titik selesai");
  lbl_stats_->setText(
      QString("Objek: %1 Hz ± %2 Hz  |  Background hitam: < %1 Hz (plat)")
          .arg(target, 0, 'f', 0)
          .arg(tol, 0, 'f', 0));
  recorder_->startRecording(x, y);
  return {true,
          QString("Perekaman citra: objek %1 Hz, background hitam < %1 Hz.")
              .arg(target, 0, 'f', 0)};
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
  if (!path.isEmpty() && !gray_image_.save(path))
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
  if (!f) return;
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
  if (!f) return;
  for (int r = 0; r < n_baris_; ++r) {
    for (int c = 0; c < n_kolom_; ++c) {
      if (c) f << ',';
      f << static_cast<int>(gray_vals_[static_cast<size_t>(r * n_kolom_ + c)]);
    }
    f << '\n';
  }
}

}  // namespace pa
