"""UI test: launch the full recorder app window."""

import sys
from pathlib import Path

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
    app = App()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(run_ui())
