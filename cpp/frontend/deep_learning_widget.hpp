#pragma once

#include <QImage>
#include <QString>
#include <QWidget>

class QLabel;
class QPushButton;

namespace pa {

class SpatialMapWidget;

class DeepLearningWidget : public QWidget {
  Q_OBJECT
 public:
  explicit DeepLearningWidget(SpatialMapWidget* spatial, QWidget* parent = nullptr);
  void setGrayscaleReady(bool ready);
  QString modelPath() const { return model_path_; }
  bool hasModel() const { return !model_path_.isEmpty(); }

 private slots:
  void muatModelDefault();
  void importCitra();
  void loadFolder();
  void jalankanInferensi();
  void simpanHasil();

 private:
  void showPreview();
  QString assetsDir() const;

  SpatialMapWidget* spatial_ = nullptr;
  QLabel* lbl_data_ = nullptr;
  QLabel* lbl_model_ = nullptr;
  QLabel* lbl_preview_in_ = nullptr;
  QLabel* lbl_preview_out_ = nullptr;
  QPushButton* btn_import_ = nullptr;
  QPushButton* btn_folder_ = nullptr;
  QPushButton* btn_infer_ = nullptr;
  QPushButton* btn_save_ = nullptr;
  QPushButton* btn_reload_model_ = nullptr;
  bool gray_ready_ = false;
  QString model_path_;
  QImage input_img_;
  QImage output_img_;
};

}  // namespace pa
