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
    resize_frame,
    timestamp,
)
from recorder.core.screen import ScreenRecorderCore as ScreenRecorder
from recorder.core.webcam import WebcamRecorderCore as WebcamRecorder

__all__ = [
    "WebcamRecorder",
    "ScreenRecorder",
    "fmt_time",
    "resize_frame",
    "timestamp",
]
