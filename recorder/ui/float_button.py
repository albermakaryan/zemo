"""Floating always-on-top Start/Stop button window (PySide, draggable, no title bar)."""

from PySide6 import QtCore, QtGui, QtWidgets

from recorder import config


class FloatButtonWindow(QtWidgets.QWidget):
    """Always-on-top floating window with one big circular Start/Stop button and countdown."""

    SIZE = 120  # circular button window (width = height)

    def __init__(self, app_window: QtWidgets.QWidget):
        super().__init__(None, QtCore.Qt.WindowType.FramelessWindowHint)
        self._app = app_window
        self._countdown_remaining = 0
        self._countdown_timer = QtCore.QTimer(self)
        self._countdown_timer.timeout.connect(self._countdown_tick)

        self.setWindowTitle("Rec")
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setWindowFlag(QtCore.Qt.WindowType.WindowStaysOnTopHint, True)
        self.setFixedSize(self.SIZE + 8, self.SIZE + 8)

        self._drag_pos: QtCore.QPoint | None = None

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        self._canvas = QtWidgets.QPushButton(self)
        self._canvas.setCursor(
            QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        )
        self._canvas.setFlat(True)
        # Do not allow keyboard focus; only mouse clicks should toggle recording.
        self._canvas.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        self._canvas.clicked.connect(self._on_clicked)
        layout.addWidget(self._canvas)

        self._canvas.installEventFilter(self)

        self._update_button_style(start=True)
        self._place_topright()

        self._poll_timer = QtCore.QTimer(self)
        self._poll_timer.timeout.connect(self._update_ui)
        self._poll_timer.start(400)

    def _place_topright(self):
        screen = QtWidgets.QApplication.primaryScreen()
        if screen is None:
            self.move(100, config.FLOAT_TOP_OFFSET)
            return
        geo = screen.availableGeometry()
        x = max(0, geo.right() - self.width() - 8)
        y = config.FLOAT_TOP_OFFSET
        self.move(x, y)

    def eventFilter(self, obj, event):
        if obj is self._canvas:
            if event.type() == QtCore.QEvent.Type.Paint:
                self._paint_button()
            elif event.type() == QtCore.QEvent.Type.MouseButtonPress:
                if event.button() == QtCore.Qt.MouseButton.LeftButton:
                    # Start potential drag, but let QPushButton also handle the click
                    self._drag_pos = (
                        event.globalPosition().toPoint()
                        - self.frameGeometry().topLeft()
                    )
                    event.ignore()
                    return False
            elif event.type() == QtCore.QEvent.Type.MouseMove:
                if (
                    self._drag_pos is not None
                    and event.buttons() & QtCore.Qt.MouseButton.LeftButton
                ):
                    self.move(event.globalPosition().toPoint() - self._drag_pos)
                    event.accept()
                    return True
            elif event.type() == QtCore.QEvent.Type.MouseButtonRelease:
                self._drag_pos = None
        return super().eventFilter(obj, event)

    def _paint_button(self):
        pix = QtGui.QPixmap(self.SIZE, self.SIZE)
        pix.fill(QtCore.Qt.GlobalColor.transparent)
        painter = QtGui.QPainter(pix)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)

        rect = pix.rect().adjusted(4, 4, -4, -4)
        is_recording = self._is_recording()
        if self._countdown_remaining > 0:
            fill = QtGui.QColor(config.BG3)
            text = str(self._countdown_remaining)
            text_color = QtGui.QColor(config.FG2)
        elif is_recording:
            fill = QtGui.QColor(config.FLOAT_STOP_BG)
            text = "⏹"
            text_color = QtGui.QColor(config.FLOAT_STOP_FG)
        else:
            fill = QtGui.QColor(config.FLOAT_START_BG)
            text = "⏺"
            text_color = QtGui.QColor(config.FLOAT_START_FG)

        pen = QtGui.QPen(QtGui.QColor(config.BORDER))
        pen.setWidth(2)
        painter.setPen(pen)
        painter.setBrush(fill)
        painter.drawEllipse(rect)

        painter.setPen(text_color)
        font = QtGui.QFont("Segoe UI", 32, QtGui.QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(rect, QtCore.Qt.AlignmentFlag.AlignCenter, text)
        painter.end()

        self._canvas.setIcon(QtGui.QIcon(pix))
        self._canvas.setIconSize(pix.size())

    def _update_button_style(self, start: bool):
        self._paint_button()

    def _is_counting_down(self) -> bool:
        return self._countdown_remaining > 0

    def _is_recording(self) -> bool:
        a = self._app
        w = getattr(a, "_webcam_panel", None)
        s = getattr(a, "_screen_panel", None)
        w_rec = getattr(getattr(w, "recorder", None), "recording", False) if w else False
        s_rec = getattr(getattr(s, "recorder", None), "recording", False) if s else False
        return bool(w_rec or s_rec)

    def _on_clicked(self):
        if self._is_recording():
            self._app.stop_both()
            self._update_ui()
        elif not self._is_counting_down():
            if not self._app.get_recording_email():
                return
            self._app.showMinimized()
            self.raise_()
            self.activateWindow()
            self._start_countdown()

    def _start_countdown(self):
        self._countdown_remaining = config.COUNTDOWN_SECONDS
        self._countdown_timer.start(1000)
        self._update_ui()

    def _countdown_tick(self):
        if self._countdown_remaining <= 0:
            self._countdown_timer.stop()
            saved_pos = self.pos()
            self._app.record_both()
            self._update_ui()
            self.move(saved_pos)
            return
        self._countdown_remaining -= 1
        self._update_ui()

    def _update_ui(self):
        self._paint_button()
