"""UIMixin: builds the main window layout (top bar, panels, bottom bar)."""

from PySide6 import QtCore, QtGui, QtWidgets

from recorder import config
from recorder.recorders import WebcamRecorder, ScreenRecorder
from recorder.ui.panels import RecorderPanel
from gazer import EyeTracker


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
        root_layout.addWidget(self._build_settings_panel())
        root_layout.addWidget(self._build_panels())
        root_layout.addWidget(self._build_bottombar())

        # Sync indicator with checkbox initial state and any future changes
        self._update_gaze_indicator(self._chk_gaze.isChecked())
        self._chk_gaze.stateChanged.connect(
            lambda state: self._update_gaze_indicator(bool(state))
        )

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

        # Settings gear button — upper-right, before Record Both
        self._btn_settings = QtWidgets.QPushButton("⚙", topbar)
        self._btn_settings.setFont(sans_font)
        self._btn_settings.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
        self._btn_settings.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        self._btn_settings.setCheckable(True)
        self._btn_settings.setChecked(False)
        self._btn_settings.setFixedSize(34, 34)
        self._btn_settings.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {config.BG3};
                color: {config.FG2};
                border: none;
            }}
            QPushButton:hover {{
                background-color: {config.BORDER};
                color: {config.FG};
            }}
            QPushButton:checked {{
                background-color: {config.BORDER};
                color: {config.FG};
            }}
            """
        )
        self._btn_settings.clicked.connect(self._toggle_settings_panel)
        layout.addWidget(self._btn_settings, alignment=QtCore.Qt.AlignmentFlag.AlignRight)

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
        self._btn_both.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        self._btn_both.clicked.connect(self.record_both)
        layout.addWidget(self._btn_both, alignment=QtCore.Qt.AlignmentFlag.AlignRight)

        return topbar

    def _build_settings_panel(self) -> QtWidgets.QFrame:
        """Collapsible settings panel, hidden by default, sits below the top bar."""
        mono_sm = QtGui.QFont("Courier New", 9)

        self._settings_panel = QtWidgets.QFrame(self._central)
        self._settings_panel.setStyleSheet(
            f"background-color: {config.BG2}; border: 1px solid {config.BORDER};"
        )
        self._settings_panel.setVisible(False)

        sp_layout = QtWidgets.QHBoxLayout(self._settings_panel)
        sp_layout.setContentsMargins(14, 8, 14, 8)
        sp_layout.setSpacing(16)

        # Section label
        lbl = QtWidgets.QLabel("GAZE TRACKING", self._settings_panel)
        lbl.setFont(QtGui.QFont("Courier New", 9, QtGui.QFont.Weight.Bold))
        lbl.setStyleSheet(f"color: {config.FG2}; border: none;")
        sp_layout.addWidget(lbl)

        model_exists = EyeTracker.is_model_saved()

        self._chk_gaze = QtWidgets.QCheckBox("Enable", self._settings_panel)
        self._chk_gaze.setFont(mono_sm)
        self._chk_gaze.setStyleSheet(f"color: {config.FG}; border: none;")
        self._chk_gaze.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        self._chk_gaze.setEnabled(True)
        self._chk_gaze.setChecked(True)  # always on by default; missing model is handled at record time
        if not model_exists:
            self._chk_gaze.setToolTip("Calibrate first to enable gaze tracking")
        sp_layout.addWidget(self._chk_gaze)

        self._gaze_status_lbl = QtWidgets.QLabel("", self._settings_panel)
        self._gaze_status_lbl.setFont(mono_sm)
        self._gaze_status_lbl.setStyleSheet(f"color: {config.MUTED}; border: none;")
        sp_layout.addWidget(self._gaze_status_lbl)

        sp_layout.addStretch(1)

        return self._settings_panel

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
        self._btn_stop_both.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        self._btn_stop_both.clicked.connect(self.stop_both)
        layout.addWidget(self._btn_stop_both)

        model_exists = EyeTracker.is_model_saved()
        self._btn_calibrate = QtWidgets.QPushButton(
            "Re-calibrate Eyes" if model_exists else "Calibrate Eyes", bottom
        )
        self._btn_calibrate.setFont(sans_font)
        self._btn_calibrate.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
        self._btn_calibrate.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        self._btn_calibrate.setStyleSheet(
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
        self._btn_calibrate.clicked.connect(self._on_calibrate_clicked)
        layout.addWidget(self._btn_calibrate)

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

        self._gaze_indicator_lbl = QtWidgets.QLabel("", bottom)
        self._gaze_indicator_lbl.setFont(mono_sm)
        self._gaze_indicator_lbl.setStyleSheet(f"color: {config.MUTED}; margin-left: 8px;")
        layout.addWidget(self._gaze_indicator_lbl)

        self._email_lbl = QtWidgets.QLabel("", bottom)
        self._email_lbl.setFont(mono_sm)
        self._email_lbl.setStyleSheet(f"color: {config.MUTED}; margin-left: 8px;")
        layout.addWidget(self._email_lbl)

        return bottom

    def _toggle_settings_panel(self, checked: bool):
        self._settings_panel.setVisible(checked)

    def _update_gaze_indicator(self, enabled: bool):
        """Update the bottom-bar gaze indicator to reflect current setting."""
        if enabled:
            self._gaze_indicator_lbl.setText("+ gaze")
            self._gaze_indicator_lbl.setStyleSheet(f"color: {config.GREEN}; margin-left: 8px;")
        else:
            self._gaze_indicator_lbl.setText("")

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
