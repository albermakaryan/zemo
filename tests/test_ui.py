"""UI test: launch the full recorder app window (PySide)."""

import sys
from pathlib import Path

from PySide6 import QtWidgets


if __name__ == "__main__":
    _root = Path(__file__).resolve().parent.parent
    if str(_root) not in sys.path:
        sys.path.insert(0, str(_root))


def run_ui() -> int:
    """Launch the full recorder UI. Returns 0 after window is closed."""
    from tests.test_deps import check_deps
    from recorder import config
    from recorder.ui import App

    if not check_deps(verbose=False):
        print("Install dependencies first: pip install -r requirements.txt")
        return 1
    config.ensure_recordings_dirs()
    print("Opening recorder UI. Close the window when done.")
    qt_app = QtWidgets.QApplication(sys.argv)
    win = App()
    win.show()
    code = qt_app.exec()
    return int(code)


if __name__ == "__main__":
    sys.exit(run_ui())
