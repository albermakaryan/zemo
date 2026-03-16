# Screen & Webcam Recorder

Desktop app to record screen and/or webcam as MP4, with a floating movable start/stop button and optional countdown.

## Features

- **Screen** and **webcam** recording (separate or both at once, synced)
- **System audio**: Windows via WASAPI (PyAudioWPatch); Linux via PulseAudio/PipeWire monitor (sounddevice)
- **MP4** video output for webcam and screen
- **Floating button** window (always on top, draggable to any monitor) with one big Start/Stop
- **Countdown** before recording starts (default 5 seconds, configurable)
- **Recordings** saved under `recordings/webcam/`, `recordings/screen/`, and `recordings/audio/`

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
  - Internal/system audio (when available) to `recordings/audio/<email>_audio.wav`
- All three share:
  - A common **start barrier** so they begin at the same time.
  - A shared **wall-clock start time** and **stop time** when you click **Stop Both**.
- The internal audio recorder stores chunks with timestamps and later builds a WAV that:
  - Includes any needed silence at the start so it lines up with video.
  - Pads/trims so its total duration matches the video timeline.
- After **Stop Both**, the app automatically runs the mux script:
  - It calls `python -m recorder.audio.mux_audio_into_video --screen-only <email>`
  - This uses ffmpeg with `aresample=async=1:first_pts=0` and `-vsync cfr` to keep audio/video aligned.
  - The final synced file is written to `recordings/screen_with_audio/<email>_screen_with_audio.mp4`.

## Build a standalone .exe (Windows)

1. Install dependencies and run the app at least once: `pip install -r requirements.txt`
2. From the project root, run **`build_exe.bat`** (double-click or from a terminal).
3. The executable is created at **`dist\Recorder_<version>.exe`** (for example `Recorder_1.2.3.exe`).

When you run `build_exe.bat`:

- **Version source of truth** is the `VERSION` file in the project root.
- The script bumps the version **automatically** and writes it back to `VERSION`:
  - No argument (default) or `patch` → `MAJOR.MINOR.(PATCH+1)` (e.g. `1.2.3 → 1.2.4`)
  - `minor` → `MAJOR.(MINOR+1).0` (e.g. `1.2.3 → 1.3.0`)
  - `major` → `(MAJOR+1).0.0` (e.g. `1.2.3 → 2.0.0`)
  - Explicit version like `build_exe.bat 1.4.0` sets `VERSION` to `1.4.0` directly.
- It then runs `python build_version_info.py <version>` to regenerate `version_info.txt` so the Windows file properties match.
- Finally it builds using `Recorder.spec` and copies `dist\Recorder.exe` to `dist\Recorder_<version>.exe`.

The app window title shows the current version (e.g. `Recorder v1.2.4`). You can copy `Recorder_<version>.exe` to any folder (or another PC). On first run it will create a `recordings` folder next to the exe (with `webcam/`, `screen/`, and `audio/` inside) for saving videos. No Python installation needed on that machine.

## Project layout

```text
zemo/
├── main.py              # Entry point (dependency check + launch)
├── run_recorder.bat     # Windows launcher
├── run_recorder.sh      # Linux/macOS launcher
├── requirements.txt
├── pyproject.toml
├── recorder/            # Package
│   ├── __init__.py
│   ├── config.py        # Paths, constants, theme
│   ├── ui/              # App, panels, float button (Qt UI layer)
│   ├── core/            # Core recording logic (webcam/screen), no UI
│   ├── audio/           # Internal (system) audio recorder (Windows + Linux backends)
└── recordings/          # Output (created automatically)
    ├── webcam/          # Webcam MP4s
    ├── screen/          # Screen MP4s
    └── audio/           # System audio WAVs (when available)
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
- **Recordings location:** by default `recordings/` is created next to the script / exe, with `webcam/`, `screen/`, and `audio/` subfolders. `.gitkeep` files are created so these folders can be tracked in Git even when empty.

## License

Use as you like.
