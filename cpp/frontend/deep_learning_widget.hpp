#pragma once

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

 private:
  SpatialMapWidget* spatial_ = nullptr;
  QLabel* lbl_status_ = nullptr;
  QComboBox* cmb_model_ = nullptr;
  QPushButton* btn_import_ = nullptr;
  bool gray_ready_ = false;
};

}  // namespace pa
