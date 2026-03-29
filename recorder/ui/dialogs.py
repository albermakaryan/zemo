"""Modal dialogs (e.g. university email) implemented with PySide."""

from typing import Optional

from PySide6 import QtCore, QtGui, QtWidgets

from recorder import config


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
