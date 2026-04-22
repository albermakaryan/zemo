"""
Screen & Webcam Recorder – entry point.

Install (once per machine):
  pip install -e .          # core (Windows + Linux)
  pip install -e ".[windows]"  # optional: dxcam + system audio (Windows only)

Start:
  Windows: run_recorder.bat  or  python main.py
  Linux/macOS: ./run_recorder.sh  or  python main.py
"""

import ctypes
import sys


def _check_vcredist() -> None:
    """Warn early if the VC++ 2015-2022 runtime is missing instead of crashing silently."""
    required = ["vcruntime140.dll", "msvcp140.dll"]
    missing = [dll for dll in required if not _dll_loadable(dll)]
    if not missing:
        return

    msg = (
        "This application requires the Microsoft Visual C++ Redistributable "
        "(2015-2022 x64) which is missing on this machine.\n\n"
        "Download and install it from:\n"
        "https://aka.ms/vs/17/release/vc_redist.x64.exe\n\n"
        f"Missing: {', '.join(missing)}"
    )
    ctypes.windll.user32.MessageBoxW(0, msg, "Missing Runtime — Recorder", 0x10)
    sys.exit(1)


def _dll_loadable(name: str) -> bool:
    try:
        ctypes.WinDLL(name)
        return True
    except OSError:
        return False


if sys.platform == "win32":
    _check_vcredist()

# Frozen exe (PyInstaller): subprocess cannot use ``python -c``; use ``Recorder.exe --calibrate-only``.
if __name__ == "__main__" and "--calibrate-only" in sys.argv:
    from gazer import EyeTracker

    EyeTracker.calibrate_and_create()
    raise SystemExit(0)

from PySide6 import QtWidgets


def main():
    # Auto-mux screen video with internal audio after "Stop Both".
    # Off by default; enable with CLI flag: --auto-mux
    auto_mux = "--auto-mux" in sys.argv

    from recorder.ui import App

    qt_app = QtWidgets.QApplication(sys.argv)
    win = App(auto_mux=auto_mux)
    win.show()
    try:
        sys.exit(qt_app.exec())
    except KeyboardInterrupt:
        win.close()
        sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
