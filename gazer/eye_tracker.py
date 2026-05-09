"""Eye tracking via eyetrax: calibration, model persistence, per-frame gaze estimation."""

import os
from pathlib import Path
import urllib.request

from eyetrax import GazeEstimator, run_lissajous_calibration

from recorder import config


FACE_LANDMARKER_TASK_URL = (
    "https://storage.googleapis.com/mediapipe-models/"
    "face_landmarker/face_landmarker/float16/1/face_landmarker.task"
)
FACE_LANDMARKER_TASK_PATH = (
    Path.home() / ".cache" / "eyetrax" / "mediapipe" / "face_landmarker.task"
)


class EyeTracker:
    """Wraps a GazeEstimator for calibration and per-frame gaze prediction.

    Typical usage
    -------------
    First-time setup (opens a Lissajous calibration window):
        tracker = EyeTracker.calibrate_and_create()

    Subsequent sessions (loads saved model):
        tracker = EyeTracker()

    Per-frame during recording:
        x, y = tracker.track_eyes(webcam_frame)
    """

    def __init__(self, model_path: str | None = None):
        self._model_path = model_path or str(config.GAZE_ESTIMATOR_PATH)
        self.estimator = self._load()

    def _load(self) -> GazeEstimator:
        estimator = GazeEstimator()
        estimator.load_model(self._model_path)
        return estimator

    @classmethod
    def calibrate_and_create(cls, model_path: str | None = None) -> "EyeTracker":
        """Run Lissajous calibration, save the model, and return a ready EyeTracker.

        Opens a full-screen calibration window managed by eyetrax.
        """
        path = model_path or str(config.GAZE_ESTIMATOR_PATH)
        estimator = GazeEstimator()
        run_lissajous_calibration(estimator)
        estimator.save_model(path)
        inst = object.__new__(cls)
        inst._model_path = path
        inst.estimator = estimator
        return inst

    @staticmethod
    def is_model_saved(model_path: str | None = None) -> bool:
        """Return True if a calibration model file exists on disk."""
        path = model_path or str(config.GAZE_ESTIMATOR_PATH)
        return os.path.exists(path)

    @staticmethod
    def is_face_landmarker_available() -> bool:
        """Return True if the MediaPipe face landmark model is already cached."""
        return FACE_LANDMARKER_TASK_PATH.exists()

    @staticmethod
    def download_face_landmarker(progress_callback=None) -> None:
        """Download face_landmarker.task to the eyetrax cache directory.

        progress_callback(bytes_done: int, total_bytes: int | None) is called after each chunk.
        Raises on network or filesystem errors.
        """
        dst = FACE_LANDMARKER_TASK_PATH
        dst.parent.mkdir(parents=True, exist_ok=True)
        tmp = dst.with_suffix(dst.suffix + ".tmp")
        try:
            req = urllib.request.Request(
                FACE_LANDMARKER_TASK_URL, headers={"User-Agent": "eyetrax"}
            )
            with urllib.request.urlopen(req, timeout=60) as resp, tmp.open("wb") as fh:
                raw_total = resp.headers.get("Content-Length")
                total = int(raw_total) if raw_total and raw_total.isdigit() else None
                downloaded = 0
                while True:
                    chunk = resp.read(65536)
                    if not chunk:
                        break
                    fh.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback is not None:
                        progress_callback(downloaded, total)
            tmp.replace(dst)
        except Exception:
            tmp.unlink(missing_ok=True)
            raise

    def track_eyes(self, frame) -> tuple[float | None, float | None]:
        """Return (x, y) screen coordinates estimated from a webcam frame.

        Returns (None, None) when a blink is detected or features cannot be extracted.
        """
        features, blink = self.estimator.extract_features(frame)
        if features is not None and not blink:
            x, y = self.estimator.predict([features])[0]
            return float(x), float(y)
        return None, None

