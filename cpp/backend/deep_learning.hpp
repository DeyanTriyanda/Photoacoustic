#pragma once
#include <string>
#include <vector>

namespace pa {

// Cari folder assets/ (build/../assets, CWD/assets, dll.)
std::string resolveAssetsDir();

// Daftar basename *.onnx di assets/
std::vector<std::string> daftarModelDiAssets(const std::string& assets_dir);

// Model default: Real-ESRGAN-x4plus.onnx → x2plus → Real-ESRGAN* → onnx pertama
// Return path absolut, atau string kosong jika tidak ada.
std::string cariModelDiAssets(const std::string& assets_dir = {});

// Path ikon: LogoPAI.png / logoPAI.png / logo.png
std::string cariLogoDiAssets(const std::string& assets_dir = {});

}  // namespace pa
