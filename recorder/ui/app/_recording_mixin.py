"""RecordingMixin: record_both, stop_both, mux dispatch, audio callbacks."""

import sys
import subprocess
import time
import threading
from pathlib import Path

from PySide6 import QtCore

from recorder import config
from recorder.audio import InternalAudioRecorder, is_loopback_available
from recorder.audio import mux_audio_into_video as muxmod
from recorder.ui.dialogs import ask_university_email


class RecordingMixin:
    """Mixin that owns all recording-action logic for the App window."""

    # ------------------------------------------------------------------
    # Email
    # ------------------------------------------------------------------

    def get_recording_email(self):
        """Return current university email; prompts if unset. Returns None if cancelled."""
        if self._user_email:
            return self._user_email
        email = ask_university_email(self)
        if email:
            self._user_email = email
            self._email_lbl.setText(f"Recording as: {email}")
        return email

    # ------------------------------------------------------------------
    # Start
    # ------------------------------------------------------------------

    def record_both(self):
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
                on_done=lambda f: QtCore.QTimer.singleShot(
                    0, lambda: self._on_audio_done(f)
                ),
            )
            self._audio_recorder.start(
                save_dir=str(config.get_audio_dir()),
                start_barrier=barrier,
                start_time_ref=shared_start_time,
                email=email,
            )
            self._audio_status_lbl.setText("+ audio")
            self._audio_status_lbl.setStyleSheet(f"color: {config.GREEN};")
        else:
            self._audio_recorder = None
            self._audio_status_lbl.setText("(no system audio)")
            self._audio_status_lbl.setStyleSheet(f"color: {config.MUTED};")

    # ------------------------------------------------------------------
    # Stop
    # ------------------------------------------------------------------

    def stop_both(self):
        """Stop all recorders with a shared stop_time, join threads, then mux."""
        stop_time = time.time()

        for panel in (self._webcam_panel, self._screen_panel):
            recorder = getattr(panel, "recorder", None)
            if recorder and getattr(recorder, "stop", None):
                recorder.stop(stop_time=stop_time)

        if getattr(self, "_audio_recorder", None) and self._audio_recorder.recording:
            self._audio_recorder.stop(stop_time=stop_time)

        self._join_recorders_concurrent(timeout=5.0)

        if getattr(self, "_auto_mux", False):
            self._dispatch_mux()

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

    # ------------------------------------------------------------------
    # Audio status callbacks
    # ------------------------------------------------------------------

    def _on_audio_status(self, status: str, message: str):
        def _():
            self._audio_status_lbl.setText(message[:40] if message else status)

        QtCore.QTimer.singleShot(0, _)

    def _on_audio_done(self, filename: str):
        self._audio_status_lbl.setText("audio saved")
        self._audio_status_lbl.setStyleSheet(f"color: {config.MUTED};")

    # ------------------------------------------------------------------
    # Mux dispatch (frozen exe vs. plain Python)
    # ------------------------------------------------------------------

    def _dispatch_mux(self):
        """Kick off screen+audio muxing in a background thread after stop."""
        email = getattr(self, "_user_email", None)
        audio_rec = getattr(self, "_audio_recorder", None)
        has_audio = bool(audio_rec and getattr(audio_rec, "filename", ""))
        if not (email and has_audio):
            return

        if getattr(sys, "frozen", False):
            t = threading.Thread(target=self._mux_frozen, daemon=True)
        else:
            t = threading.Thread(target=self._mux_cli, args=(email,), daemon=True)
        t.start()

    def _mux_frozen(self):
        """Mux using muxmod directly (PyInstaller frozen exe path)."""
        audio_rec = getattr(self, "_audio_recorder", None)
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
        out_path = out_dir / f"{screen_file.stem}_screen_with_audio{config.VIDEO_EXT}"

        try:
            # Give the screen recorder a little extra time to finish
            # closing the MP4 before probing/muxing.
            time.sleep(5)
            ffmpeg_exe = muxmod._get_ffmpeg_exe()
            if not ffmpeg_exe:
                print("Muxing failed: ffmpeg not found.")
                return
            print(f"Muxing:\n  Video : {screen_file}\n  Audio : {audio_file}")
            ok = muxmod.mux_one(screen_file, audio_file, out_path, ffmpeg_exe)
            print(f"  Done  → {out_path}" if ok else "  Muxing failed.")
        except Exception:
            print("  Muxing failed.")

    def _mux_cli(self, email: str):
        """Mux by calling the CLI helper module (non-frozen Python path)."""
        audio_rec = getattr(self, "_audio_recorder", None)
        screen_recorder = getattr(self._screen_panel, "recorder", None)
        screen_p = (
            getattr(screen_recorder, "filename", "")
            or getattr(self._screen_panel, "_last_file", "")
            or "?"
        )
        audio_p = getattr(audio_rec, "filename", "") if audio_rec else "?"
        out_dir = config.RECORDINGS_DIR / "screen_with_audio"

        try:
            # Small delay so the screen MP4 is fully written before
            # the CLI helper probes and muxes it.
            print("Waiting for screen video to be fully written...")
            time.sleep(60)
            print("Done waiting.")
            cmd = [sys.executable, "-m", "recorder.audio.mux_audio_into_video", "--screen-only", email]
            print(f"Muxing:\n  Video : {screen_p}\n  Audio : {audio_p}")
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            result_files = sorted(
                out_dir.glob("*_screen_with_audio.mp4"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            saved = result_files[0] if result_files else out_dir
            print(f"  Done  → {saved}")
        except Exception:
            print("  Muxing failed.")
