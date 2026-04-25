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


def __getattr__(name: str):
    if name == "App":
        from recorder.ui import App
        return App
    raise AttributeError(f"module 'recorder' has no attribute {name!r}")
