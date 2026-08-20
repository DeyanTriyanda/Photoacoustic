#pragma once

#include <QImage>
#include <QWidget>

class QLabel;
class QComboBox;
class QPushButton;

namespace pa {

class SpatialMapWidget;

class DeepLearningWidget : public QWidget {
  Q_OBJECT
 public:
  explicit DeepLearningWidget(SpatialMapWidget* spatial, QWidget* parent = nullptr);
  void setGrayscaleReady(bool ready);

 private slots:
  void refreshModels();
  void importCitra();
  void loadFolder();
  void pilihModel();
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
  QComboBox* cmb_model_ = nullptr;
  QPushButton* btn_import_ = nullptr;
  QPushButton* btn_folder_ = nullptr;
  QPushButton* btn_infer_ = nullptr;
  QPushButton* btn_save_ = nullptr;
  bool gray_ready_ = false;
  QImage input_img_;
  QImage output_img_;
};

}  // namespace pa
