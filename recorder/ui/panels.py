"""Recorder panel: preview, controls, and file info for one source (Webcam or Screen)."""

import subprocess
import sys
from pathlib import Path

import tkinter as tk
from tkinter import filedialog, messagebox

from recorder import config
from recorder.recorders import fmt_time, frame_to_tk


class RecorderPanel(tk.Frame):
    """One panel (Webcam or Screen) with preview, controls, and file info."""

    def __init__(self, parent, app, title, recorder_cls, subfolder, **kwargs):
        super().__init__(
            parent, bg=config.BG2, highlightbackground=config.BORDER,
            highlightthickness=1, **kwargs
        )
        self._app = app
        self.title_str = title
        self.recorder_cls = recorder_cls
        self.subfolder = subfolder
        self.recorder = None
        self._tk_img = None
        self._last_file = ""
        self._build()

    def _effective_save_dir(self) -> Path:
        base = Path(self._app._recordings_base)
        return base / self.subfolder

    def _build(self):
        header = tk.Frame(self, bg=config.BG3, pady=0)
        header.pack(fill="x")

        tk.Label(
            header, text=self.title_str.upper(), font=config.MONO,
            bg=config.BG3, fg=config.FG2, padx=14, pady=10
        ).pack(side="left")

        self._status_dot = tk.Label(
            header, text="●", font=config.MONO, bg=config.BG3, fg=config.MUTED, padx=4
        )
        self._status_dot.pack(side="right", padx=(0, 6))

        self._timer_lbl = tk.Label(
            header, text="00:00", font=config.MONO,
            bg=config.BG3, fg=config.MUTED, padx=6
        )
        self._timer_lbl.pack(side="right")

        self._canvas = tk.Canvas(
            self, width=config.PREVIEW_W, height=config.PREVIEW_H,
            bg="#050505", highlightthickness=0
        )
        self._canvas.pack()
        self._draw_placeholder()

        self._file_lbl = tk.Label(
            self, text="No recording yet", font=config.MONO_SM,
            bg=config.BG2, fg=config.MUTED, anchor="w", padx=14, pady=6
        )
        self._file_lbl.pack(fill="x")

        sep = tk.Frame(self, bg=config.BORDER, height=1)
        sep.pack(fill="x")

        ctrl = tk.Frame(self, bg=config.BG2, pady=12, padx=14)
        ctrl.pack(fill="x")

        sans = config.sans_font()
        self._btn_record = tk.Button(
            ctrl, text="⏺  Start Recording", font=sans,
            bg=config.RED, fg="white", relief="flat", cursor="hand2",
            activebackground="#ff5555", activeforeground="white",
            padx=14, pady=8, command=self._toggle_recording,
        )
        self._btn_record.pack(side="left")

        self._btn_folder = tk.Button(
            ctrl, text="📁", font=sans, bg=config.BG3, fg=config.FG2,
            relief="flat", cursor="hand2",
            activebackground=config.BORDER, activeforeground=config.FG,
            padx=10, pady=8, command=self._choose_folder,
        )
        self._btn_folder.pack(side="left", padx=(8, 0))

        self._btn_open = tk.Button(
            ctrl, text="▶  Play", font=sans, bg=config.BG3, fg=config.FG2,
            relief="flat", cursor="hand2",
            activebackground=config.BORDER, activeforeground=config.FG,
            padx=14, pady=8, command=self._open_file, state="disabled",
        )
        self._btn_open.pack(side="right")

    def _draw_placeholder(self):
        self._canvas.delete("all")
        cx, cy = config.PREVIEW_W // 2, config.PREVIEW_H // 2
        self._canvas.create_text(cx, cy, text="No preview", font=config.MONO_SM, fill=config.MUTED)

    def _choose_folder(self):
        folder = filedialog.askdirectory(
            initialdir=str(self._app._recordings_base),
            title="Save recordings to (folder will contain webcam/ and screen/)...",
        )
        if folder:
            self._app._recordings_base = Path(folder)

    def _toggle_recording(self):
        if self.recorder and self.recorder.recording:
            self._stop_recording()
        else:
            self._start_recording()

    def _start_recording(self, start_barrier=None, email=None):
        email = email if email is not None else self._app.get_recording_email()
        if not email:
            return
        save_dir = self._effective_save_dir()
        self.recorder = self.recorder_cls(
            on_frame=self._on_frame,
            on_status=self._on_status,
            on_done=self._on_done,
        )
        self.recorder.start(str(save_dir), start_barrier=start_barrier, email=email)
        self._btn_record.config(text="⏹  Stop", bg=config.BG3, fg=config.RED, activebackground=config.BG3)
        self._btn_open.config(state="disabled")

    def _stop_recording(self, stop_time=None):
        if self.recorder:
            self.recorder.stop(stop_time=stop_time)
        self._btn_record.config(
            text="⏺  Start Recording", bg=config.RED, fg="white", activebackground="#ff5555"
        )

    def _on_frame(self, frame, elapsed):
        try:
            photo = frame_to_tk(frame)
            self._tk_img = photo
            self._canvas.after(0, lambda: self._canvas.create_image(0, 0, anchor="nw", image=self._tk_img))
            self._timer_lbl.after(
                0,
                lambda t=elapsed: (
                    self._timer_lbl.config(text=fmt_time(t), fg=config.RED),
                    self._status_dot.config(fg=config.RED),
                ),
            )
        except Exception:
            pass

    def _on_status(self, state, msg):
        self._file_lbl.after(0, lambda: self._file_lbl.config(text=msg))

    def _on_done(self, filename):
        self._last_file = filename
        short = Path(filename).name

        def _update():
            self._file_lbl.config(text=f"✓  {short}", fg=config.GREEN)
            self._status_dot.config(fg=config.GREEN)
            self._timer_lbl.config(fg=config.FG2)
            self._btn_record.config(
                text="⏺  Start Recording", bg=config.RED, fg="white", activebackground="#ff5555"
            )
            self._btn_open.config(state="normal")

        self._file_lbl.after(0, _update)

    def _open_file(self):
        if not self._last_file or not Path(self._last_file).exists():
            messagebox.showinfo("File not found", "Recording file not found.")
            return
        if sys.platform == "win32":
            subprocess.Popen(["start", "", self._last_file], shell=True)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", self._last_file])
        else:
            subprocess.Popen(["xdg-open", self._last_file])
