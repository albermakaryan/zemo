"""
Configuration and constants for the recorder app.
"""

import sys
from pathlib import Path

# Project root: when frozen (PyInstaller exe), use the folder containing the exe
if getattr(sys, "frozen", False):
    PROJECT_ROOT = Path(sys.executable).resolve().parent
else:
    PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Recordings base folder; webcam and screen subfolders live here
RECORDINGS_DIR_NAME = "recordings"
RECORDINGS_DIR = PROJECT_ROOT / RECORDINGS_DIR_NAME
WEBCAM_SUBDIR = "webcam"
SCREEN_SUBDIR = "screen"


def get_recordings_dir() -> Path:
    """Base directory for all recordings (contains webcam/ and screen/)."""
    return RECORDINGS_DIR


def get_webcam_dir() -> Path:
    """Directory for webcam recordings."""
    return RECORDINGS_DIR / WEBCAM_SUBDIR


def get_screen_dir() -> Path:
    """Directory for screen recordings."""
    return RECORDINGS_DIR / SCREEN_SUBDIR


def ensure_recordings_dirs() -> None:
    """Create recordings base and subfolders if they don't exist."""
    RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
    (RECORDINGS_DIR / WEBCAM_SUBDIR).mkdir(parents=True, exist_ok=True)
    (RECORDINGS_DIR / SCREEN_SUBDIR).mkdir(parents=True, exist_ok=True)


# ─── UI / theme ─────────────────────────────────────────────────────────────
BG = "#0f0f0f"
BG2 = "#1a1a1a"
BG3 = "#242424"
BORDER = "#2e2e2e"
RED = "#ff3b3b"
GREEN = "#3ddc84"
MUTED = "#555555"
FG = "#e0e0e0"
FG2 = "#888888"
MONO = ("Courier New", 10)
MONO_SM = ("Courier New", 9)


def sans_font():
    import tkinter as tk
    return ("Segoe UI", 10) if getattr(tk, "TkVersion", None) else ("Helvetica", 10)


# ─── Recording ────────────────────────────────────────────────────────────────
PREVIEW_W = 400
PREVIEW_H = 225
FPS = 20.0
VIDEO_EXT = ".mp4"
# Default device indices: 0 = first/default camera, 1 = first/primary monitor (mss: 0=all, 1=primary)
CAMERA_INDEX = 0
MONITOR_INDEX = 1
# Use mp4v first (no extra DLLs). H.264 needs OpenH264 on Windows and often fails.
VIDEO_FOURCC_TRY_ORDER = ("mp4v",)
COUNTDOWN_SECONDS = 5
# Max screen frames to write per loop when catching up (avoids death spiral; more = smoother but heavier)
SCREEN_CATCHUP_FRAMES = 20

# Float button: position (top-right, a bit below top so browser close button stays reachable)
FLOAT_TOP_OFFSET = 56
# Softer colors for float button
FLOAT_START_BG = "#2a3d2a"
FLOAT_START_FG = "#a8d4a8"
FLOAT_STOP_BG = "#3d2a2a"
FLOAT_STOP_FG = "#d4a8a8"
