"""
Screen & Webcam Recorder – entry point.

Install (once per machine):
  pip install -e .          # core (Windows + Linux)
  pip install -e ".[windows]"  # optional: dxcam + system audio (Windows only)

Start:
  Windows: run_recorder.bat  or  python main.py
  Linux/macOS: ./run_recorder.sh  or  python main.py
"""

import sys

from PySide6 import QtWidgets


def main():
    # Auto-mux screen video with internal audio after "Stop Both"
    # Can be disabled with CLI flag: --no-auto-mux
    auto_mux = "--no-auto-mux" not in sys.argv

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
