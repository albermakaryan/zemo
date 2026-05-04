"""
Core screen recorder (backend-only, no UI toolkit imports).

Reusable from different frontends (PySide GUI, CLI tools, tests).
"""

from pathlib import Path
import sys
import threading
import time

import cv2
import numpy as np

from recorder import config
from recorder.common import (
    create_writer,
    email_filename_part,
    make_even,
    resize_frame,
    unique_name_with_suffix,
)

_dxcam = None


def _dxcam_module():
    """Return dxcam module if available (Windows), else None."""
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


class ScreenRecorderCore:
    """Screen recording via dxcam (Windows) or mss in a background thread."""

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
        self._start_barrier = None
        self._on_frame_written = None

    def set_on_frame_written(self, callback):
        """Register ``callback(frame, elapsed, is_padding)`` after each encoded frame."""
        self._on_frame_written = callback

    def start_preview(self):
        self._stop.clear()
        self._pending_recording = None
        self._thread = threading.Thread(
            target=self._run, args=(True, None, None, None), daemon=True
        )
        self._thread.start()

    def begin_recording(self, save_dir, start_barrier=None, email=None):
        save_path = Path(save_dir)
        save_path.mkdir(parents=True, exist_ok=True)
        (save_path / ".gitkeep").touch(exist_ok=True)
        base = email_filename_part(email) if email else "user"
        self.filename = str(unique_name_with_suffix(save_path, base, f"_screen{config.VIDEO_EXT}"))
        self.recording = True
        self._pending_recording = (str(save_dir), start_barrier, email)

    def start(self, save_dir, start_barrier=None, email=None):
        self._stop.clear()
        self._pending_recording = None
        self._start_barrier = start_barrier
        self.recording = True
        save_path = Path(save_dir)
        save_path.mkdir(parents=True, exist_ok=True)
        (save_path / ".gitkeep").touch(exist_ok=True)
        base = email_filename_part(email) if email else "user"
        self.filename = str(unique_name_with_suffix(save_path, base, f"_screen{config.VIDEO_EXT}"))
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

    # ── capture backend helpers ────────────────────────────────────────────────

    def _make_dxcam_capture(self):
        """Return (grab, w, h, cleanup) for dxcam, or None if no frame arrives."""
        dxcam = _dxcam_module()
        camera = dxcam.create(output_color="BGR", output_idx=max(0, config.MONITOR_INDEX - 1))
        camera.start(target_fps=int(config.FPS))
        frame = None
        for _ in range(100):
            if self._stop.is_set():
                break
            frame = camera.get_latest_frame()
            if frame is not None:
                break
            time.sleep(0.02)
        if frame is None:
            try:
                camera.stop()
            except Exception:
                pass
            return None
        nat_h, nat_w = frame.shape[:2]
        if config.RECORDING_WIDTH and config.RECORDING_HEIGHT:
            w, h = make_even(config.RECORDING_WIDTH), make_even(config.RECORDING_HEIGHT)
        else:
            w, h = make_even(nat_w), make_even(nat_h)

        def cleanup():
            try:
                camera.stop()
            except Exception:
                pass

        return camera.get_latest_frame, w, h, cleanup

    def _make_mss_capture(self):
        """Return (grab, w, h, cleanup) for mss."""
        import mss
        sct = mss.mss()
        monitor = sct.monitors[config.MONITOR_INDEX]
        # Use actual grab dimensions (not monitor dict) so DPI scaling doesn't cause mismatch.
        probe = cv2.cvtColor(np.array(sct.grab(monitor)), cv2.COLOR_BGRA2BGR)
        nat_h, nat_w = probe.shape[:2]
        if config.RECORDING_WIDTH and config.RECORDING_HEIGHT:
            w, h = make_even(config.RECORDING_WIDTH), make_even(config.RECORDING_HEIGHT)
        else:
            w, h = make_even(nat_w), make_even(nat_h)

        def grab():
            try:
                return cv2.cvtColor(np.array(sct.grab(monitor)), cv2.COLOR_BGRA2BGR)
            except Exception:
                return None

        return grab, w, h, sct.close

    def _open_writer(self, w: int, h: int, label: str = ""):
        for fourcc_str in config.VIDEO_FOURCC_TRY_ORDER:
            out, ok = create_writer(self.filename, fourcc_str, config.FPS, w, h)
            if ok:
                suffix = f" ({label})" if label else ""
                self.on_status("recording", f"→ {Path(self.filename).name}{suffix}")
                return out
            if out:
                out.release()
        self.on_status("error", "Failed to create MP4 writer")
        self.recording = False
        return None

    # ── main thread ────────────────────────────────────────────────────────────

    def _run(self, preview_only, save_dir=None, start_barrier=None, email=None):
        self._start_barrier = start_barrier

        # Pick backend; fall back from dxcam to mss if no initial frame arrives.
        capture_ctx = label = None
        if _dxcam_module() is not None:
            capture_ctx = self._make_dxcam_capture()
            if capture_ctx is None and not self._stop.is_set():
                self.on_status("error", "dxcam: no frame (fallback to mss)")
            else:
                label = "dxcam"
        if capture_ctx is None and not self._stop.is_set():
            capture_ctx = self._make_mss_capture()
        if capture_ctx is None or self._stop.is_set():
            return

        grab, w, h, cleanup = capture_ctx
        out = None
        t0 = time.time()
        frame_count = 0
        last_bgr = None
        frame_interval = 1.0 / config.FPS
        next_write_time = t0

        try:
            if not preview_only and save_dir:
                out = self._open_writer(w, h, label or "")
                if out is None:
                    return
                if start_barrier is not None:
                    start_barrier.wait()
                t0 = time.time()
                next_write_time = t0

            while not self._stop.is_set():
                # Transition: preview → recording
                if preview_only and self._pending_recording is not None:
                    _, barrier, _ = self._pending_recording
                    self._pending_recording = None
                    out = self._open_writer(w, h, label or "")
                    if out is None:
                        break
                    if barrier is not None:
                        barrier.wait()
                    t0 = time.time()
                    frame_count = 0
                    next_write_time = t0
                    preview_only = False

                sleep_until = next_write_time - time.time()
                if sleep_until > 0.002:
                    time.sleep(sleep_until)
                if self._stop.is_set():
                    break

                t_now = time.time()
                frame = grab()
                if frame is None:
                    frame = last_bgr
                else:
                    if (frame.shape[1], frame.shape[0]) != (w, h):
                        frame = cv2.resize(frame, (w, h))
                    last_bgr = frame

                if frame is None:
                    next_write_time += frame_interval
                    continue

                if out is not None:
                    out.write(frame)
                    frame_count += 1
                    if self._on_frame_written is not None:
                        try:
                            self._on_frame_written(frame, t_now - t0, False)
                        except Exception:
                            pass

                next_write_time += frame_interval
                self.on_frame(resize_frame(frame, config.PREVIEW_W, config.PREVIEW_H), t_now - t0)

        finally:
            cleanup()
            if out is not None:
                t_final = getattr(self, "_stop_time", None) or time.time()
                elapsed = t_final - t0
                frames_missing = int(elapsed * config.FPS) - frame_count
                if last_bgr is not None and frames_missing > 0:
                    for _ in range(frames_missing):
                        out.write(last_bgr)
                        if self._on_frame_written is not None:
                            try:
                                self._on_frame_written(last_bgr, elapsed, True)
                            except Exception:
                                pass
                out.release()
                self.on_done(self.filename)
            self.recording = False
