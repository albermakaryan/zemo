"""Floating always-on-top Start/Stop button window (draggable, no title bar)."""

import tkinter as tk

from recorder import config


class FloatButtonWindow(tk.Toplevel):
    """Always-on-top floating window with one big circular Start/Stop button and countdown."""

    SIZE = 120  # circular button window (width = height)

    def __init__(self, app):
        super().__init__(app)
        self._app = app
        self._countdown_remaining = 0
        self._countdown_job = None
        self.title("Rec")
        self.configure(bg=config.BG2)
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.wm_attributes("-topmost", True)
        self.overrideredirect(True)

        self._canvas = tk.Canvas(
            self, width=self.SIZE, height=self.SIZE,
            bg=config.BG2, highlightthickness=0, cursor="hand2",
        )
        self._canvas.pack(padx=4, pady=4)
        self._drag_start_x = self._drag_start_y = None
        self._drag_win_x = self._drag_win_y = None
        self._drag_moved = False
        self._canvas.bind("<Button-1>", self._on_press)
        self._canvas.bind("<B1-Motion>", self._on_drag)
        self._canvas.bind("<ButtonRelease-1>", self._on_release)

        r = 4
        self._oval_id = self._canvas.create_oval(
            r, r, self.SIZE - r, self.SIZE - r,
            fill=config.FLOAT_START_BG, outline=config.BORDER, width=2,
        )
        self._text_id = self._canvas.create_text(
            self.SIZE // 2, self.SIZE // 2,
            text="⏺", font=("Segoe UI", 32, "bold"),
            fill=config.FLOAT_START_FG,
        )

        self.geometry(f"{self.SIZE + 8}x{self.SIZE + 8}")
        self.bind("<Button-1>", self._on_press)
        self.bind("<B1-Motion>", self._on_drag)
        self.bind("<ButtonRelease-1>", self._on_release_window)
        self._place_topright()
        self._poll()

    def _place_topright(self):
        self.update_idletasks()
        try:
            sw = self.winfo_screenwidth()
            self.geometry(f"+{max(0, sw - self.SIZE - 8)}+{config.FLOAT_TOP_OFFSET}")
        except Exception:
            self.geometry(f"+100+{config.FLOAT_TOP_OFFSET}")

    def _on_press(self, e):
        self._drag_start_x = e.x_root
        self._drag_start_y = e.y_root
        self._drag_win_x = self.winfo_rootx()
        self._drag_win_y = self.winfo_rooty()
        self._drag_moved = False
        self._drag_pressed_on_canvas = e.widget == self._canvas
        self._app.bind_all("<B1-Motion>", self._on_drag)
        self._app.bind_all("<ButtonRelease-1>", self._on_release_anywhere)

    def _on_drag(self, e):
        if not self.winfo_exists():
            return
        dx = e.x_root - self._drag_start_x
        dy = e.y_root - self._drag_start_y
        if abs(dx) > 5 or abs(dy) > 5:
            self._drag_moved = True
        self.geometry(f"+{self._drag_win_x + dx}+{self._drag_win_y + dy}")
        self._drag_start_x = e.x_root
        self._drag_start_y = e.y_root
        self._drag_win_x = self.winfo_rootx()
        self._drag_win_y = self.winfo_rooty()

    def _on_release_anywhere(self, e):
        self._app.unbind_all("<B1-Motion>")
        self._app.unbind_all("<ButtonRelease-1>")
        if self.winfo_exists() and self._drag_pressed_on_canvas and not self._drag_moved:
            self._toggle()
        self._drag_start_x = self._drag_start_y = None

    def _on_release(self, e):
        pass

    def _on_release_window(self, e):
        pass

    def _is_counting_down(self):
        return self._countdown_remaining > 0

    def _is_recording(self):
        a = self._app
        w = getattr(a._webcam_panel, "recorder", None)
        s = getattr(a._screen_panel, "recorder", None)
        return (w and getattr(w, "recording", False)) or (s and getattr(s, "recording", False))

    def _toggle(self):
        if self._is_recording():
            self._app._stop_both()
            self._update_ui()
        elif not self._is_counting_down():
            # Email only when user clicks small button to start recording
            if not self._app.get_recording_email():
                return
            # Minimize preview window so only the small start/stop button is visible
            self._app.iconify()
            self.lift()
            self.attributes("-topmost", True)
            self._start_countdown()

    def _start_countdown(self):
        self._countdown_remaining = config.COUNTDOWN_SECONDS
        self._canvas.config(cursor="")
        self._canvas.itemconfig(self._oval_id, fill=config.BG3)
        self._canvas.itemconfig(self._text_id, text=str(self._countdown_remaining), fill=config.FG2)
        self._countdown_tick()

    def _countdown_tick(self):
        if self._countdown_job:
            self.after_cancel(self._countdown_job)
            self._countdown_job = None
        if not self.winfo_exists():
            return
        if self._countdown_remaining <= 0:
            self._canvas.config(cursor="hand2")
            self._saved_x, self._saved_y = self.winfo_rootx(), self.winfo_rooty()
            self._app._record_both()
            self._update_ui()
            self.geometry(f"+{self._saved_x}+{self._saved_y}")
            return
        self._canvas.itemconfig(self._text_id, text=str(self._countdown_remaining))
        self._countdown_remaining -= 1
        self._countdown_job = self.after(1000, self._countdown_tick)

    def _update_ui(self):
        if self._countdown_job:
            return
        x, y = self.winfo_rootx(), self.winfo_rooty()
        if self._is_recording():
            self._canvas.itemconfig(self._oval_id, fill=config.FLOAT_STOP_BG)
            self._canvas.itemconfig(self._text_id, text="⏹", fill=config.FLOAT_STOP_FG)
        else:
            self._canvas.itemconfig(self._oval_id, fill=config.FLOAT_START_BG)
            self._canvas.itemconfig(self._text_id, text="⏺", fill=config.FLOAT_START_FG)
        self.geometry(f"+{x}+{y}")

    def _poll(self):
        try:
            if self.winfo_exists() and not self._is_counting_down():
                self._update_ui()
            self.after(400, self._poll)
        except tk.TclError:
            pass
