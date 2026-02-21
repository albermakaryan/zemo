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
    make_even,
    resize_frame,
    sanitize_email_for_filename,
    timestamp,
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

    def start(self, save_dir, start_barrier=None, email=None):
        self._stop.clear()
        self._start_barrier = start_barrier
        self.recording = True
        save_path = Path(save_dir)
        save_path.mkdir(parents=True, exist_ok=True)
        prefix = f"{sanitize_email_for_filename(email)}_" if email else ""
        self.filename = str(save_path / f"{prefix}webcam_{timestamp()}{config.VIDEO_EXT}")
        self._thread = threading.Thread(target=self._run, args=(save_dir,), daemon=True)
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

    def _run(self, save_dir):
        if sys.platform == "win32" and hasattr(cv2, "CAP_MSMF"):
            cap = cv2.VideoCapture(config.CAMERA_INDEX, cv2.CAP_MSMF)
        else:
            cap = None
        if cap is None or not cap.isOpened():
            if cap is not None:
                cap.release()
            cap = cv2.VideoCapture(config.CAMERA_INDEX)
        if not cap.isOpened():
            self.on_status("error", "Cannot open webcam")
            self.recording = False
            return

        w = make_even(int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)))
        h = make_even(int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)))
        out = None
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
            self.recording = False
            return
        self.on_status("recording", f"→ {Path(self.filename).name}")
        if getattr(self, "_start_barrier", None) is not None:
            self._start_barrier.wait()
        t0 = time.time()
        frame_count = 0
        frame = None
        try:
            next_write_time = t0
            ret = True
            while not self._stop.is_set():
                t_now = time.time()
                while next_write_time <= t_now:
                    ret, frame = cap.read()
                    if not ret:
                        break
                    if (frame.shape[1], frame.shape[0]) != (w, h):
                        frame = cv2.resize(frame, (w, h))
                    out.write(frame)
                    frame_count += 1
                    next_write_time += 1.0 / config.FPS
                    preview = resize_frame(frame, config.PREVIEW_W, config.PREVIEW_H)
                    self.on_frame(preview, time.time() - t0)
                if not ret:
                    break
                sleep_until = next_write_time - time.time()
                if sleep_until > 0.002:
                    time.sleep(sleep_until)
        finally:
            # Pad by real elapsed time (t0..t_final), not synthetic next_write_time, so no drift
            t_final = getattr(self, "_stop_time", None) or time.time()
            elapsed = t_final - t0
            expected_frames = int(elapsed * config.FPS)
            frames_missing = expected_frames - frame_count
            if frame is not None and frames_missing > 0:
                for _ in range(frames_missing):
                    out.write(frame)
            cap.release()
            out.release()
            self.recording = False
            self.on_done(self.filename)
