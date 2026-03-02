"""
Audio recording module: internal (system/loopback) and optionally external (microphone).

Internal recording captures what is playing on the PC (e.g. online course audio)
via Windows WASAPI loopback. Requires PyAudioWPatch on Windows.
"""

from recorder.audio.internal import InternalAudioRecorder, is_loopback_available

__all__ = ["InternalAudioRecorder", "is_loopback_available"]
