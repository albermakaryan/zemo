"""
Screen & Webcam Recorder – GUI app with synced recording and floating start/stop button.
"""

from pathlib import Path


def _load_version() -> str:
    """Return app version from VERSION file, or '0.0.0' if missing."""
    try:
        root = Path(__file__).resolve().parent.parent
        ver_file = root / "VERSION"
        return ver_file.read_text(encoding="utf-8", errors="replace").strip() or "0.0.0"
    except Exception:
        return "0.0.0"


__version__ = _load_version()

from recorder.ui import App

__all__ = ["App", "__version__"]
