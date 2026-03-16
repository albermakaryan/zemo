"""Main application window: top bar, recorder panels, and recording actions."""

import sys
import subprocess
import time
import threading
from pathlib import Path

import tkinter as tk

from recorder import config, __version__
from recorder.common import email_filename_part
from recorder.recorders import WebcamRecorder, ScreenRecorder
from recorder.audio import InternalAudioRecorder, is_loopback_available
from recorder.audio import mux_audio_into_video as muxmod

from recorder.ui.dialogs import ask_university_email
from recorder.ui.float_button import FloatButtonWindow
from recorder.ui.panels import RecorderPanel


class App(tk.Tk):
    """Main recorder application window."""

    def __init__(self, auto_mux: bool = True):
        super().__init__()
        self.title(f"Recorder v{__version__}")
        self.configure(bg=config.BG)
        self.resizable(False, False)

        config.ensure_recordings_dirs()
        self._recordings_base = config.get_recordings_dir()
        self._user_email = None
        # Internal (system) audio; started with Record Both when available
        self._audio_recorder = None
        # When True, merge screen video + internal audio into recordings/screen_with_audio after Stop Both
        self._auto_mux = bool(auto_mux)

        # TODO(alber): file naming / suffix logic
        # Right now, filename uniqueness (adding _1, _2, … suffixes) is handled
        # inside each recorder (screen, webcam, audio) via unique_name_with_suffix().
        # That prevents overwrites, but the suffixes are per-folder/type only.
        # For a more polished UX, centralize this logic here so all outputs for a
        # single "session" (screen, webcam, audio, muxed) share a consistent
        # base name and run index, and display that in the UI.

        self._build()
        self.update_idletasks()

        self._float_win = FloatButtonWindow(self)

        # Show main window with webcam + screen preview (no recording, no email yet)
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self.update_idletasks()
        ww = self.winfo_width()
        wh = self.winfo_height()
        self.geometry(f"+{(sw - ww) // 2}+{(sh - wh) // 2}")
        self.lift()
        self.attributes("-topmost", True)
        self.after(100, lambda: self.attributes("-topmost", False))
        self._start_previews()

    def _start_previews(self):
        """Start webcam (and screen if supported) in preview-only mode so capture runs from app start."""
        for panel in (self._webcam_panel, self._screen_panel):
            if hasattr(panel, "_start_preview"):
                panel._start_preview()

    def _build(self):
        topbar = tk.Frame(self, bg=config.BG, pady=0)
        topbar.pack(fill="x", padx=24, pady=(20, 0))

        tk.Label(
            topbar,
            text="● REC",
            font=("Courier New", 11, "bold"),
            bg=config.BG,
            fg=config.RED,
        ).pack(side="left")
        tk.Label(
            topbar,
            text="  STUDIO",
            font=("Courier New", 11),
            bg=config.BG,
            fg=config.FG2,
        ).pack(side="left")

        sans = config.sans_font()
        self._btn_both = tk.Button(
            topbar,
            text="⏺  Record Both",
            font=sans,
            bg=config.BG3,
            fg=config.FG,
            relief="flat",
            cursor="hand2",
            activebackground=config.BORDER,
            activeforeground=config.FG,
            padx=16,
            pady=8,
            command=self._record_both,
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
            bottom,
            text="⏹  Stop Both",
            font=sans,
            bg=config.BG3,
            fg=config.RED,
            relief="flat",
            cursor="hand2",
            activebackground=config.BORDER,
            activeforeground=config.RED,
            padx=16,
            pady=8,
            command=self._stop_both,
        )
        self._btn_stop_both.pack(side="left")

        self._email_lbl = tk.Label(
            bottom,
            text="",
            font=config.MONO_SM,
            bg=config.BG,
            fg=config.MUTED,
        )
        self._email_lbl.pack(side="right", padx=(8, 0))
        self._audio_status_lbl = tk.Label(
            bottom,
            text="",
            font=config.MONO_SM,
            bg=config.BG,
            fg=config.MUTED,
        )
        self._audio_status_lbl.pack(side="right", padx=(8, 0))
        tk.Label(
            bottom,
            text="Press ⏹ Stop to save. Saves to recordings/webcam, screen & audio",
            font=config.MONO_SM,
            bg=config.BG,
            fg=config.MUTED,
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
                on_done=lambda f: self.after(0, lambda: self._on_audio_done(f)),
            )
            save_dir = str(config.get_audio_dir())
            self._audio_recorder.start(
                save_dir=save_dir,
                start_barrier=barrier,
                start_time_ref=shared_start_time,
                email=email,
            )
            self._audio_status_lbl.config(text="+ audio", fg=config.GREEN)
        else:
            self._audio_recorder = None
            self._audio_status_lbl.config(text="(no system audio)", fg=config.MUTED)

    def _on_audio_status(self, status: str, message: str):
        def _():
            self._audio_status_lbl.config(text=message[:40] if message else status)

        self.after(0, _)

    def _on_audio_done(self, filename: str):
        self._audio_status_lbl.config(text="audio saved", fg=config.MUTED)

    def _stop_both(self):
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

    def on_close(self):
        """Gracefully stop all recordings before destroying the window."""
        stop_time = time.time()
        for panel in (self._webcam_panel, self._screen_panel):
            recorder = getattr(panel, "recorder", None)
            if recorder and getattr(recorder, "stop", None):
                recorder.stop(stop_time=stop_time)
        if getattr(self, "_audio_recorder", None) and self._audio_recorder.recording:
            self._audio_recorder.stop(stop_time=stop_time)
        self._join_recorders_concurrent(timeout=5.0)

        if getattr(self, "_float_win", None) and self._float_win.winfo_exists():
            self._float_win.destroy()
        self.destroy()
