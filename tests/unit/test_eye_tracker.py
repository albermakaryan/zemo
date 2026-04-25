"""Unit tests for `gazer.eye_tracker` (no real calibration or model load)."""

from gazer.eye_tracker import EyeTracker


def test_is_model_saved_respects_path(tmp_path):
    p = tmp_path / "gaze_model.pkl"
    assert EyeTracker.is_model_saved(str(p)) is False
    p.write_bytes(b"x")
    assert EyeTracker.is_model_saved(str(p)) is True
