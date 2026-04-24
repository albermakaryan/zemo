# Screen & Webcam Recorder

Desktop app to record screen and/or webcam as MP4, with a floating movable start/stop button and optional countdown.

## Features

- **Screen** and **webcam** recording (separate or both at once, synced)
- **System audio**: Windows via WASAPI (PyAudioWPatch); Linux via PulseAudio/PipeWire monitor (sounddevice)
- **MP4** video output for webcam and screen
- **Gaze tracking**: per-frame eye-gaze estimation via eyetrax; saved as a CSV alongside recordings
- **Floating button** window (always on top, draggable to any monitor) with one big Start/Stop
- **Countdown** before recording starts (default 5 seconds, configurable)
- **Recordings** saved under `recordings/webcam/`, `recordings/screen/`, `recordings/audio/`, and `recordings/gaze/`

## Requirements

- Python 3.12+ (see `pyproject.toml`)
- **Windows 10+ or Linux** for screen + webcam recording
- **Windows**: system audio via `pip install -e ".[windows]"` (PyAudioWPatch). **Linux**: system audio via `pip install -e ".[linux]"` (sounddevice + PulseAudio/PipeWire)

## Setup (once per machine)

1. Install Python from [python.org](https://www.python.org/downloads/) and ensure **Add Python to PATH** is checked (on Windows).
2. In the project folder, install dependencies:

   **Option A – simple (uses `requirements.txt`):**
   ```bash
   pip install -r requirements.txt
   ```

   **Option B – editable install with extras:**
   ```bash
   pip install -e .
   # Windows only (dxcam + system audio via PyAudioWPatch):
   pip install -e ".[windows]"
   ```

## Run

- **Windows (GUI):** double-click `run_recorder.bat`
- **Linux/macOS (shell):** run `./run_recorder.sh` or `bash run_recorder.sh`
- **Any OS (CLI):** `python main.py`
- **Standalone .exe (Windows):** double-click `dist\Recorder.exe` after building (see below)

If Python is missing, the batch file opens the Python download page.

## Recording & audio syncing

- Clicking **Record Both** starts:
  - Webcam recording to `recordings/webcam/<email>_webcam.mp4`
  - Screen recording to `recordings/screen/<email>_screen.mp4`
  - Internal/system audio (when available) to `recordings/audio/<email>_audio.mka` (or `.wav` fallback)
- All three share a common **start barrier** so they begin at the same instant.

### Audio sync strategy

When `av` (PyAV) is installed the audio recorder writes a **Matroska Audio (.mka)** file instead of WAV. Every FLAC packet carries a PTS derived from WASAPI's `input_buffer_adc_time` (the hardware ADC clock). Because that clock ticks continuously even while the audio device is idle, a pause in the watched video shows up as a PTS jump in the container — no silence padding, no threshold tuning needed. ffmpeg aligns video and audio by PTS when muxing, so sync is mathematically exact.

If `input_buffer_adc_time` is zero (some drivers don't expose it) the recorder falls back to `time.perf_counter()` gap detection: when the inter-callback interval exceeds 8× the nominal callback period (~186 ms at 44100/1024), the PTS is advanced by the measured gap. Same result, slightly less precision.

Without PyAV the recorder falls back to a plain WAV file with silence padding on detected gaps.

The WASAPI callback itself never touches disk — all writes go through a bounded in-memory queue (≈46 s buffer) drained by a dedicated writer thread. This keeps the audio thread timing clean and prevents false gap detections from disk-I/O latency.

- After **Stop Both**, the app automatically muxes screen + audio:
  - Calls `python -m recorder.audio.mux_audio_into_video --screen-only <email>`
  - ffmpeg combines the screen MP4 and audio file (`.mka` preferred over `.wav`) by PTS alignment, re-encodes audio to AAC 192k.
  - Final file: `recordings/screen_with_audio/<email>_screen_with_audio.mp4`.

## Gaze tracking

Gaze tracking uses [eyetrax](https://github.com/) to estimate where on screen the participant is looking during webcam recording.

### Setup

1. Click **Calibrate Eyes** in the bottom bar. A full-screen Lissajous calibration window will open.
2. Follow the on-screen target with your eyes until calibration completes.
3. The model is saved to `gaze_model.pkl` next to the app. The button changes to **Re-calibrate Eyes**.

### During recording

- Enable/disable gaze tracking via **⚙** (gear) in the top bar, then the **Enable** checkbox in the panel (on by default).
- The **`+ gaze`** indicator in the bottom bar (green) reflects the setting.
- If gaze is enabled but no calibration file exists when you start recording, a popup lets you **continue without gaze** (gaze is turned off for that session) or **cancel** to calibrate first. The start controls stay available so that flow is never blocked.
- After the countdown, loading the gaze stack (MediaPipe) can take a few seconds; the float button may show **⏳** while that runs on a background thread so the UI stays responsive.

### Output

Each recording session produces `recordings/gaze/<email>_gaze.csv` with columns:

| Column | Description |
|---|---|
| `video_id` | User email |
| `frame_id` | 0-based frame counter (only increments on successful gaze detections) |
| `minute` | Integer minutes since first gaze frame |
| `second` | Integer seconds within the current minute |
| `x` | Estimated screen X coordinate |
| `y` | Estimated screen Y coordinate |

Blink or no-face frames produce no row.

## Build a standalone .exe (Windows)

1. Install dependencies and run the app at least once: `pip install -r requirements.txt`
2. From the project root, run **`build_exe.bat`** (double-click or from a terminal).
3. The executable is created at **`dist\Recorder_<version>.exe`** (for example `Recorder_1.2.3.exe`).

### Test build (no version bump)

To verify the build without changing **`VERSION`**, **`version_info.txt`**, or the versioned `dist\Recorder_<ver>.exe` name:

```bat
build_exe.bat --test
```

(You can also pass `test` without dashes.) The script reads the current `VERSION` as-is, does not rewrite that file, keeps an existing `version_info.txt` if present, and copies the result to **`dist\Recorder_test.exe`**. Use this for local QA; use a normal `build_exe.bat` run for release builds.

### Normal release build

When you run `build_exe.bat` **without** `--test`:

- **Version source of truth** is the `VERSION` file in the project root.
- The script bumps the version **automatically** and writes it back to `VERSION`:
  - No argument (default) or `patch` → `MAJOR.MINOR.(PATCH+1)` (e.g. `1.2.3 → 1.2.4`)
  - `minor` → `MAJOR.(MINOR+1).0` (e.g. `1.2.3 → 1.3.0`)
  - `major` → `(MAJOR+1).0.0` (e.g. `1.2.3 → 2.0.0`)
  - Explicit version like `build_exe.bat 1.4.0` sets `VERSION` to `1.4.0` directly.
- It then runs `python build_version_info.py <version>` to regenerate `version_info.txt` so the Windows file properties match.
- Finally it builds using `Recorder.spec` and copies `dist\Recorder.exe` to `dist\Recorder_<version>.exe`.

**Frozen .exe and gaze:** The PyInstaller one-file layout includes a small runtime hook (`gazer/pyi_rth_eyetrax.py`) so eyetrax can load its gaze model modules inside the bundle. Calibration from the **Calibrate** button uses `Recorder.exe --calibrate-only` in the frozen build (see `main.py`).

The app window title shows the current version (e.g. `Recorder v1.2.4`). You can copy `Recorder_<version>.exe` to any folder (or another PC). On first run it will create a `recordings` folder next to the exe (with `webcam/`, `screen/`, `audio/`, and `gaze/` as needed) for saving files. No Python installation needed on that machine.

## Project layout

```text
zemo/
├── main.py              # Entry point (dependency check + launch)
├── run_recorder.bat     # Windows launcher
├── run_recorder.sh      # Linux/macOS launcher
├── gaze_model.pkl       # Saved gaze calibration model (created on first calibration)
├── requirements.txt
├── pyproject.toml
├── recorder/            # Package
│   ├── __init__.py
│   ├── config.py        # Paths, constants, theme
│   ├── ui/              # App, panels, float button (Qt UI layer)
│   ├── core/            # Core recording logic (webcam/screen), no UI
│   ├── audio/           # Internal (system) audio recorder (Windows + Linux backends)
├── gazer/               # Gaze tracking package (EyeTracker wrapping eyetrax)
└── recordings/          # Output (created automatically)
    ├── webcam/          # Webcam MP4s
    ├── screen/          # Screen MP4s
    ├── audio/           # System audio .mka (PyAV) or .wav (fallback)
    ├── gaze/            # Gaze CSVs (<email>_gaze.csv)
    └── screen_with_audio/  # Muxed screen + audio MP4s
```

## Test audio only (no full app)

To check system audio capture without the full app:

- `./run_audio_test.sh` — record 15 s to `recordings_test/audio/`
- `./run_audio_test.sh 20` — record 20 s
- `python3 -m tests audio --seconds 10`

Play a video in the browser while it runs; the WAV should contain that audio. Linux: `pip install -e ".[linux]"` and Pulse/PipeWire running.

## Why is audio “(no system audio)” or failed?

- **On Windows:** install `pip install -e ".[windows]"` (PyAudioWPatch). If it still fails, check that you have a default playback device.
- **On Linux:** install `pip install -e ".[linux]"` (sounddevice) for PulseAudio/PipeWire monitor. If still "(no system audio)", ensure Pulse/PipeWire is running and a monitor source exists.
- **On macOS:** system audio is not implemented.

## Configuration

- **Countdown length:** edit `COUNTDOWN_SECONDS` in `recorder/config.py`.
- **Gaze model path:** edit `GAZE_ESTIMATOR_PATH` in `recorder/config.py` (default: `gaze_model.pkl` next to the app).
- **Recordings location:** by default `recordings/` is created next to the script / exe, with `webcam/`, `screen/`, `audio/`, and `gaze/` subfolders. `.gitkeep` files are created so these folders can be tracked in Git even when empty.

## License

Use as you like.
