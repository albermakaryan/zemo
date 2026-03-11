"""
Audio recording module: internal (system/loopback) capture.

Internal recording captures what is playing on the PC (e.g. online course audio)
via Windows WASAPI loopback or Linux PulseAudio/PipeWire monitor. Backend is
chosen by platform automatically.
"""

from recorder.audio.internal import InternalAudioRecorder, is_loopback_available

__all__ = ["InternalAudioRecorder", "is_loopback_available"]
