"""Main application window: top bar, recorder panels, and recording actions."""

import time
import threading
from pathlib import Path

import tkinter as tk

from recorder import config
from recorder.common import email_filename_part
from recorder.recorders import WebcamRecorder, ScreenRecorder
from recorder.audio import InternalAudioRecorder, is_loopback_available

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
        self._audio_recorder = None  # internal (system) audio; started with Record Both when available
        self._detector_enabled = tk.BooleanVar(value=False)

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

        self._detector_cb = tk.Checkbutton(
            bottom, text="Run after Stop Both", font=config.MONO_SM,
            variable=self._detector_enabled, bg=config.BG, fg=config.FG2,
            selectcolor=config.BG3, activebackground=config.BG, activeforeground=config.FG2,
        )
        self._detector_cb.pack(side="left", padx=(16, 0))

        self._emotion_overlay = None  # EmotionOverlay when detection is on
        self._btn_realtime_detector = tk.Button(
            bottom, text="▶  Start emotion detection", font=sans,
            bg=config.BG3, fg=config.GREEN, relief="flat", cursor="hand2",
            activebackground=config.BORDER, activeforeground=config.FG,
            padx=12, pady=8, command=self._toggle_realtime_emotion_detection,
        )
        self._btn_realtime_detector.pack(side="left", padx=(8, 0))

        self._email_lbl = tk.Label(
            bottom, text="",
            font=config.MONO_SM, bg=config.BG, fg=config.MUTED,
        )
        self._email_lbl.pack(side="right", padx=(8, 0))
        self._audio_status_lbl = tk.Label(
            bottom, text="",
            font=config.MONO_SM, bg=config.BG, fg=config.MUTED,
        )
        self._audio_status_lbl.pack(side="right", padx=(8, 0))
        self._detection_status_lbl = tk.Label(
            bottom, text="",
            font=config.MONO_SM, bg=config.BG, fg=config.MUTED,
        )
        self._detection_status_lbl.pack(side="right", padx=(8, 0))
        tk.Label(
            bottom, text="Press ⏹ Stop to save. Saves to recordings/webcam, screen & audio",
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
        use_audio = is_loopback_available()
        num_party = 3 if use_audio else 2
        shared_start_time = [None]

        def set_shared_t0():
            shared_start_time[0] = time.time()

        barrier = threading.Barrier(num_party, action=set_shared_t0)

        # If emotion detection overlay is active, attach the email-based name so
        # CSV saving can start once recording is running. This does not start
        # detection or recording by itself.
        if getattr(self, "_emotion_overlay", None) is not None:
            try:
                from detector.realtime import EmotionOverlay  # type: ignore
                if isinstance(self._emotion_overlay, EmotionOverlay):
                    self._emotion_overlay.set_name_part(email_filename_part(email))
            except Exception:
                pass
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

    def _toggle_realtime_emotion_detection(self):
        """Start or stop emotion overlay on the webcam preview (no second window)."""
        if self._emotion_overlay is not None:
            self._stop_realtime_emotion_detection()
            return
        try:
            from detector.realtime import EmotionOverlay
        except ImportError:
            from tkinter import messagebox
            messagebox.showerror(
                "Emotion detection",
                "Detector not available. Install: pip install deepface tf-keras",
            )
            return

        recorder = getattr(self._webcam_panel, "recorder", None)
        if recorder is None or not getattr(recorder, "_thread", None) or not recorder._thread.is_alive():
            from tkinter import messagebox
            messagebox.showwarning(
                "Emotion detection",
                "Webcam preview is not running. Start the webcam first.",
            )
            return

        save_dir = config.get_detection_dir().resolve()
        # Do NOT prompt for email here; detection is independent from recording.
        # We only attach an email-based name after the user starts recording.
        self._emotion_overlay = EmotionOverlay(
            save_dir=save_dir,
            fps=config.FPS,
            sample_interval_s=0.5,
        )
        recorder.set_overlay_callback(self._emotion_overlay)

        self._detection_status_lbl.config(
            text="Emotion detection on — overlay in webcam preview",
            fg=config.GREEN,
        )
        self._btn_realtime_detector.config(
            text="⏹  Stop emotion detection",
            fg=config.RED,
        )

    def _stop_realtime_emotion_detection(self):
        """Stop emotion overlay and close CSV."""
        recorder = getattr(self._webcam_panel, "recorder", None)
        if recorder is not None and hasattr(recorder, "set_overlay_callback"):
            recorder.set_overlay_callback(None)
        if self._emotion_overlay is not None:
            self._emotion_overlay.stop()
            csv_path = self._emotion_overlay.csv_path
            self._emotion_overlay = None
            self._detection_status_lbl.config(
                text=f"Saved: {csv_path}" if csv_path.exists() else "Emotion detection stopped",
                fg=config.GREEN if csv_path.exists() else config.MUTED,
            )
        self._btn_realtime_detector.config(
            text="▶  Start emotion detection",
            fg=config.GREEN,
        )

    def _stop_both(self):
        """
        Stop all recorders (webcam, screen, and audio if active) with one shared stop_time,
        then join their threads concurrently. If emotion detection is enabled, run it in
        a background thread and save results to recordings/detection/.
        """
        stop_time = time.time()

        for panel in (self._webcam_panel, self._screen_panel):
            recorder = getattr(panel, "recorder", None)
            if recorder and getattr(recorder, "stop", None):
                recorder.stop(stop_time=stop_time)
        if getattr(self, "_audio_recorder", None) and self._audio_recorder.recording:
            self._audio_recorder.stop(stop_time=stop_time)

        self._join_recorders_concurrent(timeout=5.0)

        if self._detector_enabled.get():
            webcam_path = getattr(self._webcam_panel, "_last_file", "") or ""
            screen_path = getattr(self._screen_panel, "_last_file", "") or ""
            w_path = Path(webcam_path) if webcam_path else None
            s_path = Path(screen_path) if screen_path else None
            if w_path and s_path and w_path.exists() and s_path.exists():
                out_dir = config.get_detection_dir().resolve()
                out_dir.mkdir(parents=True, exist_ok=True)
                stem = w_path.stem
                output_csv = str(out_dir / f"{stem}_emotions.csv")
                output_video = str(out_dir / f"{stem}_annotated.mp4")
                webcam_abs = str(w_path.resolve())
                screen_abs = str(s_path.resolve())
                self._detection_status_lbl.config(text="Detecting emotions…", fg=config.MUTED)

                def run_detection():
                    try:
                        from detector import analyze_webcam_and_screen
                        analyze_webcam_and_screen(
                            webcam_path=webcam_abs,
                            screen_path=screen_abs,
                            output_csv=output_csv,
                            sample_every_s=1.0,
                            output_annotated_video=output_video,
                        )
                        short_csv = Path(output_csv).name
                        short_vid = Path(output_video).name
                        msg = f"Saved: {out_dir}"
                        self.after(0, lambda: self._detection_status_lbl.config(
                            text=msg, fg=config.GREEN
                        ))
                    except ImportError:
                        self.after(0, lambda: self._detection_status_lbl.config(
                            text="Detection: install deepface", fg=config.RED
                        ))
                    except Exception as e:
                        self.after(0, lambda: self._detection_status_lbl.config(
                            text=f"Detection error: {str(e)[:40]}", fg=config.RED
                        ))

                t = threading.Thread(target=run_detection, daemon=True)
                t.start()
            else:
                self._detection_status_lbl.config(
                    text="Detection: no webcam/screen file", fg=config.MUTED
                )

    def _join_recorders_concurrent(self, timeout: float = 5.0):
        """Join webcam, screen, and audio recorder threads in parallel."""
        join_threads = []
        for panel in (self._webcam_panel, self._screen_panel):
            recorder = getattr(panel, "recorder", None)
            if recorder and getattr(recorder, "join", None):
                t = threading.Thread(target=recorder.join, kwargs={"timeout": timeout}, daemon=True)
                t.start()
                join_threads.append(t)
        if getattr(self, "_audio_recorder", None) and hasattr(self._audio_recorder, "join"):
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