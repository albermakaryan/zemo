"""RecordingMixin: record_both, stop_both, mux dispatch, audio callbacks."""

import csv
import sys
import subprocess
import time
import threading
from pathlib import Path

from PySide6 import QtCore, QtWidgets

from recorder import config
from recorder.audio import InternalAudioRecorder, is_loopback_available
from recorder.audio import mux_audio_into_video as muxmod

from recorder.common import email_filename_part, unique_name_with_suffix
from recorder.ui.dialogs import SettingsDialog,ask_university_email
from gazer import EyeTracker


class RecordingMixin:
    """Mixin that owns all recording-action logic for the App window."""

    def _any_recording(self) -> bool:
        for panel in (self._webcam_panel, self._screen_panel):
            r = getattr(panel, "recorder", None)
            if r and getattr(r, "recording", False):
                return True
        a = getattr(self, "_audio_recorder", None)
        return bool(a and getattr(a, "recording", False))

    def _refresh_settings_button_state(self) -> None:
        btn = getattr(self, "_btn_settings", None)
        if not btn:
            return
        btn.setEnabled(not self._any_recording())

    def _apply_persisted_fps(self, v: int) -> None:
        v = max(config.FPS_MIN, min(config.FPS_MAX, int(v)))
        old = int(config.FPS)
        config.FPS = v
        s = QtCore.QSettings(config.QSETTINGS_ORG, config.QSETTINGS_APP)
        s.setValue("recording/fps", v)
        s.sync()
        self._update_fps_status_label()
        if self._any_recording():
            return
        if old != v:
            self._restart_previews_for_fps()

    def _open_settings(self) -> None:
        if self._any_recording():
            return
        dlg = SettingsDialog(self, config.FPS)
        dlg.setMinimumWidth(400)
        if self.frameGeometry().isValid():
            g = self.frameGeometry()
            dlg.move(g.center() - dlg.rect().center())
        if dlg.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return
        self._apply_persisted_fps(dlg.saved_fps)

    def _restart_previews_for_fps(self) -> None:
        for panel in (self._webcam_panel, self._screen_panel):
            r = getattr(panel, "recorder", None)
            if r and getattr(r, "stop", None):
                r.stop()
        self._join_recorders_concurrent(timeout=3.0)
        for panel in (self._webcam_panel, self._screen_panel):
            panel.recorder = None
        self._start_previews()

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
        # Gaze check happens first — before email prompt or anything else.
        if not self._gaze_ready_or_prompt():
            return

        email = self.get_recording_email()
        if not email:
            return

        # ---------------- Gaze setup (BEFORE recorders start) ----------------
        # The callback MUST be attached on the webcam recorder before the
        # preview→recording transition fires the synchronization barrier;
        # otherwise the first several seconds of frames are written to the
        # MP4 without any corresponding gaze rows. During preview the
        # callback is a no-op (it checks ``is_recording``), so attaching
        # early is safe.
        self._gaze_csv_file = None
        self._gaze_csv_writer = None
        self._eye_tracker = None
        gaze_enabled = (
            getattr(self, "_chk_gaze", None) is not None
            and self._chk_gaze.isChecked()
            and EyeTracker.is_model_saved()
        )
        if gaze_enabled:
            try:
                self._eye_tracker = EyeTracker()
                webcam_recorder = getattr(self._webcam_panel, "recorder", None)
                gaze_dir = config.RECORDINGS_DIR / config.GAZE_SUBDIR
                gaze_dir.mkdir(parents=True, exist_ok=True)

                # Predict the webcam filename using the same logic
                # ``WebcamRecorderCore.begin_recording`` will use, so the gaze
                # CSV name and the ``video_id`` column match the eventual
                # MP4 filename. Calling ``unique_name_with_suffix`` here does
                # not create any file, and ``begin_recording`` will get the
                # same result when it runs a moment later.
                webcam_dir = config.get_webcam_dir()
                webcam_dir.mkdir(parents=True, exist_ok=True)
                base = email_filename_part(email) if email else "user"
                predicted = unique_name_with_suffix(
                    webcam_dir, base, f"_webcam{config.VIDEO_EXT}"
                )
                predicted_stem = predicted.stem  # e.g. "alber@gmail.com_1_webcam"
                if "_webcam" in predicted_stem:
                    video_id = predicted_stem[: predicted_stem.rfind("_webcam")]
                else:
                    video_id = email

                csv_path = gaze_dir / f"{video_id}_gaze.csv"
                self._gaze_csv_file = open(csv_path, "w", newline="")
                self._gaze_csv_writer = csv.writer(self._gaze_csv_file)
                self._gaze_csv_writer.writerow(["video_id", "frame_id", "minute", "second", "x", "y"])
                frame_counter = [0]
                start_elapsed = [None]
                last_gaze = [None, None]

                def _gaze_on_frame_written(frame, elapsed, is_padding=False):
                    # Called from webcam only immediately after each out.write (encoded frame).
                    if self._gaze_csv_writer is None:
                        return
                    if not is_padding:
                        x, y = self._eye_tracker.track_eyes(frame)
                        last_gaze[0], last_gaze[1] = x, y
                    else:
                        x, y = last_gaze[0], last_gaze[1]
                    if start_elapsed[0] is None:
                        start_elapsed[0] = elapsed
                    relative = int(elapsed - start_elapsed[0])
                    self._gaze_csv_writer.writerow(
                        [video_id, frame_counter[0], relative // 60, relative % 60, x, y]
                    )
                    frame_counter[0] += 1

                if webcam_recorder is not None:
                    webcam_recorder.set_on_frame_written(_gaze_on_frame_written)
                self._gaze_status_lbl.setText("+ gaze")
                self._gaze_status_lbl.setStyleSheet(f"color: {config.GREEN};")
                self._btn_calibrate.setEnabled(False)
            except Exception as exc:
                self._gaze_status_lbl.setText("gaze error")
                self._gaze_status_lbl.setStyleSheet(f"color: {config.RED};")
                print(f"Gaze tracking init failed: {exc}")
                self._eye_tracker = None
                if self._gaze_csv_file:
                    self._gaze_csv_file.close()
                    self._gaze_csv_file = None
                self._gaze_csv_writer = None

        # ---------------- Start recorders ----------------
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

        self._refresh_settings_button_state()
    def _gaze_ready_or_prompt(self) -> bool:
        """Return True if recording can proceed. If gaze is on but model is missing,
        show a popup and return False so the caller aborts the start."""
        gaze_on = (
            getattr(self, "_chk_gaze", None) is not None
            and self._chk_gaze.isChecked()
        )
        if not gaze_on or EyeTracker.is_model_saved():
            return True

        from PySide6 import QtWidgets

        msg = QtWidgets.QMessageBox(self)
        msg.setWindowTitle("Gaze Tracking — No Calibration Model")
        msg.setText("Gaze tracking is enabled but no calibration model was found.")
        msg.setInformativeText(
            "You can calibrate first using the Calibrate button, "
            "or continue recording with gaze tracking disabled."
        )
        btn_continue = msg.addButton(
            "Continue without gaze", QtWidgets.QMessageBox.ButtonRole.AcceptRole
        )
        msg.addButton("Cancel", QtWidgets.QMessageBox.ButtonRole.RejectRole)
        msg.setDefaultButton(btn_continue)
        msg.exec()

        if msg.clickedButton() == btn_continue:
            self._chk_gaze.setChecked(False)
            self._update_gaze_indicator(False)
            return True
        return False

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
        self._refresh_settings_button_state()

        # Detach gaze callback only after the thread has fully finished —
        # including the padding-frame writes in the finally block.
        webcam_recorder = getattr(self._webcam_panel, "recorder", None)
        if webcam_recorder is not None:
            webcam_recorder.set_on_frame_written(None)

        self._flush_gaze_csv()

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
    # Gaze tracking
    # ------------------------------------------------------------------

    def _flush_gaze_csv(self):
        """Close the gaze CSV file that was written row-by-row during recording."""
        # Re-enable calibrate button and clear status regardless of outcome
        if getattr(self, "_btn_calibrate", None) is not None:
            self._btn_calibrate.setEnabled(True)
        if getattr(self, "_gaze_status_lbl", None) is not None:
            self._gaze_status_lbl.setText("")

        self._eye_tracker = None
        self._gaze_csv_writer = None

        f = getattr(self, "_gaze_csv_file", None)
        if f is not None:
            try:
                f.close()
                print(f"Gaze data saved → {f.name}")
            except Exception as exc:
                print(f"Gaze CSV close failed: {exc}")
            self._gaze_csv_file = None

    def _on_calibrate_clicked(self):
        """Stop webcam preview, run Lissajous calibration, then restart preview."""
        self._btn_calibrate.setEnabled(False)
        self._btn_calibrate.setText("Calibrating…")

        float_win = getattr(self, "_float_win", None)
        if float_win is not None:
            float_win.hide()

        # Stop the webcam recorder so its VideoCapture releases the camera
        # before eyetrax opens its own capture for calibration.
        webcam_panel = getattr(self, "_webcam_panel", None)
        old_recorder = getattr(webcam_panel, "recorder", None) if webcam_panel else None
        if old_recorder is not None:
            old_recorder.stop()
            webcam_panel.recorder = None

        def _calibrate():
            # Wait for the old capture to be fully released before calibration opens it.
            if old_recorder is not None:
                old_recorder.join(timeout=2.0)
            try:
                # Run calibration in a subprocess so that cv2.imshow / cv2.waitKey /
                # cv2.destroyAllWindows execute on that process's main thread.
                # On Windows, OpenCV GUI calls hang when called from a non-main thread
                # (they wait for Win32 messages that never arrive), so a subprocess is
                # the only reliable way to run the calibration window from here.
                # PyInstaller: sys.executable is the .exe — ``-c`` is ignored, spawns a second GUI.
                if getattr(sys, "frozen", False):
                    cmd = [sys.executable, "--calibrate-only"]
                else:
                    cmd = [
                        sys.executable,
                        "-c",
                        "from gazer import EyeTracker; EyeTracker.calibrate_and_create()",
                    ]
                subprocess.run(cmd, check=False, cwd=str(config.PROJECT_ROOT))
            except Exception as exc:
                print(f"Calibration failed: {exc}")
            # Emit a Qt signal (thread-safe) to notify the main thread.
            self._calibration_finished.emit()

        threading.Thread(target=_calibrate, daemon=True).start()

    def _on_calibration_done(self):
        """Called on the main thread after calibration finishes."""
        # Restart webcam preview now that the camera is free again
        webcam_panel = getattr(self, "_webcam_panel", None)
        if webcam_panel is not None and webcam_panel.recorder is None:
            webcam_panel._start_preview()

        model_exists = EyeTracker.is_model_saved()
        self._btn_calibrate.setEnabled(True)
        self._btn_calibrate.setText("Re-calibrate Eyes" if model_exists else "Calibrate Eyes")
        self._chk_gaze.setEnabled(True)
        if model_exists:
            self._chk_gaze.setChecked(True)
            self._chk_gaze.setToolTip("")
            self._gaze_status_lbl.setText("model ready")
            self._gaze_status_lbl.setStyleSheet(f"color: {config.GREEN};")
        else:
            self._chk_gaze.setToolTip("Calibrate first to enable gaze tracking")
        self._update_gaze_indicator(self._chk_gaze.isChecked())

        float_win = getattr(self, "_float_win", None)
        if float_win is not None:
            float_win.show()

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
