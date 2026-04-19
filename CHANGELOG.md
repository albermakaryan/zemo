# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- **Gaze tracking** (`gazer/` package, `recorder/ui/app/`): per-frame eye-gaze estimation using [eyetrax](https://github.com/) during webcam recording.
  - `gazer/eye_tracker.py`: wraps `GazeEstimator` — calibration, model persistence (`gaze_model.pkl`), and per-frame `track_eyes(frame)` returning `(x, y)` screen coordinates.
  - **Calibrate button** in the bottom bar: launches a Lissajous calibration window in a subprocess (avoids OpenCV GUI / Win32 threading conflicts). Stops the webcam preview before calibration, then restarts it automatically after. Button label switches between "Calibrate Eyes" and "Re-calibrate Eyes" based on model presence.
  - **Settings panel** (⚙ gear button, upper-right of top bar): collapsible inline panel with an "Enable" checkbox for gaze tracking. Gaze is **on by default**. If the model file is missing when recording starts, a popup asks the user to either continue without gaze tracking (disables it in settings) or cancel to calibrate first.
  - **`+ gaze` indicator** in the bottom bar (green): visible whenever gaze tracking is enabled, mirrors the state of the settings checkbox.
  - **Gaze CSV output**: one file per recording session, saved to `recordings/gaze/<email>_gaze.csv`. Written row-by-row during recording (no memory buffering). Columns: `video_id` (user email), `frame_id` (0-based), `minute`, `second` (integer, relative to first captured gaze frame), `x`, `y`.
  - `config.py`: new constants `GAZE_SUBDIR = "gaze"` and `GAZE_ESTIMATOR_PATH`. `ensure_recordings_dirs()` now also creates `recordings/gaze/`.

- **Webcam camera retry** (`recorder/core/webcam.py`): if the camera cannot be opened on the first attempt (e.g. temporarily held by the calibration subprocess), the recorder retries up to 6 times with 1-second intervals before giving up.

### Changed

- **`recorder/__init__.py`**: `from recorder.ui import App` is now a lazy `__getattr__` import to avoid a circular import when the `gazer` subprocess imports `recorder.config`.
- **`recorder/ui/app/window.py`**: added `_calibration_finished = QtCore.Signal()` signal (connected to `_on_calibration_done`) so the background calibration thread can safely notify the main Qt thread when the subprocess exits.
- **Float button** (`recorder/ui/float_button.py`): gaze readiness check (`_gaze_ready_or_prompt`) now runs before the email prompt and countdown, so the popup appears immediately on click.

- **Webcam horizontal flip** (`recorder/core/webcam.py`): after each frame is read from the camera, the pipeline can apply `cv2.flip(frame, 1)` so left and right match real-world orientation. The same correction is used for the live preview and for frames written to the webcam MP4, so they stay consistent.

### Changed

- **Configuration** (`recorder/config.py`): new setting `WEBCAM_FLIP_HORIZONTAL` with three modes:
  - `True`: always flip (use on any OS if the image is still mirror-like).
  - `False`: never flip.
  - `"auto"` (default): flip only when the built-in rules expect a mirrored driver stream (see below).

- **Windows camera backends** (`recorder/core/webcam.py`): opening the webcam now tries **DirectShow** first, then **Media Foundation (MSMF)**, then a plain `VideoCapture(index)` fallback, so more devices open reliably and behavior is easier to reason about than MSMF-only.

### Why

Many Windows webcam drivers deliver a **horizontally mirrored** image (like looking in a mirror: text and hands appear reversed compared to how others see you or how a normal photo looks). Without a flip, preview and recordings stay mirrored.

An earlier `"auto"` rule only flipped when using **MSMF**. The app prefers **DirectShow** when it works, so the flip often never ran and the picture stayed mirrored. The current logic flips under `"auto"` for **all** of this app’s Windows capture paths (`dshow`, `msmf`, and the generic fallback). On **Linux and macOS**, typical OpenCV capture is usually already correct, so `"auto"` leaves the image unchanged there; users with unusual drivers can set `WEBCAM_FLIP_HORIZONTAL = True`.

Keeping **`"auto"`** as the default avoids hard-coding `sys.platform` in `config.py` while still picking a sensible behavior per OS in one place (`_effective_horizontal_flip` in `webcam.py`).
