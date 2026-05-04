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


def email_filename_part(email: str) -> str:
    """Email as filename part, keeping @ and . (e.g. alber.makaryan@ysu.am). Replaces only invalid chars."""
    if not email or not isinstance(email, str):
        return "user"
    s = email.strip()
    for c in '\\/:*?"<>|':
        s = s.replace(c, "_")
    return s or "user"


def unique_name_with_suffix(directory: Path, base: str, tail: str) -> Path:
    """
    Return a Path like:
      base{tail}
      base_1{tail}
      base_2{tail}
    choosing the first that does NOT exist.

    If base already ends with _N (numeric), we increment N:
      base_3{tail} -> base_4{tail}, etc.
    """
    directory.mkdir(parents=True, exist_ok=True)
    name_part = base or "user"
    while True:
        candidate = directory / f"{name_part}{tail}"
        if not candidate.exists():
            return candidate
        if "_" in name_part and name_part.rsplit("_", 1)[-1].isdigit():
            prefix, num = name_part.rsplit("_", 1)
            name_part = f"{prefix}_{int(num) + 1}"
        else:
            name_part = f"{name_part}_1"


def fmt_time(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    return f"{m:02d}:{s:02d}"


def resize_frame(frame, w: int, h: int):
    return cv2.resize(frame, (w, h), interpolation=cv2.INTER_AREA)


