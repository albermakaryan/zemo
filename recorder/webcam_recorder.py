"""
Webcam recording in a background thread. Uses OpenCV VideoCapture; frame pacing for real-time playback.
"""

import sys
import threading
import time
from pathlib import Path

import cv2

from recorder import config
from recorder.common import (
    create_writer,
    email_filename_part,
    make_even,
    resize_frame,
    unique_name_with_suffix,
)


class WebcamRecorder:
    def __init__(self, on_frame, on_status, on_done):
        self.on_frame = on_frame
        self.on_status = on_status
        self.on_done = on_done
        self._stop = threading.Event()
        self._stop_time = None
        self._thread = None
        self.recording = False
        self.filename = ""
        self._pending_recording = (
            None  # (save_dir, barrier, email) when user clicks Record
        )
        self._overlay_callback = None  # optional callback(frame, elapsed_s) — draws on frame in place for preview

    def set_overlay_callback(self, callback):
        """Set or clear optional overlay. Callback(frame, elapsed_s, is_recording) draws on frame in place; CSV should be written only when is_recording is True."""
        self._overlay_callback = callback

    def start_preview(self):
        """Start capture thread in preview-only mode (no file). Call begin_recording() later to start writing."""
        self._stop.clear()
        self._pending_recording = None
        self._thread = threading.Thread(target=self._run, args=(True,), daemon=True)
        self._thread.start()

    def begin_recording(self, save_dir, start_barrier=None, email=None):
        """Switch from preview to recording (called after countdown)."""
        save_path = Path(save_dir)
        save_path.mkdir(parents=True, exist_ok=True)
        (save_path / ".gitkeep").touch(exist_ok=True)
        base = email_filename_part(email) if email else "user"
        # email_webcam.mp4, email_1_webcam.mp4, email_2_webcam.mp4, ...
        candidate = unique_name_with_suffix(
            save_path, base, f"_webcam{config.VIDEO_EXT}"
        )
        self.filename = str(candidate)
        self.recording = True
        self._pending_recording = (str(save_dir), start_barrier, email)

    def start(self, save_dir, start_barrier=None, email=None):
        """Start directly in recording mode (legacy)."""
        self._stop.clear()
        self._pending_recording = None
        self.recording = True
        save_path = Path(save_dir)
        save_path.mkdir(parents=True, exist_ok=True)
        (save_path / ".gitkeep").touch(exist_ok=True)
        base = email_filename_part(email) if email else "user"
        candidate = unique_name_with_suffix(
            save_path, base, f"_webcam{config.VIDEO_EXT}"
        )
        self.filename = str(candidate)
        self._thread = threading.Thread(
            target=self._run, args=(False, save_dir, start_barrier, email), daemon=True
        )
        self._thread.start()

    def stop(self, stop_time=None):
        # Set stop_time before signaling thread so finally block sees it (no race)
        self._stop_time = stop_time
        self._stop.set()
        self.recording = False

    def join(self, timeout: float = 3.0) -> None:
        """Wait for the recording thread to finish (so VideoWriter is released)."""
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)

    def _run(self, preview_only, save_dir=None, start_barrier=None, email=None):
        cap = None
        # Try config index first, then 0, 1, 2, ... (some systems expose camera on different indices)
        indices_to_try = [config.CAMERA_INDEX]
        for i in range(5):
            if i not in indices_to_try:
                indices_to_try.append(i)
        for idx in indices_to_try:
            if sys.platform == "win32" and hasattr(cv2, "CAP_MSMF"):
                cap = cv2.VideoCapture(idx, cv2.CAP_MSMF)
            else:
                cap = cv2.VideoCapture(idx)
            if cap is not None and cap.isOpened():
                break
            if cap is not None:
                cap.release()
                cap = None
        if cap is None or not cap.isOpened():
            self.on_status(
                "error",
                "No webcam found (tried indices 0–4). Check /dev/video* or camera permissions.",
            )
            return

        src_w = make_even(int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)))
        src_h = make_even(int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)))
        if config.RECORDING_WIDTH is not None and config.RECORDING_HEIGHT is not None:
            w, h = make_even(config.RECORDING_WIDTH), make_even(config.RECORDING_HEIGHT)
        else:
            w, h = src_w, src_h

        out = None
        t0 = time.time()
        frame_count = 0
        frame = None
        next_write_time = t0
        frame_interval = 1.0 / config.FPS

        if not preview_only and save_dir:
            for fourcc_str in config.VIDEO_FOURCC_TRY_ORDER:
                out, ok = create_writer(self.filename, fourcc_str, config.FPS, w, h)
                if ok:
                    break
                if out:
                    out.release()
                    out = None
            if not out or not out.isOpened():
                self.on_status("error", "Failed to create MP4 writer")
                cap.release()
                return
            self.on_status("recording", f"→ {Path(self.filename).name}")
            if start_barrier is not None:
                start_barrier.wait()
            t0 = time.time()
            next_write_time = t0

        try:
            while not self._stop.is_set():
                # If preview mode and pending recording, create writer and sync
                if preview_only and self._pending_recording is not None:
                    save_dir, barrier, email = self._pending_recording
                    self._pending_recording = None
                    for fourcc_str in config.VIDEO_FOURCC_TRY_ORDER:
                        out, ok = create_writer(
                            self.filename, fourcc_str, config.FPS, w, h
                        )
                        if ok:
                            break
                        if out:
                            out.release()
                            out = None
                    if not out or not out.isOpened():
                        self.on_status("error", "Failed to create MP4 writer")
                        break
                    self.on_status("recording", f"→ {Path(self.filename).name}")
                    if barrier is not None:
                        barrier.wait()
                    t0 = time.time()
                    frame_count = 0
                    next_write_time = t0
                    preview_only = False

                if not preview_only and out is None:
                    break

                ret, frame = cap.read()
                if not ret:
                    time.sleep(0.01)
                    continue
                if (frame.shape[1], frame.shape[0]) != (w, h):
                    frame = cv2.resize(frame, (w, h))
                elapsed = time.time() - t0 if out else 0
                if out is not None:
                    t_now = time.time()
                    if next_write_time <= t_now:
                        out.write(frame)
                        frame_count += 1
                        next_write_time += frame_interval
                    sleep_until = next_write_time - time.time()
                    if sleep_until > 0.002:
                        time.sleep(sleep_until)
                if self._overlay_callback is not None:
                    try:
                        self._overlay_callback(frame, elapsed, self.recording)
                    except Exception:
                        pass
                preview = resize_frame(frame, config.PREVIEW_W, config.PREVIEW_H)
                self.on_frame(preview, elapsed)
        finally:
            if out is not None:
                t_final = getattr(self, "_stop_time", None) or time.time()
                elapsed = t_final - t0
                expected_frames = int(elapsed * config.FPS)
                frames_missing = expected_frames - frame_count
                if frame is not None and frames_missing > 0:
                    for _ in range(frames_missing):
                        out.write(frame)
                out.release()
                self.on_done(self.filename)
            cap.release()
            self.recording = False
