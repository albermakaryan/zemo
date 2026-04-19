"""Eye tracking via eyetrax: calibration, model persistence, per-frame gaze estimation."""

import os

from eyetrax import GazeEstimator, run_lissajous_calibration

from recorder import config


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

    def track_eyes(self, frame) -> tuple[float | None, float | None]:
        """Return (x, y) screen coordinates estimated from a webcam frame.

        Returns (None, None) when a blink is detected or features cannot be extracted.
        """
        features, blink = self.estimator.extract_features(frame)
        if features is not None and not blink:
            x, y = self.estimator.predict([features])[0]
            return float(x), float(y)
        return None, None

    def destroy(self) -> None:
        """Delete the saved calibration model file from disk."""
        try:
            os.remove(self._model_path)
        except OSError:
            pass
