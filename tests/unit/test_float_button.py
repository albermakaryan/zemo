"""Qt widget tests for the floating start/stop button (isolated from full `App`)."""

from unittest.mock import MagicMock, patch

import pytest
from PySide6 import QtWidgets
from PySide6.QtTest import QTest

import recorder.ui.float_button as float_btn
from recorder import config
from recorder.ui.float_button import FloatButtonWindow


def _pump_and_close(qapp, float_win):
    float_win.close()
    for _ in range(20):
        qapp.processEvents()


def test_float_button_shows_with_fake_app(qapp, fake_recording_app):
    float_win = FloatButtonWindow(fake_recording_app)
    try:
        float_win.show()
        QTest.qWait(150)
        qapp.processEvents()
        assert float_win.isVisible()
        assert float_win.windowTitle() == "Rec"
        assert float_win.width() == FloatButtonWindow.SIZE + 8
    finally:
        _pump_and_close(qapp, float_win)


def test_float_button_reflects_recording_state(qapp, fake_recording_app):
    float_win = FloatButtonWindow(fake_recording_app)
    try:
        float_win.show()
        QTest.qWait(50)
        qapp.processEvents()
        assert not fake_recording_app._webcam_panel.recorder.recording
        fake_recording_app._webcam_panel.recorder.recording = True
        float_win._update_ui()
        assert float_win.isVisible()
    finally:
        _pump_and_close(qapp, float_win)


def test_float_button_is_recording_true_if_screen_only(qapp, fake_recording_app):
    float_win = FloatButtonWindow(fake_recording_app)
    try:
        fake_recording_app._webcam_panel.recorder.recording = False
        fake_recording_app._screen_panel.recorder.recording = True
        assert float_win._is_recording() is True
    finally:
        _pump_and_close(qapp, float_win)


def test_float_button_place_topright_when_no_primary_screen(
    qapp, fake_recording_app, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(
        "recorder.ui.float_button.QtWidgets.QApplication.primaryScreen", lambda: None
    )
    float_win = FloatButtonWindow(fake_recording_app)
    try:
        assert float_win.x() == 8
        assert float_win.y() == config.FLOAT_TOP_OFFSET
    finally:
        _pump_and_close(qapp, float_win)


def test_on_clicked_noop_when_start_pending(
    qapp, fake_recording_app, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(float_btn.config, "COUNTDOWN_SECONDS", 1)
    float_win = FloatButtonWindow(fake_recording_app)
    try:
        fake_recording_app._recording_start_pending = True
        float_win._on_clicked()
        assert fake_recording_app.record_both_called == 0
    finally:
        _pump_and_close(qapp, float_win)


def test_on_clicked_noop_without_email(
    qapp, fake_recording_app, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(float_btn.config, "COUNTDOWN_SECONDS", 1)
    float_win = FloatButtonWindow(fake_recording_app)
    try:
        fake_recording_app._email = ""
        float_win._on_clicked()
        assert fake_recording_app.record_both_called == 0
    finally:
        _pump_and_close(qapp, float_win)


def test_on_clicked_noop_when_gaze_blocked(
    qapp, fake_recording_app, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(float_btn.config, "COUNTDOWN_SECONDS", 1)
    float_win = FloatButtonWindow(fake_recording_app)
    try:
        fake_recording_app._gaze_ok = False
        float_win._on_clicked()
        assert fake_recording_app.record_both_called == 0
    finally:
        _pump_and_close(qapp, float_win)


def test_on_clicked_starts_countdown_with_valid_email(
    qapp, fake_recording_app, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(float_btn.config, "COUNTDOWN_SECONDS", 3)
    float_win = FloatButtonWindow(fake_recording_app)
    try:
        float_win._on_clicked()
        assert float_win._countdown_remaining == 3
        assert float_win._countdown_timer.isActive()
    finally:
        _pump_and_close(qapp, float_win)


def test_countdown_tick_invokes_record_both_at_zero(qapp, fake_recording_app):
    float_win = FloatButtonWindow(fake_recording_app)
    try:
        float_win._countdown_remaining = 1
        float_win._countdown_tick()
        assert fake_recording_app.record_both_called == 1
        assert float_win._countdown_remaining == 0
    finally:
        _pump_and_close(qapp, float_win)


def test_countdown_tick_decrements_without_firing(
    qapp, fake_recording_app, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(float_btn.config, "COUNTDOWN_SECONDS", 5)
    float_win = FloatButtonWindow(fake_recording_app)
    try:
        float_win._countdown_remaining = 3
        float_win._countdown_tick()
        assert fake_recording_app.record_both_called == 0
        assert float_win._countdown_remaining == 2
    finally:
        _pump_and_close(qapp, float_win)


def _patched_message_box_class_for_dialog(mock_dlg: MagicMock) -> MagicMock:
    """
    Stand-in for `QMessageBox` that keeps the real `StandardButton` enum. A plain
    `MagicMock` would replace `StandardButton`, so the app's `exec() == …Yes` check
    could never pass.
    """
    m = MagicMock()
    m.StandardButton = QtWidgets.QMessageBox.StandardButton
    m.return_value = mock_dlg
    return m


def test_on_clicked_stop_delegates_when_user_confirms_yes(qapp, fake_recording_app):
    fake_recording_app._webcam_panel.recorder.recording = True
    float_win = FloatButtonWindow(fake_recording_app)
    try:
        mock_dlg = MagicMock()
        mock_dlg.exec.return_value = QtWidgets.QMessageBox.StandardButton.Yes
        mbox = _patched_message_box_class_for_dialog(mock_dlg)
        with patch.object(float_btn.QtWidgets, "QMessageBox", mbox):
            float_win._on_clicked()
        assert fake_recording_app.stop_both_called == 1
    finally:
        _pump_and_close(qapp, float_win)


def test_on_clicked_stop_canceled_when_user_declines(qapp, fake_recording_app):
    fake_recording_app._webcam_panel.recorder.recording = True
    float_win = FloatButtonWindow(fake_recording_app)
    try:
        mock_dlg = MagicMock()
        mock_dlg.exec.return_value = QtWidgets.QMessageBox.StandardButton.No
        mbox = _patched_message_box_class_for_dialog(mock_dlg)
        with patch.object(float_btn.QtWidgets, "QMessageBox", mbox):
            float_win._on_clicked()
        assert fake_recording_app.stop_both_called == 0
    finally:
        _pump_and_close(qapp, float_win)


def test_paint_path_countdown_and_pending(qapp, fake_recording_app):
    float_win = FloatButtonWindow(fake_recording_app)
    try:
        float_win._countdown_remaining = 2
        float_win._update_ui()
        assert float_win._canvas.icon().isNull() is False
        float_win._countdown_remaining = 0
        fake_recording_app._recording_start_pending = True
        float_win._update_ui()
        assert float_win._canvas.icon().isNull() is False
    finally:
        _pump_and_close(qapp, float_win)
