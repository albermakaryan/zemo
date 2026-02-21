"""
UI package: main app, panels, floating button, dialogs.
Recording logic lives in recorder.webcam_recorder / recorder.screen_recorder.
"""

from recorder.ui.app import App
from recorder.ui.dialogs import ask_university_email
from recorder.ui.float_button import FloatButtonWindow
from recorder.ui.panels import RecorderPanel

__all__ = ["App", "RecorderPanel", "FloatButtonWindow", "ask_university_email"]
