# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Fixed

- **Calibration on a new machine – face landmark model auto-download** (`gazer/eye_tracker.py`, `recorder/ui/app/_recording_mixin.py`): clicking **Calibrate Eyes** on a machine where `~/.cache/eyetrax/mediapipe/face_landmarker.task` is absent now downloads the model (~26 MB) with a modal **"First-time Setup"** progress dialog before launching the calibration window. Previously the download happened silently inside the calibration subprocess with no UI feedback, making the app appear frozen or broken on a fresh install.
- **Bridge GC freeze after model download** (`recorder/ui/app/_recording_mixin.py`): the `FaceLandmarkerDownloadBridge` QObject is now stored on `self` (`self._dl_bridge`) for the lifetime of the download. Previously it was a local variable; Python could collect it before the background thread called `bridge.done.emit()`, silently disconnecting the slot and leaving the modal progress dialog open forever.
- **`unicodedata` missing from frozen exe** (`Recorder.spec`): added `unicodedata` to `hiddenimports`. The calibration subprocess (`Recorder.exe --calibrate-only`) imports `mediapipe.tasks.python.vision`, which transitively pulls in `matplotlib → matplotlib._mathtext → unicodedata`. PyInstaller's static analysis did not follow this chain, so the subprocess crashed with `ModuleNotFoundError: No module named 'unicodedata'` on machines where the model had to be loaded for the first time.
- **Data loss on window close** (`recorder/ui/app/window.py`): `closeEvent` now calls `_flush_gaze_csv()` and `_flush_mouse_csv()` after joining recorders. Previously, closing the window while recording left the gaze worker queue un-drained and both CSV files unclosed.
- **`analyze_recordings.py` standalone crash** (`validation/analyze_recordings.py`): imports `DEFAULT_FPS` instead of `FPS`. `config.FPS` is set dynamically by the app at startup via `_load_fps_setting()`; importing it directly in a standalone script always raised `ImportError` if run before the app initialised.
- **Webcam recordings – black bars / padding** (`recorder/config.py`): `WEBCAM_PREFERRED_WIDTH` and `WEBCAM_PREFERRED_HEIGHT` now default to `None` so OpenCV uses the camera’s native mode. They previously matched the primary monitor size (via `pyautogui`), which pushed many drivers to letterbox the sensor image inside a display-shaped frame.

### Added

- **`EyeTracker.is_face_landmarker_available()` / `download_face_landmarker()`** (`gazer/eye_tracker.py`): two new static methods. `is_face_landmarker_available()` returns `True` when `face_landmarker.task` is already cached. `download_face_landmarker(progress_callback)` downloads it from Google Storage to the eyetrax cache directory, calling `progress_callback(bytes_done, total_bytes)` after each chunk so callers can drive a progress bar.
- **`FaceLandmarkerDownloadBridge`** (`recorder/ui/app/_recording_mixin.py`): `QObject` subclass with `progress(int, int)` and `done(bool, str)` signals, used to relay download progress from a background thread to the main Qt thread.
- **`is_padding` column** in gaze and mouse CSV (`recorder/ui/app/_recording_mixin.py`): integer flag (`0` = real data, `1` = synthetic fill) so downstream consumers can distinguish genuine measurements from padding frames. Previously there was no way to tell them apart.
- **`elapsed_s` float column** in gaze and mouse CSV: sub-second timestamp (seconds since first frame, 4 decimal places). The previous `minute` / `second` integer split truncated to whole seconds, so all 15 frames per second shared the same timestamp. Both old columns are kept for backward compatibility.
- **Kalman smoothing for gaze** (`recorder/ui/app/_recording_mixin.py`): each raw `(x, y)` prediction from `track_eyes` is passed through a `cv2.KalmanFilter` (via `eyetrax.make_kalman()`) before being written to the CSV. Reduces per-frame noise at zero cost to the recording loop. Skipped gracefully if `make_kalman` is unavailable.
- **`build_exe.bat --test`** (or `test`): test build that does **not** bump `VERSION`, does **not** overwrite `VERSION`, and skips regenerating `version_info.txt` when that file already exists (so release metadata stays unchanged). Output is copied to **`dist\Recorder_test.exe`** instead of `dist\Recorder_<version>.exe`. Use for local verification before a versioned release.
- **PyInstaller frozen app – eyetrax models** (`gazer/pyi_rth_eyetrax.py`, `Recorder.spec`): runtime hook replaces `eyetrax.models._auto_discover()` so model modules load without scanning a filesystem path that does not exist inside the one-file bundle (fixes `FileNotFoundError` for `_MEI…/eyetrax/models` when calibrating or starting gaze from the `.exe`).
- **Gaze tracking** (`gazer/` package, `recorder/ui/app/`): per-frame eye-gaze estimation using [eyetrax](https://github.com/) during webcam recording.
  - `gazer/eye_tracker.py`: wraps `GazeEstimator` — calibration, model persistence (`gaze_model.pkl`), and per-frame `track_eyes(frame)` returning `(x, y)` screen coordinates.
  - **Calibrate button** in the bottom bar: launches a Lissajous calibration window in a subprocess (avoids OpenCV GUI / Win32 threading conflicts). Stops the webcam preview before calibration, then restarts it automatically after. Button label switches between “Calibrate Eyes” and “Re-calibrate Eyes” based on model presence.
  - **Settings panel** (⚙ gear button, upper-right of top bar): collapsible inline panel with an “Enable” checkbox for gaze tracking. Gaze is **on by default**. If the model file is missing when recording starts, a popup asks the user to either continue without gaze tracking (disables it in settings) or cancel to calibrate first.
  - **`+ gaze` indicator** in the bottom bar (green): visible whenever gaze tracking is enabled, mirrors the state of the settings checkbox.
  - **Gaze CSV output**: one file per recording session, saved to `recordings/gaze/<email>_gaze.csv`. Written row-by-row during recording (no memory buffering). Columns: `video_id` (user email), `frame_id` (0-based), `minute`, `second` (integer, relative to first captured gaze frame), `x`, `y`.
  - `config.py`: new constants `GAZE_SUBDIR = “gaze”` and `GAZE_ESTIMATOR_PATH`. `ensure_recordings_dirs()` now also creates `recordings/gaze/`.
- **Webcam camera retry** (`recorder/core/webcam.py`): if the camera cannot be opened on the first attempt (e.g. temporarily held by the calibration subprocess), the recorder retries up to 6 times with 1-second intervals before giving up.

### Changed

- **Mux delay** (`recorder/ui/app/_recording_mixin.py`): `_mux_cli` sleep reduced from **60 s** to **5 s**. Recorders are already joined before `_dispatch_mux` runs, so the file is fully written by then; the short margin covers OS-level flush only.
- **Mouse cursor reads** (`recorder/ui/app/_recording_mixin.py`): `pyautogui.position()` replaced with a direct `ctypes.windll.user32.GetCursorPos` call. Removes the `pyautogui` import and its heavyweight dependencies (screenshot, keyboard/mouse automation) for a function that only needed cursor coordinates.
- **`_is_silent` in audio recorder** (`recorder/audio/internal_win.py`): uses `numpy.frombuffer` + `np.abs(...).max()` instead of `struct.unpack` + Python `max()`. Falls back to `struct` only when numpy is absent.
- **H.264 codec fallback** (`recorder/config.py`): `VIDEO_FOURCC_TRY_ORDER` is now `(“mp4v”, “avc1”)`. `avc1` (H.264) produces 3–5× smaller files when the OpenH264 DLL is present; `mp4v` remains the safe default when it is not.
- **Barrier action removed** (`recorder/ui/app/_recording_mixin.py`): `threading.Barrier` in `_start_recorders_barrier_and_audio` no longer carries a `set_shared_t0` action, and `start_time_ref` is no longer passed to the audio recorder. The Windows audio recorder (`internal_win.py`) stored `_start_time_ref` but never read it; the alignment it was intended for is handled instead by the per-stream `t0` measured after the barrier fires.
- **Development dependencies** (`pyproject.toml`): `pytest`, `pytest-mock`, `pytest-cov`, `pre-commit`, and `pip` are listed under `[dependency-groups] dev`. [uv](https://docs.astral.sh/uv/) includes that group on a normal `uv sync` and omits it on `uv sync --no-dev`. The `[project.optional-dependencies] dev` extra was removed; optional extras `windows` and `linux` are unchanged.
- **`recorder/__init__.py`**: `from recorder.ui import App` is now a lazy `__getattr__` import to avoid a circular import when the `gazer` subprocess imports `recorder.config`.
- **`recorder/ui/app/window.py`**: added `_calibration_finished = QtCore.Signal()` signal (connected to `_on_calibration_done`) so the background calibration thread can safely notify the main Qt thread when the subprocess exits.
- **Float button** (`recorder/ui/float_button.py`): gaze readiness check (`_gaze_ready_or_prompt`) runs before the email prompt and countdown, so the “no calibration / continue without gaze” popup appears immediately on click. **⏳** shows while the gaze stack is loading after the countdown; the top **Record Both** and float controls stay coordinated during busy states (recording, countdown, gaze init) without disabling start based on missing calibration — users can still choose to record without gaze via the existing dialog.
- **Async gaze model load** (`recorder/ui/app/_recording_mixin.py`): `EyeTracker()` (MediaPipe / `GazeEstimator`) is constructed on a **background thread**; the main Qt thread continues the UI so the app does not freeze on the last second of the countdown. Completion is delivered via a `GazeInitBridge` signal (`QtCore.QObject` + `Signal`) so the rest of `record_both` runs on the GUI thread.
- **Webcam horizontal flip** (`recorder/core/webcam.py`): after each frame is read from the camera, the pipeline can apply `cv2.flip(frame, 1)` so left and right match real-world orientation. The same correction is used for the live preview and for frames written to the webcam MP4, so they stay consistent.
- **Configuration** (`recorder/config.py`): new setting `WEBCAM_FLIP_HORIZONTAL` with three modes:
  - `True`: always flip (use on any OS if the image is still mirror-like).
  - `False`: never flip.
  - `”auto”` (default): flip only when the built-in rules expect a mirrored driver stream. Under `”auto”`, the app flips for all Windows capture paths (`dshow`, `msmf`, and the generic fallback); Linux and macOS are left unchanged.
- **Windows camera backends** (`recorder/core/webcam.py`): opening the webcam now tries **DirectShow** first, then **Media Foundation (MSMF)**, then a plain `VideoCapture(index)` fallback, so more devices open reliably and behavior is easier to reason about than MSMF-only.

### Removed

- **`open_webcam`** (`recorder/common.py`): unused helper (MSMF-only open); the webcam recorder uses its own `_try_open_capture` (DirectShow → MSMF → default).
- **`sanitize_email_for_filename`** (`recorder/common.py`): all internal code uses `email_filename_part`; this variant was only re-exported and untested by the main app.
- **`frame_to_tk`** (`recorder/common.py`): Tkinter helper in a PySide6 application; leftover from an earlier frontend.
- **Dead `frame_counter`** (`recorder/ui/app/_recording_mixin.py`): after the async-queue refactor, `frame_counter = [0]` in `_gaze_on_frame_written` was incremented but the value was never consumed (the gaze worker uses its own `fcount`).
- **`config.MONO`, `config.MONO_SM`** (`recorder/config.py`): Tkinter-era font tuples; no Python file referenced them.
- **`config.sans_font()`** (`recorder/config.py`): Tkinter helper that imported `tkinter` at call time; never called by the PySide6 app.
- **`config.DETECTION_SUBDIR`, `config.get_detection_dir()`** (`recorder/config.py`): no app code ever wrote to or read from the detection directory.
- **`EyeTracker.destroy()`** (`gazer/eye_tracker.py`): defined but never called from any file in the project.
- **Unused imports** across multiple files: `import os` / `import sys` in `scripts/video_detail.py`; `import time` in `recorder/audio/mux_audio_into_video.py`; `from typing import List, Optional, Tuple` in `recorder/common.py` (made redundant by the function removals above).
- **`equal_frames = {}`** (`scripts/video_detail.py`): initialized but never written to or read from.

### Documentation

- **`README.md`**, **`docs/USER_MANUAL.md`**, and **`CHANGELOG.md`**: document **`build_exe.bat --test`**, the **eyetrax** PyInstaller hook, **async gaze loading** and **⏳** on the float button, the **gaze / email / countdown** order, **Record Both** busy-state behavior, **Python 3.12+**, and troubleshooting for frozen calibration.
- **`README.md`**: **uv** install (`uv sync`, `uv sync --no-dev`), **Development** (tests / dev deps), and **Configuration** for webcam `WEBCAM_PREFERRED_*` defaults.
