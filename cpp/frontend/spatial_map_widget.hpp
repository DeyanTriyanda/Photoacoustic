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

 private:
  std::function<void(int, int, int, int)> on_progress_;
  QLabel* lbl_progress_ = nullptr;
  QLabel* lbl_stats_ = nullptr;
  QLabel* lbl_image_ = nullptr;
  QImage gray_image_;
  SpatialScanRecorder* recorder_ = nullptr;
  int n_baris_ = 0;
  int n_kolom_ = 0;
  std::vector<std::uint8_t> captured_mask_;
  std::vector<double> corrected_;
};

}  // namespace pa
