"""
Internal (system) audio recording: capture what is playing on the PC.

Uses Windows WASAPI loopback (PyAudioWPatch) on Windows; otherwise Linux/macOS
via PulseAudio/PipeWire or sounddevice. One workflow: backend chosen by platform
(like screen recording: dxcam vs mss).
"""

import sys

if sys.platform == "win32":
    from recorder.audio.internal_win import InternalAudioRecorder, is_loopback_available
else:
    from recorder.audio.internal_linux import (
        InternalAudioRecorder,
        is_loopback_available,
    )

__all__ = ["InternalAudioRecorder", "is_loopback_available"]
