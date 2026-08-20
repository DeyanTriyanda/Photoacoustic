#include "frontend/deep_learning_widget.hpp"

#include <QVBoxLayout>
#include <QHBoxLayout>
#include <QLabel>
#include <QComboBox>
#include <QPushButton>
#include <QGroupBox>
#include <QFileInfo>
#include <QFileDialog>
#include <QDir>
#include <QMessageBox>
#include <QCoreApplication>
#include <QPixmap>

#include "backend/deep_learning.hpp"
#include "frontend/spatial_map_widget.hpp"

namespace pa {

DeepLearningWidget::DeepLearningWidget(SpatialMapWidget* spatial, QWidget* parent)
    : QWidget(parent), spatial_(spatial) {
  auto* root = new QHBoxLayout(this);

  auto* kiri = new QVBoxLayout;
  root->addLayout(kiri);

  auto* data = new QGroupBox("1. Data Input");
  auto* dataLay = new QVBoxLayout(data);
  btn_import_ = new QPushButton("Import Citra");
  btn_import_->setEnabled(false);
  btn_folder_ = new QPushButton("Folder");
  lbl_data_ = new QLabel(
      "Belum ada data.\nImport Citra aktif setelah scan raster selesai.");
  lbl_data_->setWordWrap(true);
  lbl_data_->setStyleSheet("color:#555;");
  dataLay->addWidget(btn_import_);
  dataLay->addWidget(btn_folder_);
  dataLay->addWidget(lbl_data_);
  kiri->addWidget(data);

  auto* model = new QGroupBox("2. Model");
  auto* modelLay = new QVBoxLayout(model);
  lbl_model_ = new QLabel("Pilih model .onnx dari assets/");
  lbl_model_->setWordWrap(true);
  lbl_model_->setStyleSheet("color:#555;");
  cmb_model_ = new QComboBox;
  auto* row = new QHBoxLayout;
  auto* btn_refresh = new QPushButton("Muat Ulang");
  auto* btn_pilih = new QPushButton("Pilih Model");
  row->addWidget(btn_refresh);
  row->addWidget(btn_pilih);
  modelLay->addWidget(lbl_model_);
  modelLay->addWidget(cmb_model_);
  modelLay->addLayout(row);
  kiri->addWidget(model);

  auto* infer = new QGroupBox("3. Inferensi");
  auto* inferLay = new QVBoxLayout(infer);
  btn_infer_ = new QPushButton("Jalankan Inferensi");
  btn_infer_->setEnabled(false);
  btn_save_ = new QPushButton("Simpan Hasil PNG");
  btn_save_->setEnabled(false);
  inferLay->addWidget(btn_infer_);
  inferLay->addWidget(btn_save_);
  kiri->addWidget(infer);
  kiri->addStretch();

  auto* kanan = new QGroupBox("Pratinjau Citra");
  auto* kananLay = new QHBoxLayout(kanan);
  auto* inBox = new QVBoxLayout;
  inBox->addWidget(new QLabel("Input"));
  lbl_preview_in_ = new QLabel("—");
  lbl_preview_in_->setMinimumSize(200, 200);
  lbl_preview_in_->setAlignment(Qt::AlignCenter);
  lbl_preview_in_->setStyleSheet("background:#e8e8e8;");
  inBox->addWidget(lbl_preview_in_, 1);
  auto* outBox = new QVBoxLayout;
  outBox->addWidget(new QLabel("Output"));
  lbl_preview_out_ = new QLabel("—");
  lbl_preview_out_->setMinimumSize(200, 200);
  lbl_preview_out_->setAlignment(Qt::AlignCenter);
  lbl_preview_out_->setStyleSheet("background:#e8e8e8;");
  outBox->addWidget(lbl_preview_out_, 1);
  kananLay->addLayout(inBox, 1);
  kananLay->addLayout(outBox, 1);
  root->addWidget(kanan, 1);

  connect(btn_refresh, &QPushButton::clicked, this, &DeepLearningWidget::refreshModels);
  connect(btn_pilih, &QPushButton::clicked, this, &DeepLearningWidget::pilihModel);
  connect(btn_import_, &QPushButton::clicked, this, &DeepLearningWidget::importCitra);
  connect(btn_folder_, &QPushButton::clicked, this, &DeepLearningWidget::loadFolder);
  connect(btn_infer_, &QPushButton::clicked, this, &DeepLearningWidget::jalankanInferensi);
  connect(btn_save_, &QPushButton::clicked, this, &DeepLearningWidget::simpanHasil);
  refreshModels();
}

QString DeepLearningWidget::assetsDir() const {
  QString dir =
      QDir(QCoreApplication::applicationDirPath()).absoluteFilePath("../assets");
  if (!QDir(dir).exists())
    dir = QDir(QCoreApplication::applicationDirPath())
              .absoluteFilePath("../../assets");
  if (!QDir(dir).exists()) dir = "assets";
  return dir;
}

void DeepLearningWidget::setGrayscaleReady(bool ready) {
  gray_ready_ = ready;
  btn_import_->setEnabled(ready);
  if (!ready && input_img_.isNull()) {
    lbl_data_->setText(
        "Belum ada data.\nImport Citra aktif setelah scan raster selesai.");
  } else if (ready) {
    lbl_data_->setText("Citra grayscale siap diimpor.\nKlik Import Citra.");
  }
}

void DeepLearningWidget::refreshModels() {
  cmb_model_->clear();
  const QString dir = assetsDir();
  for (const auto& n : daftarModelDiAssets(dir.toStdString()))
    cmb_model_->addItem(QString::fromStdString(n));
  if (cmb_model_->count() == 0)
    cmb_model_->addItem("(tidak ada .onnx di assets/)");
  else
    lbl_model_->setText("Model: " + cmb_model_->currentText());
}

void DeepLearningWidget::pilihModel() {
  const QString path = QFileDialog::getOpenFileName(
      this, "Pilih Model ONNX", assetsDir(), "ONNX (*.onnx)");
  if (path.isEmpty()) return;
  const QFileInfo fi(path);
  const int idx = cmb_model_->findText(fi.fileName());
  if (idx >= 0) cmb_model_->setCurrentIndex(idx);
  else cmb_model_->addItem(fi.fileName(), path);
  lbl_model_->setText("Model: " + fi.fileName());
}

void DeepLearningWidget::showPreview() {
  if (!input_img_.isNull()) {
    lbl_preview_in_->setPixmap(QPixmap::fromImage(input_img_.scaled(
        lbl_preview_in_->size(), Qt::KeepAspectRatio, Qt::SmoothTransformation)));
  }
  if (!output_img_.isNull()) {
    lbl_preview_out_->setPixmap(QPixmap::fromImage(output_img_.scaled(
        lbl_preview_out_->size(), Qt::KeepAspectRatio, Qt::SmoothTransformation)));
    btn_save_->setEnabled(true);
  } else {
    lbl_preview_out_->setText("—");
    btn_save_->setEnabled(false);
  }
  btn_infer_->setEnabled(!input_img_.isNull());
}

void DeepLearningWidget::importCitra() {
  if (!gray_ready_ || !spatial_ || !spatial_->isGrayscaleComplete()) {
    QMessageBox::warning(this, "Deep Learning", "Citra grayscale belum lengkap.");
    return;
  }
  input_img_ = spatial_->grayscaleImage();
  output_img_ = QImage();
  lbl_data_->setText(QString("Imported dari scan: %1×%2")
                         .arg(input_img_.width())
                         .arg(input_img_.height()));
  showPreview();
}

void DeepLearningWidget::loadFolder() {
  const QString path = QFileDialog::getOpenFileName(
      this, "Muat Citra", QString(), "Image (*.png *.jpg *.jpeg *.bmp)");
  if (path.isEmpty()) return;
  QImage img(path);
  if (img.isNull()) {
    QMessageBox::warning(this, "Folder", "Gagal memuat citra.");
    return;
  }
  input_img_ = img.convertToFormat(QImage::Format_Grayscale8);
  output_img_ = QImage();
  lbl_data_->setText("Loaded: " + QFileInfo(path).fileName());
  showPreview();
}

void DeepLearningWidget::jalankanInferensi() {
  if (input_img_.isNull()) {
    QMessageBox::warning(this, "Inferensi", "Belum ada citra input.");
    return;
  }
  // Stub: salin input sebagai output (onnxruntime bisa ditambahkan nanti)
  output_img_ = input_img_.copy();
  lbl_model_->setText("Inferensi stub (pass-through). Model: " +
                      cmb_model_->currentText());
  showPreview();
  QMessageBox::information(
      this, "Deep Learning",
      "Inferensi C++ masih stub (hasil = salinan input).\n"
      "Integrasi onnxruntime dapat ditambahkan kemudian.\nModel: " +
          cmb_model_->currentText());
}

void DeepLearningWidget::simpanHasil() {
  if (output_img_.isNull()) return;
  const QString path = QFileDialog::getSaveFileName(
      this, "Simpan Hasil", "hasil_dl.png", "PNG (*.png)");
  if (path.isEmpty()) return;
  if (!output_img_.save(path))
    QMessageBox::warning(this, "Simpan", "Gagal menyimpan.");
}

}  // namespace pa
