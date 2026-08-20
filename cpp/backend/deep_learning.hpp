#pragma once
#include <string>
#include <vector>

namespace pa {

// Stub ringan: daftar / validasi path model ONNX (integrasi onnxruntime opsional).
std::vector<std::string> daftarModelDiAssets(const std::string& assets_dir);
std::string cariModelDiAssets(const std::string& assets_dir);

}  // namespace pa
