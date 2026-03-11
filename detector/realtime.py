"""
Real-time emotion detection: webcam window with bounding box, emotion name, and probability.
Saves results to a CSV in the given save_dir.
"""

from __future__ import annotations

import csv
import queue
import time
from pathlib import Path
from typing import Callable, Optional, Tuple

import cv2
import numpy as np

from .emotion_model import DeepFaceEmotionModel, EmotionResult


def _draw_overlay(
    frame: np.ndarray,
    result: EmotionResult,
) -> None:
    """Draw face bbox and emotion label + probability on frame (in-place)."""
    if result.face_bbox is not None:
        x, y, w, h = result.face_bbox
        cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
    label = f"{result.top_emotion or 'neutral'} {result.emotion_pct:.0f}%"
    cv2.putText(
        frame,
        label,
        (10, 30),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.0,
        (0, 255, 0),
        2,
    )


class EmotionOverlay:
    """
    Callable overlay for in-preview emotion detection. Draws on the frame in place.
    CSV is written only when is_recording is True (i.e. during recording, not in preview),
    and only after a name_part (email-based) has been provided.
    """

    def __init__(
        self,
        save_dir: str | Path,
        fps: float = 25.0,
        sample_interval_s: float = 0.5,
        name_part: Optional[str] = None,
    ):
        self._save_dir = Path(save_dir)
        self._save_dir.mkdir(parents=True, exist_ok=True)
        self._model = DeepFaceEmotionModel()
        self._sample_stride = max(1, int(fps * sample_interval_s))
        self._frame_idx = 0
        self._last_result: Optional[EmotionResult] = None
        self._file_handle: Optional[object] = None
        self._writer: Optional[csv.writer] = None
        self._name_part: Optional[str] = None
        self._csv_path: Optional[Path] = None
        if name_part:
            self.set_name_part(name_part)

    def set_name_part(self, name_part: str) -> None:
        """
        Set the email-based name part used for the CSV filename.
        Safe to call before or after preview starts; must be called
        before recording if you want CSV rows to be written.
        """
        safe_name = (name_part or "user").strip()
        for c in '\\/:*?"<>|':
            safe_name = safe_name.replace(c, "_")
        safe_name = safe_name or "user"
        self._name_part = safe_name
        self._csv_path = self._save_dir / f"{safe_name}_emotion.csv"

    def __call__(
        self, frame: np.ndarray, elapsed_s: float, is_recording: bool = False
    ) -> None:
        """Draw overlay on frame; write CSV row only when a name is set and is_recording is True."""
        if self._frame_idx % self._sample_stride == 0:
            try:
                self._last_result = self._model.analyze_frame(frame, time_s=elapsed_s)
                if is_recording and self._csv_path is not None:
                    if self._file_handle is None:
                        self._file_handle = self._csv_path.open(
                            "w", newline="", encoding="utf-8"
                        )
                        self._writer = csv.writer(self._file_handle)
                        self._writer.writerow(
                            [
                                "time_s",
                                "emotion",
                                "emotion_pct",
                                "face_x",
                                "face_y",
                                "face_w",
                                "face_h",
                            ]
                        )
                        self._file_handle.flush()
                    row = [
                        f"{elapsed_s:.3f}",
                        self._last_result.top_emotion,
                        f"{self._last_result.emotion_pct:.2f}",
                    ]
                    if self._last_result.face_bbox:
                        row.extend(self._last_result.face_bbox)
                    else:
                        row.extend([0, 0, 0, 0])
                    self._writer.writerow(row)
                    self._file_handle.flush()
            except Exception:
                pass
        if self._last_result is not None:
            _draw_overlay(frame, self._last_result)
        self._frame_idx += 1

    def stop(self) -> None:
        """Close CSV file. Call when disabling emotion overlay."""
        if self._file_handle is not None:
            self._file_handle.close()
            self._file_handle = None
            self._writer = None

    @property
    def csv_path(self) -> Path:
        # If CSV was never configured or written, return a sensible default path
        # so callers can still check .exists() and show a friendly message.
        if self._csv_path is not None:
            return self._csv_path
        return self._save_dir / "user_emotion.csv"


def run_realtime_emotion_detection_from_frames(
    frame_queue: queue.Queue,
    fps: float = 25.0,
    save_dir: str | Path = "",
    sample_interval_s: float = 0.5,
    on_done: Optional[Callable[[Optional[Path]], None]] = None,
) -> Optional[Path]:
    """
    Run emotion detection on frames from the given queue (no camera open).
    Queue items are (frame, elapsed_s). Use (None, None) to signal stop.
    Writes CSV to save_dir and shows OpenCV window. Press 'q' or close window to stop.
    """
    save_dir = Path(save_dir)
    save_dir.mkdir(parents=True, exist_ok=True)
    csv_path = save_dir / f"realtime_emotions_{time.strftime('%Y%m%d_%H%M%S')}.csv"

    model = DeepFaceEmotionModel()
    sample_stride = max(1, int(fps * sample_interval_s))

    file_handle = csv_path.open("w", newline="", encoding="utf-8")
    writer = csv.writer(file_handle)
    writer.writerow(
        ["time_s", "emotion", "emotion_pct", "face_x", "face_y", "face_w", "face_h"]
    )
    file_handle.flush()

    frame_idx = 0
    last_result: Optional[EmotionResult] = None
    window_name = "Real-time emotion detection (press 'q' to stop)"

    try:
        while True:
            try:
                item = frame_queue.get(timeout=0.1)
            except queue.Empty:
                item = None
            if item is not None:
                frame, t_s = item
                if frame is None and t_s is None:
                    break
                if frame is not None and t_s is not None:
                    if frame_idx % sample_stride == 0:
                        try:
                            last_result = model.analyze_frame(frame, time_s=t_s)
                            row = [
                                f"{t_s:.3f}",
                                last_result.top_emotion,
                                f"{last_result.emotion_pct:.2f}",
                            ]
                            if last_result.face_bbox:
                                row.extend(last_result.face_bbox)
                            else:
                                row.extend([0, 0, 0, 0])
                            writer.writerow(row)
                            file_handle.flush()
                        except Exception:
                            pass

                    if last_result is not None:
                        _draw_overlay(frame, last_result)

                    cv2.imshow(window_name, frame)
                    frame_idx += 1

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
            try:
                if cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE) < 1:
                    break
            except cv2.error:
                break
    finally:
        file_handle.close()
        try:
            cv2.destroyWindow(window_name)
        except cv2.error:
            pass
        if on_done is not None:
            on_done(csv_path)

    return csv_path


def run_realtime_emotion_detection(
    save_dir: str | Path,
    sample_interval_s: float = 0.5,
    camera_index: int = 0,
    on_done: Optional[Callable[[Optional[Path]], None]] = None,
) -> Optional[Path]:
    """
    Open webcam, run emotion detection in real time, show bounding box + emotion + probability,
    and append results to a timestamped CSV in save_dir. Close the OpenCV window or press 'q' to stop.

    If on_done is provided, it is called with (csv_path or None) when the window closes.
    Returns the path to the saved CSV, or None if no results or error.
    """
    save_dir = Path(save_dir)
    save_dir.mkdir(parents=True, exist_ok=True)
    csv_path = save_dir / f"realtime_emotions_{time.strftime('%Y%m%d_%H%M%S')}.csv"

    # Try given index first, then 0, 1 (index 2 can fail when only 2 devices exist)
    to_try = [camera_index]
    for x in (0, 1):
        if x not in to_try:
            to_try.append(x)
    cap = None
    for idx in to_try:
        c = cv2.VideoCapture(int(idx))
        if c.isOpened():
            cap = c
            break
        c.release()

    if cap is None:
        if on_done is not None:
            on_done(None)
        return None

    model = DeepFaceEmotionModel()
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    sample_stride = max(1, int(fps * sample_interval_s))

    file_handle = csv_path.open("w", newline="", encoding="utf-8")
    writer = csv.writer(file_handle)
    writer.writerow(
        ["time_s", "emotion", "emotion_pct", "face_x", "face_y", "face_w", "face_h"]
    )
    file_handle.flush()

    frame_idx = 0
    last_result: Optional[EmotionResult] = None
    window_name = "Real-time emotion detection (press 'q' to stop)"

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break

            t_s = frame_idx / fps

            if frame_idx % sample_stride == 0:
                try:
                    last_result = model.analyze_frame(frame, time_s=t_s)
                    row = [
                        f"{t_s:.3f}",
                        last_result.top_emotion,
                        f"{last_result.emotion_pct:.2f}",
                    ]
                    if last_result.face_bbox:
                        row.extend(last_result.face_bbox)
                    else:
                        row.extend([0, 0, 0, 0])
                    writer.writerow(row)
                    file_handle.flush()
                except Exception:
                    pass

            if last_result is not None:
                _draw_overlay(frame, last_result)

            cv2.imshow(window_name, frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
            if cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE) < 1:
                break

            frame_idx += 1
    finally:
        file_handle.close()
        cap.release()
        try:
            cv2.destroyWindow(window_name)
        except cv2.error:
            pass
        if on_done is not None:
            on_done(csv_path)

    return csv_path
