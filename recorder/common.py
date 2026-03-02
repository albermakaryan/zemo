"""
Shared utilities for video recording: writer helpers, time/name formatting, frame resize.
"""

from datetime import datetime
from pathlib import Path

import cv2

from recorder import config


def make_even(v: int) -> int:
    """Some codecs require even dimensions."""
    return max(2, v & ~1)


def create_writer(path: str, fourcc_str: str, fps: float, w: int, h: int):
    """Create VideoWriter with given FourCC; returns (writer, True) if opened else (None, False)."""
    fourcc = cv2.VideoWriter_fourcc(*fourcc_str)
    out = cv2.VideoWriter(path, fourcc, fps, (w, h))
    return (out, out.isOpened())


def timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def sanitize_email_for_filename(email: str) -> str:
    """Make email safe for use in filenames: e.g. a.b@c.edu -> a_b_at_c_edu."""
    if not email or not isinstance(email, str):
        return ""
    s = email.strip().lower()
    s = s.replace("@", "_at_")
    s = s.replace(".", "_")
    allowed = "abcdefghijklmnopqrstuvwxyz0123456789_at"
    s = "".join(c for c in s if c in allowed)
    return s or "user"


def email_filename_part(email: str) -> str:
    """Email as filename part, keeping @ and . (e.g. alber.makaryan@ysu.am). Replaces only invalid chars."""
    if not email or not isinstance(email, str):
        return "user"
    s = email.strip()
    for c in '\\/:*?"<>|':
        s = s.replace(c, "_")
    return s or "user"


def fmt_time(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    return f"{m:02d}:{s:02d}"


def resize_frame(frame, w: int, h: int):
    return cv2.resize(frame, (w, h), interpolation=cv2.INTER_AREA)


def frame_to_tk(frame):
    from PIL import Image, ImageTk
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    img = Image.fromarray(rgb)
    return ImageTk.PhotoImage(img)
