#include "backend/deep_learning.hpp"

#include <cctype>
#include <filesystem>

namespace fs = std::filesystem;

namespace pa {

std::vector<std::string> daftarModelDiAssets(const std::string& assets_dir) {
  std::vector<std::string> out;
  std::error_code ec;
  if (!fs::exists(assets_dir, ec)) return out;
  for (const auto& ent : fs::directory_iterator(assets_dir, ec)) {
    if (!ent.is_regular_file()) continue;
    auto ext = ent.path().extension().string();
    for (char& c : ext) c = static_cast<char>(std::tolower(c));
    if (ext == ".onnx") out.push_back(ent.path().filename().string());
  }
  return out;
}

std::string cariModelDiAssets(const std::string& assets_dir) {
  auto list = daftarModelDiAssets(assets_dir);
  if (list.empty()) return {};
  for (const auto& n : list) {
    if (n.find("Real-ESRGAN") != std::string::npos) return n;
  }
  return list.front();
}

}  // namespace pa
