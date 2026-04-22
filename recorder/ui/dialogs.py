"""Modal dialogs (e.g. university email, settings) implemented with PySide."""

from typing import Optional

from PySide6 import QtCore, QtGui, QtWidgets

from recorder import config


def load_persisted_fps() -> int:
    """
    Read FPS from QSettings, clamped to ``[FPS_MIN, FPS_MAX]``.

    If the key exists (e.g. you saved 14 in Settings once), that value wins over
    ``config.DEFAULT_FPS`` in the repo. Must use the same QSettings org/app as on save.
    """
    s = QtCore.QSettings(config.QSETTINGS_ORG, config.QSETTINGS_APP)
    s.sync()
    d = int(config.DEFAULT_FPS)
    raw = s.value("recording/fps")
    if raw in (None, ""):
        v = d
    else:
        try:
            v = int(float(str(raw).strip()))
        except (TypeError, ValueError):
            v = d
    return max(config.FPS_MIN, min(config.FPS_MAX, v))


class UniversityEmailDialog(QtWidgets.QDialog):
    """Simple modal dialog asking for a university email address."""

    def __init__(self, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self._email: Optional[str] = None
        self.setWindowTitle("University email")
        self.setModal(True)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose)
        self._build_ui()

    def _build_ui(self):
        self.setStyleSheet(
            f"""
            QDialog {{
                background-color: {config.BG2};
            }}
            QLabel {{
                color: {config.FG};
            }}
            QLineEdit {{
                background-color: {config.BG3};
                color: {config.FG};
                border: 1px solid {config.BORDER};
                padding: 6px;
            }}
            QPushButton {{
                background-color: {config.BG3};
                color: {config.FG};
                border: none;
                padding: 6px 16px;
            }}
            QPushButton:hover {{
                background-color: {config.BORDER};
            }}
            """
        )

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        label = QtWidgets.QLabel("Enter your University email address", self)
        label.setFont(QtGui.QFont("Segoe UI", 10))
        layout.addWidget(label)

        self._entry = QtWidgets.QLineEdit(self)
        self._entry.setFont(QtGui.QFont("Segoe UI", 10))
        layout.addWidget(self._entry)

        btn_box = QtWidgets.QDialogButtonBox(self)
        btn_ok = btn_box.addButton(
            "OK", QtWidgets.QDialogButtonBox.ButtonRole.AcceptRole
        )
        btn_cancel = btn_box.addButton(
            "Cancel", QtWidgets.QDialogButtonBox.ButtonRole.RejectRole
        )
        btn_ok.clicked.connect(self._on_ok)
        btn_cancel.clicked.connect(self.reject)

        layout.addWidget(btn_box)

        self._entry.returnPressed.connect(self._on_ok)
        self._entry.setFocus()

    def _validate(self) -> bool:
        s = (self._entry.text() or "").strip()
        if "@" in s and "." in s and len(s) > 5:
            self._email = s
            return True
        QtWidgets.QMessageBox.warning(
            self,
            "Invalid email",
            "Please enter a valid university email address.",
        )
        return False

    def _on_ok(self):
        if self._validate():
            self.accept()

    @property
    def email(self) -> Optional[str]:
        return self._email


class SettingsDialog(QtWidgets.QDialog):
    """
    Application settings. Changes are written only when the user clicks **Save**.
    (Cancel closes without writing; more fields can be added to `_on_save` later.)
    """

    def __init__(self, parent: QtWidgets.QWidget | None, initial_fps: int):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setModal(True)
        # Values read by the app after accept() (do not set WA_DeleteOnClose).
        self._saved_fps: Optional[int] = None
        self._build_ui(initial_fps)

    def _base_stylesheet(self) -> str:
        return f"""
            QDialog {{
                background-color: {config.BG2};
            }}
            QLabel {{
                color: {config.FG};
            }}
            QGroupBox {{
                color: {config.FG2};
                border: 1px solid {config.BORDER};
                border-radius: 4px;
                margin-top: 10px;
                padding: 12px 12px 8px 12px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
            }}
            QSpinBox {{
                background-color: {config.BG3};
                color: {config.FG};
                border: 1px solid {config.BORDER};
                border-radius: 2px;
                padding: 4px 8px 4px 8px;
                padding-right: 24px;
            }}
            QSpinBox::up-button, QSpinBox::down-button {{
                width: 20px;
                margin: 0 0 0 2px;
            }}
            QSlider::groove:horizontal {{
                background: {config.BG};
                height: 4px;
                border-radius: 2px;
            }}
            QSlider::sub-page:horizontal {{
                background: {config.BORDER};
                border-radius: 2px;
            }}
            QSlider::add-page:horizontal {{
                background: {config.BG};
                border-radius: 2px;
            }}
            QSlider::handle:horizontal {{
                background: {config.FG2};
                width: 14px;
                height: 14px;
                margin: -5px 0;
                border-radius: 7px;
            }}
            QSlider::handle:horizontal:hover {{
                background: {config.FG};
            }}
            QPushButton {{
                background-color: {config.BG3};
                color: {config.FG};
                border: none;
                padding: 6px 16px;
            }}
            QPushButton:hover {{
                background-color: {config.BORDER};
            }}
            QDialogButtonBox QPushButton {{
                min-width: 84px;
            }}
        """

    def _build_ui(self, initial_fps: int) -> None:
        self.setStyleSheet(self._base_stylesheet())
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 16)
        layout.setSpacing(10)

        title = QtWidgets.QLabel("Settings", self)
        title_font = QtGui.QFont("Segoe UI", 12)
        title_font.setWeight(QtGui.QFont.Weight.DemiBold)
        title.setFont(title_font)
        title.setStyleSheet(f"color: {config.FG};")
        layout.addWidget(title)

        hint = QtWidgets.QLabel(
            "Click “Save” to store your choices for this user on this computer. "
            "For FPS: when you are not recording, the live preview restarts to use the new value.",
            self,
        )
        hint.setWordWrap(True)
        hint.setFont(QtGui.QFont("Segoe UI", 9))
        hint.setStyleSheet(f"color: {config.MUTED};")
        layout.addWidget(hint)

        rec_group = QtWidgets.QGroupBox("Recording", self)
        rec_layout = QtWidgets.QFormLayout(rec_group)
        rec_layout.setSpacing(10)

        v0 = max(
            config.FPS_MIN,
            min(config.FPS_MAX, int(initial_fps)),
        )
        self._fps_spin = QtWidgets.QSpinBox(rec_group)
        self._fps_spin.setRange(config.FPS_MIN, config.FPS_MAX)
        self._fps_spin.setValue(v0)
        self._fps_spin.setFixedWidth(88)
        self._fps_spin.setButtonSymbols(
            QtWidgets.QAbstractSpinBox.ButtonSymbols.UpDownArrows
        )
        self._fps_slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal, rec_group)
        self._fps_slider.setRange(config.FPS_MIN, config.FPS_MAX)
        self._fps_slider.setValue(v0)
        self._fps_slider.setPageStep(1)
        self._fps_slider.setToolTip(
            "Target output frames per second. Lower values reduce CPU use and cut down duplicate "
            "frames when the machine cannot keep up."
        )
        self._fps_spin.setToolTip(self._fps_slider.toolTip())
        _fps_row = QtWidgets.QHBoxLayout()
        _fps_row.setSpacing(10)
        _fps_row.addWidget(self._fps_slider, stretch=1)
        _fps_row.addWidget(self._fps_spin, stretch=0)
        self._fps_spin.valueChanged.connect(self._fps_slider.setValue)
        self._fps_slider.valueChanged.connect(self._fps_spin.setValue)
        rec_layout.addRow("Frames per second (FPS):", _fps_row)
        layout.addWidget(rec_group)

        btn_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Save
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        save_btn = btn_box.button(QtWidgets.QDialogButtonBox.StandardButton.Save)
        if save_btn is not None:
            save_btn.setDefault(True)
            save_btn.setAutoDefault(True)
        cancel_btn = btn_box.button(QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        if save_btn is not None:
            save_btn.clicked.connect(self._on_save)
        if cancel_btn is not None:
            cancel_btn.clicked.connect(self.reject)
        layout.addWidget(btn_box)

    def _read_fps_from_widgets(self) -> int:
        self._fps_spin.clearFocus()
        if hasattr(self._fps_spin, "interpretText"):
            self._fps_spin.interpretText()
        v = int(self._fps_spin.value())
        v = max(config.FPS_MIN, min(config.FPS_MAX, v))
        self._fps_spin.setValue(v)
        self._fps_slider.setValue(v)
        return v

    def _on_save(self) -> None:
        """Copy all settings from widgets into attributes, then close with Accepted.
        Add other keys here (and matching fields) as the dialog grows.
        """
        self._saved_fps = self._read_fps_from_widgets()
        self.accept()

    @property
    def saved_fps(self) -> int:
        """Set only after a successful **Save** (dialog finished Accepted)."""
        if self._saved_fps is None:
            raise RuntimeError("saved_fps is only defined after saving")
        return self._saved_fps


def ask_university_email(parent: QtWidgets.QWidget | None) -> Optional[str]:
    """Show modal dialog asking for university email. Returns email or None if cancelled."""
    dlg = UniversityEmailDialog(parent)
    dlg.resize(420, 140)
    if parent is not None:
        geo = parent.frameGeometry()
        center = geo.center()
        dlg.move(center - dlg.rect().center())
    result = dlg.exec()
    if result == QtWidgets.QDialog.DialogCode.Accepted:
        return dlg.email
    return None
