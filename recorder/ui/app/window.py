"""App: main recorder window. Inherits UI-building and recording-action mixins."""

import time

from PySide6 import QtCore, QtGui, QtWidgets

from recorder import config, __version__
from recorder.ui.float_button import FloatButtonWindow

from ._ui_mixin import UIMixin
from ._recording_mixin import RecordingMixin


class App(UIMixin, RecordingMixin, QtWidgets.QMainWindow):
    """Main recorder application window."""

    _calibration_finished = QtCore.Signal()

    def __init__(self, auto_mux: bool = True, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self._calibration_finished.connect(self._on_calibration_done)
        self.setWindowTitle(f"Recorder v{__version__}")
        self.setObjectName("MainWindow")
        self.setStyleSheet(
            f"""
            QMainWindow#MainWindow {{
                background-color: {config.BG};
            }}
            """
        )
        self.setWindowIcon(QtGui.QIcon())
        self.setMinimumSize(2 * config.PREVIEW_W + 96, config.PREVIEW_H + 180)

        config.ensure_recordings_dirs()
        self._recordings_base = config.get_recordings_dir()
        self._user_email = None
        self._audio_recorder = None
        self._auto_mux = bool(auto_mux)

        self._central = QtWidgets.QWidget(self)
        self.setCentralWidget(self._central)

        self._build()
        self._float_win = FloatButtonWindow(self)
        self._float_win.show()

        self._center_on_screen()
        self._start_previews()

    def closeEvent(self, event: QtGui.QCloseEvent):
        """Gracefully stop all recordings before closing the window."""
        stop_time = time.time()
        for panel in (self._webcam_panel, self._screen_panel):
            recorder = getattr(panel, "recorder", None)
            if recorder and getattr(recorder, "stop", None):
                recorder.stop(stop_time=stop_time)
        if getattr(self, "_audio_recorder", None) and self._audio_recorder.recording:
            self._audio_recorder.stop(stop_time=stop_time)
        self._join_recorders_concurrent(timeout=5.0)

        if getattr(self, "_float_win", None):
            self._float_win.close()
        super().closeEvent(event)
