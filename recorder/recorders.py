"""
Re-exports for backward compatibility.

Core implementations now live in:
  - recorder.core.webcam  (WebcamRecorderCore)
  - recorder.core.screen  (ScreenRecorderCore)
Utility helpers live in:
  - recorder.common       (timestamp, fmt_time, resize_frame, …)
"""

from recorder.common import (
    fmt_time,
    frame_to_tk,
    resize_frame,
    sanitize_email_for_filename,
    timestamp,
)
from recorder.core.screen import ScreenRecorderCore as ScreenRecorder
from recorder.core.webcam import WebcamRecorderCore as WebcamRecorder

__all__ = [
    "WebcamRecorder",
    "ScreenRecorder",
    "fmt_time",
    "frame_to_tk",
    "resize_frame",
    "timestamp",
    "sanitize_email_for_filename",
]
