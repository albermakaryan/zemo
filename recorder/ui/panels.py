"""Recorder panel (PyQt): preview, controls, and file info for one source."""

from pathlib import Path

import cv2
from PySide6 import QtCore, QtGui, QtWidgets

from recorder import config
from recorder.recorders import fmt_time


def _frame_to_qpixmap(frame) -> QtGui.QPixmap:
    """Convert a BGR OpenCV frame to a QPixmap."""
    try:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        bytes_per_line = ch * w
        image = QtGui.QImage(
            rgb.data, w, h, bytes_per_line, QtGui.QImage.Format.Format_RGB888
        )
        return QtGui.QPixmap.fromImage(image)
    except Exception:
        return QtGui.QPixmap()


class RecorderPanel(QtWidgets.QFrame):
    """One panel (Webcam or Screen) with preview, controls, and file info."""

    # Signals so worker threads (recorders) can update UI safely
    frame_received = QtCore.Signal(object, float)  # frame (numpy array), elapsed seconds
    status_changed = QtCore.Signal(str, str)  # state, message
    recording_done = QtCore.Signal(str)  # filename

    def __init__(self, parent, app, title, recorder_cls, subfolder, **kwargs):
        super().__init__(parent, **kwargs)
        self.setObjectName(f"RecorderPanel_{title}")
        self.setStyleSheet(
            f"""
            QFrame#RecorderPanel_{title} {{
                background-color: {config.BG2};
                border: 1px solid {config.BORDER};
            }}
            """
        )
        self._app = app
        self.title_str = title
        self.recorder_cls = recorder_cls
        self.subfolder = subfolder
        self.recorder = None
        self._last_file = ""

        # Connect signals to UI-handling slots (run in main thread)
        self.frame_received.connect(self._handle_frame)
        self.status_changed.connect(self._handle_status)
        self.recording_done.connect(self._handle_done)

        self._build()

    def _effective_save_dir(self) -> Path:
        base = Path(self._app._recordings_base)
        return base / self.subfolder

    def _build(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QtWidgets.QFrame(self)
        header.setStyleSheet(
            f"background-color: {config.BG3}; border: none; color: {config.FG};"
        )
        header_layout = QtWidgets.QHBoxLayout(header)
        header_layout.setContentsMargins(14, 4, 14, 4)

        title_lbl = QtWidgets.QLabel(self.title_str.upper(), header)
        mono_font = QtGui.QFont("Courier New", 10)
        title_lbl.setFont(mono_font)
        title_lbl.setStyleSheet(f"color: {config.FG2};")
        header_layout.addWidget(title_lbl, alignment=QtCore.Qt.AlignmentFlag.AlignLeft)

        self._status_dot = QtWidgets.QLabel("●", header)
        self._status_dot.setFont(mono_font)
        self._status_dot.setStyleSheet(f"color: {config.MUTED};")

        self._timer_lbl = QtWidgets.QLabel("00:00", header)
        sm_font = QtGui.QFont("Courier New", 9)
        self._timer_lbl.setFont(sm_font)
        self._timer_lbl.setStyleSheet(f"color: {config.MUTED};")

        header_layout.addWidget(self._timer_lbl, alignment=QtCore.Qt.AlignmentFlag.AlignRight)
        header_layout.addWidget(self._status_dot, alignment=QtCore.Qt.AlignmentFlag.AlignRight)

        layout.addWidget(header)

        self._preview_lbl = QtWidgets.QLabel(self)
        self._preview_lbl.setFixedSize(config.PREVIEW_W, config.PREVIEW_H)
        self._preview_lbl.setStyleSheet("background-color: #050505;")
        self._preview_lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._draw_placeholder()
        layout.addWidget(self._preview_lbl)

        self._file_lbl = QtWidgets.QLabel("No recording yet", self)
        self._file_lbl.setFont(sm_font)
        self._file_lbl.setStyleSheet(
            f"background-color: {config.BG2}; color: {config.MUTED}; padding: 6px 14px;"
        )
        self._file_lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self._file_lbl)

        sep = QtWidgets.QFrame(self)
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background-color: {config.BORDER};")
        layout.addWidget(sep)

        ctrl = QtWidgets.QFrame(self)
        ctrl.setStyleSheet(f"background-color: {config.BG2};")
        ctrl_layout = QtWidgets.QHBoxLayout(ctrl)
        ctrl_layout.setContentsMargins(14, 12, 14, 12)

        sans_font = QtGui.QFont("Segoe UI", 10)

        self._btn_record = QtWidgets.QPushButton("⏺  Start Recording", ctrl)
        self._btn_record.setFont(sans_font)
        self._btn_record.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
        # Do not allow keyboard focus, so Space/Enter cannot trigger recording.
        self._btn_record.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        self._btn_record.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {config.RED};
                color: white;
                border: none;
                padding: 8px 14px;
            }}
            QPushButton:hover {{
                background-color: #ff5555;
            }}
            """
        )
        self._btn_record.clicked.connect(self._toggle_recording)
        ctrl_layout.addWidget(self._btn_record, alignment=QtCore.Qt.AlignmentFlag.AlignLeft)

        self._btn_folder = QtWidgets.QPushButton("📁", ctrl)
        self._btn_folder.setFont(sans_font)
        self._btn_folder.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
        self._btn_folder.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {config.BG3};
                color: {config.FG2};
                border: none;
                padding: 8px 10px;
            }}
            QPushButton:hover {{
                background-color: {config.BORDER};
                color: {config.FG};
            }}
            """
        )
        self._btn_folder.clicked.connect(self._choose_folder)
        ctrl_layout.addWidget(self._btn_folder)

        ctrl_layout.addStretch(1)

        self._btn_open = QtWidgets.QPushButton("▶  Play", ctrl)
        self._btn_open.setFont(sans_font)
        self._btn_open.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
        self._btn_open.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {config.BG3};
                color: {config.FG2};
                border: none;
                padding: 8px 14px;
            }}
            QPushButton:hover:enabled {{
                background-color: {config.BORDER};
                color: {config.FG};
            }}
            QPushButton:disabled {{
                color: {config.MUTED};
            }}
            """
        )
        self._btn_open.setEnabled(False)
        self._btn_open.clicked.connect(self._open_file)
        ctrl_layout.addWidget(self._btn_open, alignment=QtCore.Qt.AlignmentFlag.AlignRight)

        layout.addWidget(ctrl)

    def _draw_placeholder(self):
        self._preview_lbl.setText("No preview")
        self._preview_lbl.setStyleSheet(
            f"background-color: #050505; color: {config.MUTED};"
        )

    def _choose_folder(self):
        folder = QtWidgets.QFileDialog.getExistingDirectory(
            self,
            "Save recordings to (folder will contain webcam/ and screen/)...",
            str(self._app._recordings_base),
        )
        if folder:
            self._app._recordings_base = Path(folder)

    def _toggle_recording(self):
        if self.recorder and self.recorder.recording:
            self._stop_recording()
        else:
            self._start_recording()

    def _start_preview(self):
        """Start recorder in preview-only mode (no file). Used at app start when email is submitted."""
        if self.recorder is not None:
            return
        self.recorder = self.recorder_cls(
            on_frame=self._on_frame,
            on_status=self._on_status,
            on_done=self._on_done,
        )
        if hasattr(self.recorder, "start_preview"):
            self.recorder.start_preview()
        # else e.g. ScreenRecorder: no preview yet, recorder stays created but idle until _start_recording

    def _start_recording(self, start_barrier=None, email=None):
        email = email if email is not None else self._app.get_recording_email()
        if not email:
            return
        save_dir = str(self._effective_save_dir())
        # If already running in preview, switch to recording
        if (
            self.recorder is not None
            and hasattr(self.recorder, "begin_recording")
            and getattr(self.recorder, "_thread", None) is not None
            and self.recorder._thread.is_alive()
            and not self.recorder.recording
        ):
            self.recorder.begin_recording(
                save_dir, start_barrier=start_barrier, email=email
            )
        else:
            if self.recorder is None:
                self.recorder = self.recorder_cls(
                    on_frame=self._on_frame,
                    on_status=self._on_status,
                    on_done=self._on_done,
                )
            self.recorder.start(save_dir, start_barrier=start_barrier, email=email)
        self._btn_record.setText("⏹  Stop")
        self._btn_record.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {config.BG3};
                color: {config.RED};
                border: none;
                padding: 8px 14px;
            }}
            """
        )
        self._btn_open.setEnabled(False)

    def _stop_recording(self, stop_time=None):
        if self.recorder:
            self.recorder.stop(stop_time=stop_time)
        self._btn_record.setText("⏺  Start Recording")
        self._btn_record.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {config.RED};
                color: white;
                border: none;
                padding: 8px 14px;
            }}
            QPushButton:hover {{
                background-color: #ff5555;
            }}
            """
        )

    # These three callbacks are passed into the recorder threads.
    # They only emit signals; UI updates happen in the connected slots.
    def _on_frame(self, frame, elapsed):
        self.frame_received.emit(frame, float(elapsed))

    def _on_status(self, state, msg):
        self.status_changed.emit(state, msg)

    def _on_done(self, filename):
        self.recording_done.emit(filename)

    # Slots that run in the GUI thread
    @QtCore.Slot(object, float)
    def _handle_frame(self, frame, elapsed):
        try:
            pix = _frame_to_qpixmap(frame)
            if not pix.isNull():
                scaled = pix.scaled(
                    self._preview_lbl.size(),
                    QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                    QtCore.Qt.TransformationMode.SmoothTransformation,
                )
                self._preview_lbl.setPixmap(scaled)
                self._preview_lbl.setText("")
            self._timer_lbl.setText(fmt_time(elapsed))
            self._timer_lbl.setStyleSheet(f"color: {config.RED};")
            self._status_dot.setStyleSheet(f"color: {config.RED};")
        except Exception:
            pass

    @QtCore.Slot(str, str)
    def _handle_status(self, state, msg):
        self._file_lbl.setText(msg)

    @QtCore.Slot(str)
    def _handle_done(self, filename):
        self._last_file = filename
        short = Path(filename).name
        self._file_lbl.setText(f"✓  {short}")
        self._file_lbl.setStyleSheet(
            f"background-color: {config.BG2}; color: {config.GREEN}; padding: 6px 14px;"
        )
        self._status_dot.setStyleSheet(f"color: {config.GREEN};")
        self._timer_lbl.setStyleSheet(f"color: {config.FG2};")
        self._btn_record.setText("⏺  Start Recording")
        self._btn_record.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {config.RED};
                color: white;
                border: none;
                padding: 8px 14px;
            }}
            QPushButton:hover {{
                background-color: #ff5555;
            }}
            """
        )
        self._btn_open.setEnabled(True)

    def _open_file(self):
        if not self._last_file or not Path(self._last_file).exists():
            QtWidgets.QMessageBox.information(
                self, "File not found", "Recording file not found."
            )
            return
        url = QtCore.QUrl.fromLocalFile(str(self._last_file))
        QtGui.QDesktopServices.openUrl(url)
