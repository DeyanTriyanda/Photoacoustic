"""Perbarui includePath IntelliSense dengan lokasi pybind11 di mesin ini."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CFG = ROOT / ".vscode" / "c_cpp_properties.json"


def main() -> None:
    try:
        import pybind11
        include = str(Path(pybind11.get_include()))
    except Exception as e:
        print("pybind11 belum terpasang:", e)
        print("Jalankan: pip install pybind11")
        return

    data = json.loads(CFG.read_text(encoding="utf-8"))
    for conf in data.get("configurations", []):
        paths = conf.setdefault("includePath", [])
        if include not in paths:
            paths.insert(0, include)
        print(f"[{conf.get('name')}] + {include}")
    CFG.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print("Selesai. Di VS Code: Ctrl+Shift+P → 'C/C++: Select a Configuration...' → Win32")
    print("lalu 'C/C++: Reset IntelliSense Database'")


if __name__ == "__main__":
    main()
