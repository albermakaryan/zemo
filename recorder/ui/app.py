"""Main application window (PyQt): top bar, recorder panels, and recording actions."""

import sys
import subprocess
import time
import threading
from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets

from recorder import config, __version__
from recorder.common import email_filename_part
from recorder.recorders import WebcamRecorder, ScreenRecorder
from recorder.audio import InternalAudioRecorder, is_loopback_available
from recorder.audio import mux_audio_into_video as muxmod

from recorder.ui.dialogs import ask_university_email
from recorder.ui.float_button import FloatButtonWindow
from recorder.ui.panels import RecorderPanel


class App(QtWidgets.QMainWindow):
    """Main recorder application window (PyQt)."""

    def __init__(self, auto_mux: bool = True, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
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

    def _center_on_screen(self):
        screen = QtWidgets.QApplication.primaryScreen()
        if screen is None:
            return
        geo = screen.availableGeometry()
        self.resize(
            2 * config.PREVIEW_W + 96,
            config.PREVIEW_H + 180,
        )
        size = self.frameGeometry()
        size.moveCenter(geo.center())
        self.move(size.topLeft())

    def _start_previews(self):
        """Start webcam (and screen if supported) in preview-only mode so capture runs from app start."""
        for panel in (self._webcam_panel, self._screen_panel):
            if hasattr(panel, "_start_preview"):
                panel._start_preview()

    def _build(self):
        root_layout = QtWidgets.QVBoxLayout(self._central)
        root_layout.setContentsMargins(24, 20, 24, 16)
        root_layout.setSpacing(16)

        # Top bar
        topbar = QtWidgets.QFrame(self._central)
        topbar.setStyleSheet(f"background-color: {config.BG};")
        top_layout = QtWidgets.QHBoxLayout(topbar)
        top_layout.setContentsMargins(0, 0, 0, 0)

        mono_font = QtGui.QFont("Courier New", 11)
        mono_bold = QtGui.QFont("Courier New", 11, QtGui.QFont.Weight.Bold)

        lbl_rec = QtWidgets.QLabel("● REC", topbar)
        lbl_rec.setFont(mono_bold)
        lbl_rec.setStyleSheet(f"color: {config.RED};")
        top_layout.addWidget(lbl_rec, alignment=QtCore.Qt.AlignmentFlag.AlignLeft)

        lbl_studio = QtWidgets.QLabel("  STUDIO", topbar)
        lbl_studio.setFont(mono_font)
        lbl_studio.setStyleSheet(f"color: {config.FG2};")
        top_layout.addWidget(lbl_studio, alignment=QtCore.Qt.AlignmentFlag.AlignLeft)

        top_layout.addStretch(1)

        sans_font = QtGui.QFont("Segoe UI", 10)
        self._btn_both = QtWidgets.QPushButton("⏺  Record Both", topbar)
        self._btn_both.setFont(sans_font)
        self._btn_both.setCursor(
            QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        )
        self._btn_both.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {config.BG3};
                color: {config.FG};
                border: none;
                padding: 8px 16px;
            }}
            QPushButton:hover {{
                background-color: {config.BORDER};
            }}
            """
        )
        self._btn_both.clicked.connect(self.record_both)
        top_layout.addWidget(self._btn_both, alignment=QtCore.Qt.AlignmentFlag.AlignRight)

        root_layout.addWidget(topbar)

        # Panels
        panels = QtWidgets.QFrame(self._central)
        panels.setStyleSheet(f"background-color: {config.BG};")
        panels_layout = QtWidgets.QHBoxLayout(panels)
        panels_layout.setContentsMargins(0, 0, 0, 0)
        panels_layout.setSpacing(12)

        self._webcam_panel = RecorderPanel(
            panels, self, "Webcam", WebcamRecorder, config.WEBCAM_SUBDIR
        )
        self._screen_panel = RecorderPanel(
            panels, self, "Screen", ScreenRecorder, config.SCREEN_SUBDIR
        )

        panels_layout.addWidget(self._webcam_panel)
        panels_layout.addWidget(self._screen_panel)

        root_layout.addWidget(panels)

        # Bottom bar
        bottom = QtWidgets.QFrame(self._central)
        bottom.setStyleSheet(f"background-color: {config.BG};")
        bottom_layout = QtWidgets.QHBoxLayout(bottom)
        bottom_layout.setContentsMargins(0, 0, 0, 0)

        self._btn_stop_both = QtWidgets.QPushButton("⏹  Stop Both", bottom)
        self._btn_stop_both.setFont(sans_font)
        self._btn_stop_both.setCursor(
            QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        )
        self._btn_stop_both.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {config.BG3};
                color: {config.RED};
                border: none;
                padding: 8px 16px;
            }}
            QPushButton:hover {{
                background-color: {config.BORDER};
                color: {config.RED};
            }}
            """
        )
        self._btn_stop_both.clicked.connect(self.stop_both)
        bottom_layout.addWidget(self._btn_stop_both)

        bottom_layout.addStretch(1)

        mono_sm = QtGui.QFont("Courier New", 9)

        info_lbl = QtWidgets.QLabel(
            "Press ⏹ Stop to save. Saves to recordings/webcam, screen & audio", bottom
        )
        info_lbl.setFont(mono_sm)
        info_lbl.setStyleSheet(f"color: {config.MUTED};")
        bottom_layout.addWidget(info_lbl, alignment=QtCore.Qt.AlignmentFlag.AlignRight)

        self._audio_status_lbl = QtWidgets.QLabel("", bottom)
        self._audio_status_lbl.setFont(mono_sm)
        self._audio_status_lbl.setStyleSheet(
            f"color: {config.MUTED}; margin-left: 8px;"
        )
        bottom_layout.addWidget(self._audio_status_lbl)

        self._email_lbl = QtWidgets.QLabel("", bottom)
        self._email_lbl.setFont(mono_sm)
        self._email_lbl.setStyleSheet(
            f"color: {config.MUTED}; margin-left: 8px;"
        )
        bottom_layout.addWidget(self._email_lbl)

        root_layout.addWidget(bottom)

    def get_recording_email(self):
        """Return current university email; if not set, show dialog. Returns None if user cancels."""
        if self._user_email:
            return self._user_email
        email = ask_university_email(self)
        if email:
            self._user_email = email
            self._email_lbl.setText(f"Recording as: {email}")
        return email

    # Public helpers used by FloatButtonWindow
    def record_both(self):
        email = self.get_recording_email()
        if not email:
            return
        use_audio = is_loopback_available()
        num_party = 3 if use_audio else 2
        shared_start_time = [None]

        def set_shared_t0():
            shared_start_time[0] = time.time()

        barrier = threading.Barrier(num_party, action=set_shared_t0)

        self._webcam_panel._start_recording(start_barrier=barrier, email=email)
        self._screen_panel._start_recording(start_barrier=barrier, email=email)
        if use_audio:
            self._audio_recorder = InternalAudioRecorder(
                on_status=self._on_audio_status,
                on_done=lambda f: QtCore.QTimer.singleShot(
                    0, lambda: self._on_audio_done(f)
                ),
            )
            save_dir = str(config.get_audio_dir())
            self._audio_recorder.start(
                save_dir=save_dir,
                start_barrier=barrier,
                start_time_ref=shared_start_time,
                email=email,
            )
            self._audio_status_lbl.setText("+ audio")
            self._audio_status_lbl.setStyleSheet(f"color: {config.GREEN};")
        else:
            self._audio_recorder = None
            self._audio_status_lbl.setText("(no system audio)")
            self._audio_status_lbl.setStyleSheet(f"color: {config.MUTED};")

    def _on_audio_status(self, status: str, message: str):
        def _():
            self._audio_status_lbl.setText(message[:40] if message else status)

        QtCore.QTimer.singleShot(0, _)

    def _on_audio_done(self, filename: str):
        self._audio_status_lbl.setText("audio saved")
        self._audio_status_lbl.setStyleSheet(f"color: {config.MUTED};")

    def stop_both(self):
        """
        Stop all recorders (webcam, screen, and audio if active) with one shared stop_time,
        then join their threads concurrently. Optionally mux screen+audio.
        """
        stop_time = time.time()

        for panel in (self._webcam_panel, self._screen_panel):
            recorder = getattr(panel, "recorder", None)
            if recorder and getattr(recorder, "stop", None):
                recorder.stop(stop_time=stop_time)
        if getattr(self, "_audio_recorder", None) and self._audio_recorder.recording:
            self._audio_recorder.stop(stop_time=stop_time)

        self._join_recorders_concurrent(timeout=5.0)

        # Optionally mux screen video with internal audio into recordings/screen_with_audio.
        # - When running as a Python script, reuse the CLI helper:
        #       python -m recorder.audio.mux_audio_into_video --screen-only <email>
        # - When running as a frozen exe (PyInstaller), call mux_one() directly, because
        #   sys.executable is the exe and cannot run modules with "-m".
        if getattr(self, "_auto_mux", False):
            email = getattr(self, "_user_email", None)
            audio_rec = getattr(self, "_audio_recorder", None)
            has_audio = bool(audio_rec and getattr(audio_rec, "filename", ""))
            if not (email and has_audio):
                return

            if getattr(sys, "frozen", False):
                # Frozen exe: use the exact files that were just recorded.
                screen_path = getattr(self._screen_panel, "_last_file", "") or ""
                audio_path = getattr(audio_rec, "filename", "") if audio_rec else ""
                if not (screen_path and audio_path):
                    return
                screen_file = Path(screen_path)
                audio_file = Path(audio_path)
                if not (screen_file.exists() and audio_file.exists()):
                    return
                out_dir = config.RECORDINGS_DIR / "screen_with_audio"
                out_dir.mkdir(parents=True, exist_ok=True)
                stem = screen_file.stem
                out_path = out_dir / f"{stem}_screen_with_audio{config.VIDEO_EXT}"

                def _run_mux_frozen():
                    try:
                        ffmpeg_exe = muxmod._get_ffmpeg_exe()
                        if not ffmpeg_exe:
                            return
                        muxmod.mux_one(screen_file, audio_file, out_path, ffmpeg_exe)
                    except Exception:
                        # If auto-mux fails, user can still run the CLI manually.
                        pass

                t_mux = threading.Thread(target=_run_mux_frozen, daemon=True)
                t_mux.start()
            else:
                # Non-frozen: call the CLI helper module, same as manual usage.
                def _run_mux_cli():
                    try:
                        cmd = [
                            sys.executable,
                            "-m",
                            "recorder.audio.mux_audio_into_video",
                            "--screen-only",
                            email,
                        ]
                        subprocess.run(cmd, check=True)
                    except Exception:
                        # If auto-mux fails, user can still run the CLI manually.
                        pass

                t_mux = threading.Thread(target=_run_mux_cli, daemon=True)
                t_mux.start()

    def _join_recorders_concurrent(self, timeout: float = 5.0):
        """Join webcam, screen, and audio recorder threads in parallel."""
        join_threads = []
        for panel in (self._webcam_panel, self._screen_panel):
            recorder = getattr(panel, "recorder", None)
            if recorder and getattr(recorder, "join", None):
                t = threading.Thread(
                    target=recorder.join, kwargs={"timeout": timeout}, daemon=True
                )
                t.start()
                join_threads.append(t)
        if getattr(self, "_audio_recorder", None) and hasattr(
            self._audio_recorder, "join"
        ):
            t = threading.Thread(
                target=self._audio_recorder.join,
                kwargs={"timeout": timeout},
                daemon=True,
            )
            t.start()
            join_threads.append(t)
        for t in join_threads:
            t.join(timeout=timeout)

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
