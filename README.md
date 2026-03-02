# Screen & Webcam Recorder

Desktop app to record screen and/or webcam as MP4, with a floating start/stop button and optional countdown.

## Features

- **Screen** and **webcam** recording (separate or both at once, synced)
- **System audio (Windows only)** via WASAPI loopback + PyAudioWPatch (what you hear from the speakers)
- **MP4** video output for webcam and screen
- **Floating button** window (always on top, draggable to any monitor) with one big Start/Stop
- **Countdown** before recording starts (default 5 seconds, configurable)
- **Recordings** saved under `recordings/webcam/`, `recordings/screen/`, and `recordings/audio/`

## Requirements

- Python 3.12+ (see `pyproject.toml`)
- **Windows 10+ or Linux** for screen + webcam recording
- **Windows only** for system audio recording (WASAPI loopback via PyAudioWPatch)

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

## Build a standalone .exe (Windows)

1. Install dependencies and run the app at least once: `pip install -r requirements.txt`
2. Double-click **`build_exe.bat`** (or in a terminal: `pyinstaller --clean Recorder.spec`)
3. The executable is created at **`dist\Recorder.exe`**

Copy `Recorder.exe` to any folder (or another PC). On first run it will create a `recordings` folder next to the exe (with `webcam/`, `screen/`, and `audio/` inside) for saving videos. No Python installation needed on that machine.

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
│   ├── ui/              # App, panels, float button
│   ├── audio/           # Internal (system) audio recorder (Windows only)
│   └── screen_recorder.py, webcam_recorder.py, ...
└── recordings/          # Output (created automatically)
    ├── webcam/          # Webcam MP4s
    ├── screen/          # Screen MP4s
    └── audio/           # System audio WAVs (Windows only)
```

## Configuration

- **Countdown length:** edit `COUNTDOWN_SECONDS` in `recorder/config.py`.
- **Recordings location:** by default `recordings/` is created next to the script / exe, with `webcam/`, `screen/`, and `audio/` subfolders. `.gitkeep` files are created so these folders can be tracked in Git even when empty.

## License

Use as you like.
