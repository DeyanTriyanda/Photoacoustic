#pragma once

#include <cstdint>
#include <functional>
#include <utility>
#include <vector>

#include <QHash>
#include <QImage>
#include <QString>
#include <QVariant>
#include <QWidget>

class QLabel;
class QPushButton;
class QTableWidget;
class QScrollArea;
class QSplitter;

namespace pa {

class AudioCapture;
class SpatialScanRecorder;

class SpatialMapWidget : public QWidget {
  Q_OBJECT
 public:
  explicit SpatialMapWidget(QWidget* parent = nullptr);

  QHash<QString, QVariant> scanParams;
  void setProgressCallback(std::function<void(int, int, int, int)> cb) {
    on_progress_ = std::move(cb);
  }

  std::pair<bool, QString> startCapture(AudioCapture* audio);
  void stopCapture();
  void resyncRow(int row1_based);
  bool isGrayscaleComplete() const;
  QImage grayscaleImage() const { return gray_image_; }

 signals:
  void grayscaleReadyChanged(bool ready);

 private slots:
  void zoomIn();
  void zoomOut();
  void zoomReset();
  void savePng();
  void saveCsvAmp();
  void saveCsvGray();

 private:
  void buildEmptyGrids(int n_baris, int n_kolom);
  void updatePointCell(int col, int row, double raw, int gray);
  void redrawImage();
  int tableRowForDataRow(int data_row) const;

  std::function<void(int, int, int, int)> on_progress_;
  QLabel* lbl_progress_ = nullptr;
  QLabel* lbl_stats_ = nullptr;
  QTableWidget* table_amp_ = nullptr;
  QTableWidget* table_gray_ = nullptr;
  QLabel* lbl_image_ = nullptr;
  QScrollArea* scroll_img_ = nullptr;
  QPushButton* btn_zoom_in_ = nullptr;
  QPushButton* btn_zoom_out_ = nullptr;
  QPushButton* btn_zoom_reset_ = nullptr;
  QPushButton* btn_save_png_ = nullptr;
  QPushButton* btn_save_csv_amp_ = nullptr;
  QPushButton* btn_save_csv_gray_ = nullptr;
  QImage gray_image_;
  SpatialScanRecorder* recorder_ = nullptr;
  int n_baris_ = 0;
  int n_kolom_ = 0;
  double zoom_ = 1.0;
  std::vector<std::uint8_t> captured_mask_;
  std::vector<double> corrected_;
  std::vector<double> raw_amp_;
  std::vector<std::uint8_t> gray_vals_;
};

}  // namespace pa
