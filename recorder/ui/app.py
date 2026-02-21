"""Main application window: top bar, recorder panels, and recording actions."""

import time
import threading

import tkinter as tk

from recorder import config
from recorder.recorders import WebcamRecorder, ScreenRecorder

from recorder.ui.dialogs import ask_university_email
from recorder.ui.float_button import FloatButtonWindow
from recorder.ui.panels import RecorderPanel


class App(tk.Tk):
    """Main recorder application window."""

    def __init__(self):
        super().__init__()
        self.title("Recorder")
        self.configure(bg=config.BG)
        self.resizable(False, False)

        config.ensure_recordings_dirs()
        self._recordings_base = config.get_recordings_dir()
        self._user_email = None

        self._build()
        self.update_idletasks()

        self._float_win = FloatButtonWindow(self)

        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        ww = self.winfo_width()
        wh = self.winfo_height()
        self.geometry(f"+{(sw - ww) // 2}+{(sh - wh) // 2}")
        self.lift()
        self.attributes("-topmost", True)
        self.after(100, lambda: self.attributes("-topmost", False))

    def _build(self):
        topbar = tk.Frame(self, bg=config.BG, pady=0)
        topbar.pack(fill="x", padx=24, pady=(20, 0))

        tk.Label(
            topbar, text="● REC", font=("Courier New", 11, "bold"), bg=config.BG, fg=config.RED
        ).pack(side="left")
        tk.Label(
            topbar, text="  STUDIO", font=("Courier New", 11), bg=config.BG, fg=config.FG2
        ).pack(side="left")

        sans = config.sans_font()
        self._btn_both = tk.Button(
            topbar, text="⏺  Record Both", font=sans,
            bg=config.BG3, fg=config.FG, relief="flat", cursor="hand2",
            activebackground=config.BORDER, activeforeground=config.FG,
            padx=16, pady=8, command=self._record_both,
        )
        self._btn_both.pack(side="right")

        panels = tk.Frame(self, bg=config.BG)
        panels.pack(padx=24, pady=16)

        self._webcam_panel = RecorderPanel(
            panels, self, "Webcam", WebcamRecorder, config.WEBCAM_SUBDIR
        )
        self._webcam_panel.pack(side="left", padx=(0, 12))

        self._screen_panel = RecorderPanel(
            panels, self, "Screen", ScreenRecorder, config.SCREEN_SUBDIR
        )
        self._screen_panel.pack(side="left")

        bottom = tk.Frame(self, bg=config.BG)
        bottom.pack(fill="x", padx=24, pady=(0, 16))

        self._btn_stop_both = tk.Button(
            bottom, text="⏹  Stop Both", font=sans,
            bg=config.BG3, fg=config.RED, relief="flat", cursor="hand2",
            activebackground=config.BORDER, activeforeground=config.RED,
            padx=16, pady=8, command=self._stop_both,
        )
        self._btn_stop_both.pack(side="left")

        self._email_lbl = tk.Label(
            bottom, text="",
            font=config.MONO_SM, bg=config.BG, fg=config.MUTED,
        )
        self._email_lbl.pack(side="right", padx=(8, 0))
        tk.Label(
            bottom, text="Press ⏹ Stop to save. Saves to recordings/webcam & recordings/screen",
            font=config.MONO_SM, bg=config.BG, fg=config.MUTED,
        ).pack(side="right")

    def get_recording_email(self):
        """Return current university email; if not set, show dialog. Returns None if user cancels."""
        if self._user_email:
            return self._user_email
        email = ask_university_email(self)
        if email:
            self._user_email = email
            self._email_lbl.config(text=f"Recording as: {email}")
        return email

    def _record_both(self):
        email = self.get_recording_email()
        if not email:
            return
        barrier = threading.Barrier(2)
        self._webcam_panel._start_recording(start_barrier=barrier, email=email)
        self._screen_panel._start_recording(start_barrier=barrier, email=email)

    def _stop_both(self):
        """
        Stop both recorders simultaneously using a single shared stop_time,
        then join both writer threads concurrently so neither starves the other.
        """
        # Capture one shared timestamp so both videos are padded to the same endpoint
        stop_time = time.time()

        # Signal both recorders to stop at the exact same instant
        for panel in (self._webcam_panel, self._screen_panel):
            recorder = getattr(panel, "recorder", None)
            if recorder and getattr(recorder, "stop", None):
                recorder.stop(stop_time=stop_time)

        # Join both writer threads concurrently — prevents one from starving the other's timeout
        self._join_recorders_concurrent(timeout=5.0)

    def _join_recorders_concurrent(self, timeout: float = 5.0):
        """
        Call join() on both recorders in parallel threads so they drain
        and release their VideoWriters at the same time.
        """
        join_threads = []
        for panel in (self._webcam_panel, self._screen_panel):
            recorder = getattr(panel, "recorder", None)
            if recorder and getattr(recorder, "join", None):
                t = threading.Thread(
                    target=recorder.join,
                    kwargs={"timeout": timeout},
                    daemon=True,
                )
                t.start()
                join_threads.append(t)
        for t in join_threads:
            t.join(timeout=timeout)

    def on_close(self):
        """Gracefully stop all recordings before destroying the window."""
        stop_time = time.time()

        for panel in (self._webcam_panel, self._screen_panel):
            recorder = getattr(panel, "recorder", None)
            if recorder and getattr(recorder, "stop", None):
                recorder.stop(stop_time=stop_time)

        # Join concurrently so both files are fully flushed before window closes
        self._join_recorders_concurrent(timeout=5.0)

        if getattr(self, "_float_win", None) and self._float_win.winfo_exists():
            self._float_win.destroy()
        self.destroy()