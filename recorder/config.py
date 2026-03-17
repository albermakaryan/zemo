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
AUDIO_SUBDIR = "audio"
DETECTION_SUBDIR = "detection"

# Separate folder for test runs (python -m tests screen/webcam/audio)
RECORDINGS_TEST_DIR_NAME = "recordings_test"
RECORDINGS_TEST_DIR = PROJECT_ROOT / RECORDINGS_TEST_DIR_NAME


def get_recordings_dir() -> Path:
    """Base directory for all recordings (contains webcam/ and screen/)."""
    return RECORDINGS_DIR


def get_webcam_dir() -> Path:
    """Directory for webcam recordings."""
    return RECORDINGS_DIR / WEBCAM_SUBDIR


def get_screen_dir() -> Path:
    """Directory for screen recordings."""
    return RECORDINGS_DIR / SCREEN_SUBDIR


def get_audio_dir() -> Path:
    """Directory for audio recordings (system/loopback)."""
    return RECORDINGS_DIR / AUDIO_SUBDIR


def get_detection_dir() -> Path:
    """Directory for emotion detection results (CSV per recording)."""
    return RECORDINGS_DIR / DETECTION_SUBDIR


def get_test_recordings_dir() -> Path:
    """Base directory for test recordings (tests module only)."""
    return RECORDINGS_TEST_DIR


def get_test_webcam_dir() -> Path:
    """Test webcam recordings."""
    return RECORDINGS_TEST_DIR / WEBCAM_SUBDIR


def get_test_screen_dir() -> Path:
    """Test screen recordings."""
    return RECORDINGS_TEST_DIR / SCREEN_SUBDIR


def get_test_audio_dir() -> Path:
    """Test audio recordings."""
    return RECORDINGS_TEST_DIR / AUDIO_SUBDIR


def ensure_test_recordings_dirs() -> None:
    """Create test recordings base and subfolders."""
    RECORDINGS_TEST_DIR.mkdir(parents=True, exist_ok=True)
    (RECORDINGS_TEST_DIR / WEBCAM_SUBDIR).mkdir(parents=True, exist_ok=True)
    (RECORDINGS_TEST_DIR / SCREEN_SUBDIR).mkdir(parents=True, exist_ok=True)
    (RECORDINGS_TEST_DIR / AUDIO_SUBDIR).mkdir(parents=True, exist_ok=True)


def ensure_recordings_dirs() -> None:
    """Create recordings base and subfolders if they don't exist."""
    RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
    (RECORDINGS_DIR / ".gitkeep").touch(exist_ok=True)
    for sub in (WEBCAM_SUBDIR, SCREEN_SUBDIR, AUDIO_SUBDIR):
        subdir = RECORDINGS_DIR / sub
        subdir.mkdir(parents=True, exist_ok=True)
        (subdir / ".gitkeep").touch(exist_ok=True)


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
FPS = 25
VIDEO_EXT = ".mp4"
# Webcam uses the camera's native resolution (often 640x480 or 720p). Screen uses full monitor
# resolution (e.g. 1920x1080), so screen recordings are usually larger. Set both below to force
# the same output size for webcam and screen (frames are resized when writing).
RECORDING_WIDTH = None  # e.g. 1920 to match screen; None = use source size
RECORDING_HEIGHT = None  # e.g. 1080; None = use source size
# Default device indices: 0 = first/default camera, 1 = first/primary monitor (mss: 0=all, 1=primary)
CAMERA_INDEX = 0
MONITOR_INDEX = 1
# Use mp4v first (no extra DLLs). H.264 needs OpenH264 on Windows and often fails.
VIDEO_FOURCC_TRY_ORDER = ("mp4v",)
COUNTDOWN_SECONDS = 5
# Max screen frames to write per loop when catching up (avoids death spiral; more = smoother but heavier)
SCREEN_CATCHUP_FRAMES = 20

# Audio (internal / system loopback)
AUDIO_SAMPLE_RATE = 44100
AUDIO_CHUNK_SIZE = 1024
AUDIO_EXT = ".wav"

# Float button: position (top-right, a bit below top so browser close button stays reachable)
FLOAT_TOP_OFFSET = 56
# Colors for float button:
# - green-ish when idle (ready to start)
# - red-ish when recording (stopping)
FLOAT_START_BG = "#2a3d2a"  # idle circle background (greenish)
FLOAT_START_FG = "#a8d4a8"  # idle icon
FLOAT_STOP_BG = "#7a1010"   # recording circle background (reddish)
FLOAT_STOP_FG = "#ffd6d6"   # recording icon
