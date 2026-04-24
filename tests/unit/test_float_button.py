"""Qt widget tests for the floating start/stop button (isolated from full `App`)."""

from PySide6.QtTest import QTest

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
