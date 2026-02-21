"""
Screen recording in a background thread. Uses mss; catch-up and fill logic for smooth, correct duration.
"""

import threading
import time
from pathlib import Path

import cv2
import numpy as np
import mss

from recorder import config
from recorder.common import (
    create_writer,
    make_even,
    resize_frame,
    sanitize_email_for_filename,
    timestamp,
)


class ScreenRecorder:
    """
    Screen recording via mss. Uses np.array + cvtColor for reliable playback.
    Catch-up cap and fill keep duration correct and reduce duplicate frames.
    """
    def __init__(self, on_frame, on_status, on_done):
        self.on_frame = on_frame
        self.on_status = on_status
        self.on_done = on_done
        self._stop = threading.Event()
        self._stop_time = None  # optional shared stop timestamp from app
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
        self.filename = str(save_path / f"{prefix}screen_{timestamp()}{config.VIDEO_EXT}")
        self._thread = threading.Thread(target=self._run, args=(save_dir,), daemon=True)
        self._thread.start()

    def stop(self, stop_time=None):
        self._stop_time = stop_time  # set before signaling so _run finally sees it
        self._stop.set()
        self.recording = False

    def join(self, timeout: float = 3.0) -> None:
        """Wait for the recording thread to finish (so VideoWriter is released)."""
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)

    def _run(self, save_dir):
        with mss.mss() as sct:
            monitor = sct.monitors[config.MONITOR_INDEX]
            w = make_even(monitor["width"])
            h = make_even(monitor["height"])
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
                self.recording = False
                return
            self.on_status("recording", f"→ {Path(self.filename).name}")
            if self._start_barrier is not None:
                self._start_barrier.wait()
            t0 = time.time()
            frame_count = 0
            last_bgr = None
            max_catchup_frames = max(1, config.SCREEN_CATCHUP_FRAMES)
            frame_interval = 1.0 / config.FPS
            try:
                next_write_time = t0
                while not self._stop.is_set():
                    t_now = time.time()
                    catchup = 0
                    # Single catch-up loop: cap applies to fresh grabs; fill uses last_bgr; advance one slot per iter
                    while next_write_time <= t_now:
                        if catchup < max_catchup_frames:
                            try:
                                img = sct.grab(monitor)
                                frame = cv2.cvtColor(np.array(img), cv2.COLOR_BGRA2BGR)
                                if (frame.shape[1], frame.shape[0]) != (w, h):
                                    frame = cv2.resize(frame, (w, h))
                                out.write(frame)
                                frame_count += 1
                                next_write_time += frame_interval
                                catchup += 1
                                last_bgr = frame
                                if frame_count % 4 == 0:
                                    preview = resize_frame(frame, config.PREVIEW_W, config.PREVIEW_H)
                                    self.on_frame(preview, time.time() - t0)
                                continue
                            except Exception:
                                pass
                        # Fill slot: use last_bgr or black frame so we always advance (avoid tight loop)
                        if last_bgr is not None:
                            out.write(last_bgr)
                        else:
                            black = np.zeros((h, w, 3), dtype=np.uint8)
                            out.write(black)
                            last_bgr = black
                        frame_count += 1
                        next_write_time += frame_interval
                        catchup += 1
                    sleep_until = next_write_time - time.time()
                    if sleep_until > 0.002:
                        time.sleep(sleep_until)
            finally:
                # Pad by real elapsed time (t0..t_final), not synthetic next_write_time, so no drift
                t_final = getattr(self, "_stop_time", None) or time.time()
                elapsed = t_final - t0
                expected_frames = int(elapsed * config.FPS)
                frames_missing = expected_frames - frame_count
                if last_bgr is not None and frames_missing > 0:
                    for _ in range(frames_missing):
                        out.write(last_bgr)
                out.release()
                self.recording = False
                self.on_done(self.filename)
