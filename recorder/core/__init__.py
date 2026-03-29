"""
Core recording primitives (backend, no UI).

This package contains the core webcam/screen recorder implementations and
other non-UI logic that can be reused from both GUI and CLI tools.
"""

from .webcam import WebcamRecorderCore
from .screen import ScreenRecorderCore

__all__ = ["WebcamRecorderCore", "ScreenRecorderCore"]

