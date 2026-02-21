"""
Re-exports for backward compatibility. Implementations live in:
  - recorder.common   (timestamp, fmt_time, resize_frame, frame_to_tk, …)
  - recorder.webcam_recorder (WebcamRecorder)
  - recorder.screen_recorder (ScreenRecorder)
"""

from recorder.common import (
    fmt_time,
    frame_to_tk,
    resize_frame,
    sanitize_email_for_filename,
    timestamp,
)
from recorder.screen_recorder import ScreenRecorder
from recorder.webcam_recorder import WebcamRecorder

__all__ = [
    "WebcamRecorder",
    "ScreenRecorder",
    "fmt_time",
    "frame_to_tk",
    "resize_frame",
    "timestamp",
    "sanitize_email_for_filename",
]
