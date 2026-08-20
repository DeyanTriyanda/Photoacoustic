#include "backend/deep_learning.hpp"

#include <cctype>
#include <filesystem>

namespace fs = std::filesystem;

namespace pa {
namespace {

bool existsDir(const fs::path& p) {
  std::error_code ec;
  return fs::is_directory(p, ec);
}

}  // namespace

std::string resolveAssetsDir() {
  std::error_code ec;
  std::vector<fs::path> kandidat;

  // CWD (sering E:\Photoacoustic saat dijalankan dari situ)
  kandidat.push_back(fs::current_path(ec) / "assets");

  // Relatif exe: build/ -> ../assets, atau exe di root -> assets
  // application path diisi dari caller Qt; di sini pakai CWD + relative umum
  kandidat.push_back(fs::path("assets"));
  kandidat.push_back(fs::path("..") / "assets");
  kandidat.push_back(fs::path("..") / ".." / "assets");

  for (const auto& p : kandidat) {
    if (existsDir(p)) return fs::weakly_canonical(p, ec).string();
  }
  // Fallback: buat relative "assets" meski belum ada (pesan error UI)
  return "assets";
}

std::vector<std::string> daftarModelDiAssets(const std::string& assets_dir) {
  std::vector<std::string> out;
  std::error_code ec;
  if (!fs::exists(assets_dir, ec)) return out;
  for (const auto& ent : fs::directory_iterator(assets_dir, ec)) {
    if (!ent.is_regular_file()) continue;
    auto ext = ent.path().extension().string();
    for (char& c : ext) c = static_cast<char>(std::tolower(static_cast<unsigned char>(c)));
    if (ext == ".onnx") out.push_back(ent.path().filename().string());
  }
  return out;
}

std::string cariModelDiAssets(const std::string& assets_dir_in) {
  const std::string assets_dir =
      assets_dir_in.empty() ? resolveAssetsDir() : assets_dir_in;
  const char* preferred[] = {
      "Real-ESRGAN-x4plus.onnx",
      "Real-ESRGAN-x2plus.onnx",
  };
  for (const char* name : preferred) {
    fs::path p = fs::path(assets_dir) / name;
    std::error_code ec;
    if (fs::is_regular_file(p, ec)) return fs::weakly_canonical(p, ec).string();
  }
  auto list = daftarModelDiAssets(assets_dir);
  for (const auto& n : list) {
    if (n.find("Real-ESRGAN") != std::string::npos)
      return (fs::path(assets_dir) / n).string();
  }
  if (!list.empty()) return (fs::path(assets_dir) / list.front()).string();
  return {};
}

std::string cariLogoDiAssets(const std::string& assets_dir_in) {
  const std::string assets_dir =
      assets_dir_in.empty() ? resolveAssetsDir() : assets_dir_in;
  const char* names[] = {"LogoPAI.png", "logoPAI.png", "logo.png"};
  for (const char* name : names) {
    fs::path p = fs::path(assets_dir) / name;
    std::error_code ec;
    if (fs::is_regular_file(p, ec)) return fs::weakly_canonical(p, ec).string();
  }
  return {};
}

}  // namespace pa
