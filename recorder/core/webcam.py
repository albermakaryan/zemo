"""
Core webcam recorder (backend-only, no UI toolkit imports).

Reusable by different frontends (PySide GUI, CLI tools, tests).
"""

from pathlib import Path
import sys
import threading
import time

import cv2

from recorder import config
from recorder.common import (
    create_writer,
    email_filename_part,
    make_even,
    resize_frame,
    unique_name_with_suffix,
)


def _try_open_capture(idx: int):
    """
    Open camera at index. On Windows, try DirectShow first (usually not mirrored), then MSMF.
    Returns ``(cap, api_name)``; on failure ``cap`` is None and ``api_name`` is ``""``.
    """
    if sys.platform == "win32":
        if hasattr(cv2, "CAP_DSHOW"):
            cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
            if cap.isOpened():
                return cap, "dshow"
            cap.release()
        if hasattr(cv2, "CAP_MSMF"):
            cap = cv2.VideoCapture(idx, cv2.CAP_MSMF)
            if cap.isOpened():
                return cap, "msmf"
            cap.release()
        cap = cv2.VideoCapture(idx)
        if cap.isOpened():
            return cap, "default"
        cap.release()
        return None, ""
    cap = cv2.VideoCapture(idx)
    if cap.isOpened():
        return cap, "default"
    cap.release()
    return None, ""


def _effective_horizontal_flip(api_name: str) -> bool:
    """
    Whether to apply cv2.flip(..., 1) after each captured frame.

    Config WEBCAM_FLIP_HORIZONTAL:
      True  -> always flip
      False -> never flip
      "auto" -> flip when we expect a mirrored stream from the driver:
                Windows (dshow / msmf / default backend for this app): yes
                Linux / macOS (V4L2 / AVFoundation via default OpenCV capture): no
                If preview is still reversed on those OSes, set True in config.
    """
    v = config.WEBCAM_FLIP_HORIZONTAL
    if v is True:
        return True
    if v is False:
        return False
    if v == "auto":
        if sys.platform == "win32" and api_name in ("dshow", "msmf", "default"):
            return True
        return False
    return False


class WebcamRecorderCore:
    """Webcam recording in a background thread using OpenCV."""

    def __init__(self, on_frame, on_status, on_done):
        self.on_frame = on_frame
        self.on_status = on_status
        self.on_done = on_done
        self._stop = threading.Event()
        self._stop_time = None
        self._thread = None
        self.recording = False
        self.filename = ""
        self._pending_recording = None  # (save_dir, barrier, email)
        self._overlay_callback = None

    def set_overlay_callback(self, callback):
        self._overlay_callback = callback

    def start_preview(self):
        self._stop.clear()
        self._pending_recording = None
        self._thread = threading.Thread(target=self._run, args=(True,), daemon=True)
        self._thread.start()

    def begin_recording(self, save_dir, start_barrier=None, email=None):
        save_path = Path(save_dir)
        save_path.mkdir(parents=True, exist_ok=True)
        (save_path / ".gitkeep").touch(exist_ok=True)
        base = email_filename_part(email) if email else "user"
        candidate = unique_name_with_suffix(
            save_path, base, f"_webcam{config.VIDEO_EXT}"
        )
        self.filename = str(candidate)
        self.recording = True
        self._pending_recording = (str(save_dir), start_barrier, email)

    def start(self, save_dir, start_barrier=None, email=None):
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
        self._stop_time = stop_time
        self._stop.set()
        self.recording = False

    def join(self, timeout: float = 3.0) -> None:
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)

    def _run(self, preview_only, save_dir=None, start_barrier=None, email=None):
        cap = None
        indices_to_try = [config.CAMERA_INDEX]
        for i in range(5):
            if i not in indices_to_try:
                indices_to_try.append(i)
        api_name = ""
        for idx in indices_to_try:
            cap, api_name = _try_open_capture(idx)
            if cap is not None and cap.isOpened():
                break
            cap = None
            api_name = ""
        if cap is None or not cap.isOpened():
            self.on_status(
                "error",
                "No webcam found (tried indices 0–4). Check /dev/video* or camera permissions.",
            )
            return

        flip_h = _effective_horizontal_flip(api_name)

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
                if flip_h:
                    frame = cv2.flip(frame, 1)
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

