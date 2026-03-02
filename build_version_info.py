"""
Write version_info.txt for PyInstaller from VERSION file or argument.
Run before building: python build_version_info.py [version]
If no argument, reads VERSION from project root. Version format: 1.0.0 or 1.0.0.0
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def parse_version(s: str) -> tuple:
    s = (s or "").strip().strip("\r\n")
    parts = re.sub(r"[^0-9.]", "", s).split(".") or ["0"]
    nums = [int(p) if p.isdigit() else 0 for p in parts[:4]]
    while len(nums) < 4:
        nums.append(0)
    return tuple(nums[:4])


def main():
    if len(sys.argv) >= 2:
        ver_str = sys.argv[1]
    else:
        version_file = ROOT / "VERSION"
        if not version_file.exists():
            ver_str = "0.0.0"
        else:
            ver_str = version_file.read_text(encoding="utf-8", errors="replace")
    vers = parse_version(ver_str)
    # PyInstaller version file: see https://pyinstaller.org/en/stable/usage.html#version-file-format
    content = f"""# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({vers[0]}, {vers[1]}, {vers[2]}, {vers[3]}),
    prodvers=({vers[0]}, {vers[1]}, {vers[2]}, {vers[3]}),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        "040904B0",
        [
          StringStruct("CompanyName", ""),
          StringStruct("FileDescription", "Recorder - Screen & Webcam Recorder"),
          StringStruct("FileVersion", "{vers[0]}.{vers[1]}.{vers[2]}.{vers[3]}"),
          StringStruct("InternalName", "Recorder"),
          StringStruct("LegalCopyright", ""),
          StringStruct("OriginalFilename", "Recorder.exe"),
          StringStruct("ProductName", "Recorder"),
          StringStruct("ProductVersion", "{vers[0]}.{vers[1]}.{vers[2]}.{vers[3]}")
        ]
      )
    ]),
    VarFileInfo([VarStruct("Translation", [1033, 1200])])
  ]
)
"""
    out = ROOT / "version_info.txt"
    out.write_text(content, encoding="utf-8")
    print(f"Wrote {out.name} with version {vers[0]}.{vers[1]}.{vers[2]}.{vers[3]}")


if __name__ == "__main__":
    main()
