"""Pytest fixtures for automated unit tests (see `tests/` root for manual smoke: `python -m tests …`)."""

import sys

import pytest
from PySide6 import QtWidgets


class FakeRecordingApp(QtWidgets.QWidget):
    """
    Minimal main-window stand-in for FloatButtonWindow tests: same attributes the float
    button reads, without full App (previews, mux, gaze).
    """

    def __init__(self):
        super().__init__(None)
        r_off = _FakeRecorder(recording=False)
        self._webcam_panel = _FakePanel(r_off)
        self._screen_panel = _FakePanel(r_off)
        self._recording_start_pending = False
        self.record_both_called = 0
        self.stop_both_called = 0
        self._email = "t@example.com"
        self._gaze_ok = True

    def get_recording_email(self) -> str:
        return self._email

    def record_both(self) -> None:
        self.record_both_called += 1

    def stop_both(self) -> None:
        self.stop_both_called += 1

    def _update_start_controls_enabled(self) -> None:
        pass

    def _gaze_ready_or_prompt(self) -> bool:
        return self._gaze_ok


class _FakePanel:
    def __init__(self, rec):
        self.recorder = rec


class _FakeRecorder:
    def __init__(self, *, recording: bool):
        self.recording = recording


@pytest.fixture(scope="session")
def qapp():
    """Single QApplication for all Qt unit tests (no pytest-qt required)."""
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication(sys.argv)
    return app


@pytest.fixture
def fake_recording_app(qapp):
    w = FakeRecordingApp()
    yield w
    w.close()
