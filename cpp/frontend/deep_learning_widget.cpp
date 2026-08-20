#include "frontend/deep_learning_widget.hpp"

#include <QVBoxLayout>
#include <QHBoxLayout>
#include <QLabel>
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

  // Model auto dari assets/ — tanpa combo / Pilih Model
  auto* model = new QGroupBox("2. Model (otomatis dari assets/)");
  auto* modelLay = new QVBoxLayout(model);
  lbl_model_ = new QLabel("Memuat model default...");
  lbl_model_->setWordWrap(true);
  lbl_model_->setStyleSheet("color:#555;");
  btn_reload_model_ = new QPushButton("Muat Ulang");
  modelLay->addWidget(lbl_model_);
  modelLay->addWidget(btn_reload_model_);
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

  connect(btn_reload_model_, &QPushButton::clicked, this,
          &DeepLearningWidget::muatModelDefault);
  connect(btn_import_, &QPushButton::clicked, this, &DeepLearningWidget::importCitra);
  connect(btn_folder_, &QPushButton::clicked, this, &DeepLearningWidget::loadFolder);
  connect(btn_infer_, &QPushButton::clicked, this, &DeepLearningWidget::jalankanInferensi);
  connect(btn_save_, &QPushButton::clicked, this, &DeepLearningWidget::simpanHasil);

  muatModelDefault();
}

QString DeepLearningWidget::assetsDir() const {
  const QString app = QCoreApplication::applicationDirPath();
  const QStringList kandidat = {
      QDir(app).absoluteFilePath("../assets"),
      QDir(app).absoluteFilePath("../../assets"),
      QDir(app).absoluteFilePath("assets"),
      QDir::current().absoluteFilePath("assets"),
      QString::fromStdString(resolveAssetsDir()),
  };
  for (const QString& d : kandidat) {
    if (QDir(d).exists()) return QDir(d).absolutePath();
  }
  return QDir::current().absoluteFilePath("assets");
}

void DeepLearningWidget::muatModelDefault() {
  const QString dir = assetsDir();
  // Prefer path absolut dari backend (x4plus → x2plus)
  const std::string found = cariModelDiAssets(dir.toStdString());
  if (found.empty()) {
    model_path_.clear();
    lbl_model_->setStyleSheet("color:#a00;");
    lbl_model_->setText(
        QString("Model tidak ditemukan di:\n%1\n\n"
                "Simpan file:\n"
                "  Real-ESRGAN-x4plus.onnx\n"
                "(atau Real-ESRGAN-x2plus.onnx)\n"
                "ke folder assets/, lalu klik Muat Ulang.")
            .arg(dir));
    return;
  }
  model_path_ = QString::fromStdString(found);
  const QFileInfo fi(model_path_);
  lbl_model_->setStyleSheet("color:#006600;");
  lbl_model_->setText(
      QString("Model default (otomatis):\n%1\n%2")
          .arg(fi.fileName())
          .arg(fi.absolutePath()));
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
  btn_infer_->setEnabled(!input_img_.isNull() && hasModel());
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
  if (!hasModel()) {
    QMessageBox::warning(
        this, "Model",
        "Model belum tersedia.\nLetakkan Real-ESRGAN-x4plus.onnx di folder assets/.");
    return;
  }
  // Stub: pass-through hingga onnxruntime diintegrasikan
  output_img_ = input_img_.copy();
  showPreview();
  QMessageBox::information(
      this, "Deep Learning",
      QString("Model terdeteksi: %1\n\n"
              "Inferensi ONNX runtime belum terhubung di build ini "
              "(hasil sementara = salinan input).\n"
              "File model siap di assets/.")
          .arg(QFileInfo(model_path_).fileName()));
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
