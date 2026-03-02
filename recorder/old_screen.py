"""
Screen recording in a background thread. Uses dxcam (Windows) when available,
else mss; one frame per interval for smooth, real-time sync.
"""

import sys
import threading
import time
from pathlib import Path

import cv2
import numpy as np

from recorder import config
from recorder.common import (
    create_writer,
    email_filename_part,
    make_even,
    resize_frame,
)

_dxcam = None


def _dxcam_module():
    """Return dxcam module if available (Windows), else None. Prefer dxcam_cpp to avoid
    pure-Python dxcam SetWaitableTimer ctypes bug on some Python versions."""
    global _dxcam
    if _dxcam is not None:
        return _dxcam
    if sys.platform != "win32":
        return None
    try:
        import dxcam_cpp as dxcam
        _dxcam = dxcam
        return _dxcam
    except ImportError:
        try:
            import dxcam
            _dxcam = dxcam
            return _dxcam
        except ImportError:
            return None


class ScreenRecorder:
    """
    Screen recording via dxcam (Windows) or mss. One frame per time slot so
    playback matches real time. Uses same API as drafts/dxcam_recorder.py.
    """
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
        name_part = email_filename_part(email) if email else "user"
        self.filename = str(save_path / f"{name_part}_screen{config.VIDEO_EXT}")
        self._thread = threading.Thread(target=self._run, args=(save_dir,), daemon=True)
        self._thread.start()

    def stop(self, stop_time=None):
        self._stop_time = stop_time
        self._stop.set()
        self.recording = False

    def join(self, timeout: float = 3.0) -> None:
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)

    def _run(self, save_dir):
        if _dxcam_module() is not None:
            self._run_dxcam(save_dir)
        else:
            self._run_mss(save_dir)

    def _run_dxcam(self, save_dir):
        """Capture using dxcam (DirectX Desktop Duplication), like drafts/dxcam_recorder.py."""
        dxcam = _dxcam_module()
        camera = None
        out = None
        t0 = time.time()
        last_bgr = None
        w = h = 0
        try:
            output_idx = max(0, config.MONITOR_INDEX - 1)
            camera = dxcam.create(output_color="BGR", output_idx=output_idx)
            camera.start(target_fps=config.FPS)
            # Get dimensions from first frame
            for _ in range(100):
                if self._stop.is_set():
                    return
                frame = camera.get_latest_frame()
                if frame is not None:
                    h, w = frame.shape[:2]
                    w = make_even(w)
                    h = make_even(h)
                    if (frame.shape[1], frame.shape[0]) != (w, h):
                        frame = cv2.resize(frame, (w, h))
                    last_bgr = frame.copy()
                    break
                time.sleep(0.02)
            if last_bgr is None:
                self.on_status("error", "dxcam: no frame (fallback to mss)")
                self._run_mss(save_dir)
                return
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
            self.on_status("recording", f"→ {Path(self.filename).name} (dxcam)")
            if self._start_barrier is not None:
                self._start_barrier.wait()
            t0 = time.time()
            frame_count = 0
            frame_interval = 1.0 / config.FPS
            next_write_time = t0
            while not self._stop.is_set():
                sleep_until = next_write_time - time.time()
                if sleep_until > 0.002:
                    time.sleep(sleep_until)
                if self._stop.is_set():
                    break
                t_now = time.time()
                if next_write_time <= t_now:
                    frame = camera.get_latest_frame()
                    if frame is None:
                        frame = last_bgr
                    else:
                        if (frame.shape[1], frame.shape[0]) != (w, h):
                            frame = cv2.resize(frame, (w, h))
                        last_bgr = frame
                    try:
                        out.write(frame)
                    except Exception:
                        if last_bgr is not None:
                            out.write(last_bgr)
                        else:
                            out.write(np.zeros((h, w, 3), dtype=np.uint8))
                    frame_count += 1
                    next_write_time += frame_interval
                    preview = resize_frame(frame, config.PREVIEW_W, config.PREVIEW_H)
                    self.on_frame(preview, time.time() - t0)
        finally:
            t_final = getattr(self, "_stop_time", None) or time.time()
            if out is not None:
                elapsed = t_final - t0
                expected_frames = int(elapsed * config.FPS)
                frames_missing = expected_frames - frame_count
                if last_bgr is not None and frames_missing > 0:
                    for _ in range(frames_missing):
                        out.write(last_bgr)
                out.release()
            # Avoid COM access violation: stop capture but do not release/delete camera
            if camera is not None:
                try:
                    camera.stop()
                except Exception:
                    pass
            self.recording = False
            self.on_done(self.filename)

    def _run_mss(self, save_dir):
        """Fallback when dxcam not available."""
        import mss
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
            frame_interval = 1.0 / config.FPS
            try:
                next_write_time = t0
                while not self._stop.is_set():
                    sleep_until = next_write_time - time.time()
                    if sleep_until > 0.002:
                        time.sleep(sleep_until)
                    if self._stop.is_set():
                        break
                    t_now = time.time()
                    if next_write_time <= t_now:
                        try:
                            img = sct.grab(monitor)
                            frame = cv2.cvtColor(np.array(img), cv2.COLOR_BGRA2BGR)
                            if (frame.shape[1], frame.shape[0]) != (w, h):
                                frame = cv2.resize(frame, (w, h))
                            out.write(frame)
                            frame_count += 1
                            next_write_time += frame_interval
                            last_bgr = frame
                            preview = resize_frame(frame, config.PREVIEW_W, config.PREVIEW_H)
                            self.on_frame(preview, time.time() - t0)
                        except Exception:
                            if last_bgr is not None:
                                out.write(last_bgr)
                            else:
                                black = np.zeros((h, w, 3), dtype=np.uint8)
                                out.write(black)
                                last_bgr = black
                            frame_count += 1
                            next_write_time += frame_interval
            finally:
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
