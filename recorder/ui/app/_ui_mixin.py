"""UIMixin: builds the main window layout (top bar, panels, bottom bar)."""

from PySide6 import QtCore, QtGui, QtWidgets

from recorder import config
from recorder.recorders import WebcamRecorder, ScreenRecorder
from recorder.ui.dialogs import load_persisted_fps
from recorder.ui.panels import RecorderPanel


class UIMixin:
    """Mixin that owns all widget-construction logic for the App window."""

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _build(self):
        root_layout = QtWidgets.QVBoxLayout(self._central)
        root_layout.setContentsMargins(24, 20, 24, 16)
        root_layout.setSpacing(16)

        root_layout.addWidget(self._build_topbar())
        root_layout.addWidget(self._build_panels())
        root_layout.addWidget(self._build_bottombar())

    def _build_topbar(self) -> QtWidgets.QFrame:
        topbar = QtWidgets.QFrame(self._central)
        topbar.setStyleSheet(f"background-color: {config.BG};")
        layout = QtWidgets.QHBoxLayout(topbar)
        layout.setContentsMargins(0, 0, 0, 0)

        mono_bold = QtGui.QFont("Courier New", 11, QtGui.QFont.Weight.Bold)
        mono_font = QtGui.QFont("Courier New", 11)
        sans_font = QtGui.QFont("Segoe UI", 10)

        lbl_rec = QtWidgets.QLabel("● REC", topbar)
        lbl_rec.setFont(mono_bold)
        lbl_rec.setStyleSheet(f"color: {config.RED};")
        layout.addWidget(lbl_rec, alignment=QtCore.Qt.AlignmentFlag.AlignLeft)

        lbl_studio = QtWidgets.QLabel("  STUDIO", topbar)
        lbl_studio.setFont(mono_font)
        lbl_studio.setStyleSheet(f"color: {config.FG2};")
        layout.addWidget(lbl_studio, alignment=QtCore.Qt.AlignmentFlag.AlignLeft)

        layout.addStretch(1)

        self._fps_status_lbl = QtWidgets.QLabel("", topbar)
        self._fps_status_lbl.setFont(mono_font)
        self._fps_status_lbl.setStyleSheet(f"color: {config.FG2};")
        self._fps_status_lbl.setToolTip(
            "Active target frame rate (the last value saved in Settings, not necessarily the "
            f"code default of {int(config.DEFAULT_FPS)} in config.py). Change in Settings… "
            "when not recording."
        )
        layout.addWidget(
            self._fps_status_lbl, alignment=QtCore.Qt.AlignmentFlag.AlignRight
        )

        self._btn_settings = QtWidgets.QPushButton("Settings…", topbar)
        self._btn_settings.setFont(sans_font)
        self._btn_settings.setCursor(
            QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        )
        self._btn_settings.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {config.BG3};
                color: {config.FG2};
                border: 1px solid {config.BORDER};
                padding: 8px 14px;
            }}
            QPushButton:hover {{
                background-color: {config.BORDER};
                color: {config.FG};
            }}
        """
        )
        self._btn_settings.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        self._btn_settings.setToolTip("Application preferences (frame rate, etc.)")
        self._btn_settings.clicked.connect(self._open_settings)
        layout.addWidget(
            self._btn_settings, alignment=QtCore.Qt.AlignmentFlag.AlignRight
        )

        self._btn_both = QtWidgets.QPushButton("⏺  Record Both", topbar)
        self._btn_both.setFont(sans_font)
        self._btn_both.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
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
        # Prevent keyboard focus so Space/Enter cannot trigger "Record Both".
        self._btn_both.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        self._btn_both.clicked.connect(self.record_both)
        layout.addWidget(self._btn_both, alignment=QtCore.Qt.AlignmentFlag.AlignRight)

        return topbar

    def _build_panels(self) -> QtWidgets.QFrame:
        panels = QtWidgets.QFrame(self._central)
        panels.setStyleSheet(f"background-color: {config.BG};")
        layout = QtWidgets.QHBoxLayout(panels)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        self._webcam_panel = RecorderPanel(
            panels, self, "Webcam", WebcamRecorder, config.WEBCAM_SUBDIR
        )
        self._screen_panel = RecorderPanel(
            panels, self, "Screen", ScreenRecorder, config.SCREEN_SUBDIR
        )

        layout.addWidget(self._webcam_panel)
        layout.addWidget(self._screen_panel)

        return panels

    def _build_bottombar(self) -> QtWidgets.QFrame:
        sans_font = QtGui.QFont("Segoe UI", 10)
        mono_sm = QtGui.QFont("Courier New", 9)

        bottom = QtWidgets.QFrame(self._central)
        bottom.setStyleSheet(f"background-color: {config.BG};")
        layout = QtWidgets.QHBoxLayout(bottom)
        layout.setContentsMargins(0, 0, 0, 0)

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
        # Prevent keyboard focus so Space/Enter cannot trigger "Stop Both".
        self._btn_stop_both.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        self._btn_stop_both.clicked.connect(self.stop_both)
        layout.addWidget(self._btn_stop_both)

        layout.addStretch(1)

        info_lbl = QtWidgets.QLabel(
            "Press ⏹ Stop to save. Saves to recordings/webcam, screen & audio", bottom
        )
        info_lbl.setFont(mono_sm)
        info_lbl.setStyleSheet(f"color: {config.MUTED};")
        layout.addWidget(info_lbl, alignment=QtCore.Qt.AlignmentFlag.AlignRight)

        self._audio_status_lbl = QtWidgets.QLabel("", bottom)
        self._audio_status_lbl.setFont(mono_sm)
        self._audio_status_lbl.setStyleSheet(f"color: {config.MUTED}; margin-left: 8px;")
        layout.addWidget(self._audio_status_lbl)

        self._email_lbl = QtWidgets.QLabel("", bottom)
        self._email_lbl.setFont(mono_sm)
        self._email_lbl.setStyleSheet(f"color: {config.MUTED}; margin-left: 8px;")
        layout.addWidget(self._email_lbl)

        return bottom

    # ------------------------------------------------------------------
    # Window helpers
    # ------------------------------------------------------------------

    def _center_on_screen(self):
        screen = QtWidgets.QApplication.primaryScreen()
        if screen is None:
            return
        geo = screen.availableGeometry()
        self.resize(2 * config.PREVIEW_W + 96, config.PREVIEW_H + 180)
        size = self.frameGeometry()
        size.moveCenter(geo.center())
        self.move(size.topLeft())

    def _start_previews(self):
        """Start webcam (and screen) in preview-only mode from app launch."""
        for panel in (self._webcam_panel, self._screen_panel):
            if hasattr(panel, "_start_preview"):
                panel._start_preview()

    def _load_fps_setting(self) -> None:
        config.FPS = load_persisted_fps()
        self._update_fps_status_label()

    def _update_fps_status_label(self) -> None:
        lbl = getattr(self, "_fps_status_lbl", None)
        if not lbl:
            return
        lbl.setText(f"FPS {int(config.FPS)}")
