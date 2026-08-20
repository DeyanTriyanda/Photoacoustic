#include "frontend/deep_learning_widget.hpp"

#include <QVBoxLayout>
#include <QHBoxLayout>
#include <QLabel>
#include <QComboBox>
#include <QPushButton>
#include <QFileInfo>
#include <QDir>
#include <QMessageBox>
#include <QCoreApplication>

#include "backend/deep_learning.hpp"
#include "frontend/spatial_map_widget.hpp"

namespace pa {

DeepLearningWidget::DeepLearningWidget(SpatialMapWidget* spatial, QWidget* parent)
    : QWidget(parent), spatial_(spatial) {
  auto* lay = new QVBoxLayout(this);
  lbl_status_ = new QLabel("Citra grayscale belum siap diimpor.");
  cmb_model_ = new QComboBox;
  btn_import_ = new QPushButton("Import Citra");
  btn_import_->setEnabled(false);
  auto* row = new QHBoxLayout;
  row->addWidget(new QLabel("Model:"));
  row->addWidget(cmb_model_, 1);
  auto* btn_refresh = new QPushButton("Muat Ulang");
  row->addWidget(btn_refresh);
  lay->addWidget(lbl_status_);
  lay->addLayout(row);
  lay->addWidget(btn_import_);
  lay->addStretch();
  connect(btn_refresh, &QPushButton::clicked, this, &DeepLearningWidget::refreshModels);
  connect(btn_import_, &QPushButton::clicked, this, &DeepLearningWidget::importCitra);
  refreshModels();
}

void DeepLearningWidget::setGrayscaleReady(bool ready) {
  gray_ready_ = ready;
  btn_import_->setEnabled(ready);
  lbl_status_->setText(ready ? "Citra grayscale siap diimpor.\nKlik Import Citra."
                             : "Citra grayscale belum siap diimpor.");
}

void DeepLearningWidget::refreshModels() {
  cmb_model_->clear();
  const QString assets =
      QDir(QCoreApplication::applicationDirPath()).absoluteFilePath("../assets");
  QString dir = assets;
  if (!QDir(dir).exists())
    dir = QDir(QCoreApplication::applicationDirPath()).absoluteFilePath("../../assets");
  if (!QDir(dir).exists()) dir = "assets";
  for (const auto& n : daftarModelDiAssets(dir.toStdString()))
    cmb_model_->addItem(QString::fromStdString(n));
  if (cmb_model_->count() == 0) cmb_model_->addItem("(tidak ada .onnx di assets/)");
}

void DeepLearningWidget::importCitra() {
  if (!gray_ready_ || !spatial_ || !spatial_->isGrayscaleComplete()) {
    QMessageBox::warning(this, "Deep Learning", "Citra grayscale belum lengkap.");
    return;
  }
  QMessageBox::information(
      this, "Deep Learning",
      "Citra grayscale diimpor (C++ stub).\n"
      "Integrasi onnxruntime dapat ditambahkan kemudian.\nModel: " +
          cmb_model_->currentText());
}

}  // namespace pa
