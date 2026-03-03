# Screen & Webcam Recorder

Desktop app to record screen and/or webcam as MP4, with a floating start/stop button and optional countdown.

## Features

- **Screen** and **webcam** recording (separate or both at once, synced)
- **System audio**: Windows via WASAPI (PyAudioWPatch); Linux via PulseAudio/PipeWire monitor (sounddevice)
- **MP4** video output for webcam and screen
- **Floating button** window (always on top, draggable to any monitor) with one big Start/Stop
- **Countdown** before recording starts (default 5 seconds, configurable)
- **Recordings** saved under `recordings/webcam/`, `recordings/screen/`, and `recordings/audio/`
- **Emotion detection** overlay on webcam preview; CSV saved only while recording to `recordings/detection/<email>_emotion.csv`

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

## Testing emotion detection results

After recording with emotion detection on, the CSV is at `recordings/detection/<email>_emotion.csv`. To view a summary (row count, time range, emotion distribution, sample rows):

```bash
python scripts/view_emotion_csv.py recordings/detection/makaryanalber@gmail.com_emotion.csv
# or, to use the latest CSV in that folder:
python scripts/view_emotion_csv.py
```

To run full pipeline emotion analysis on existing webcam + screen videos (writes a new CSV and annotated video):

```bash
python analyze_recording.py --webcam recordings/webcam/<email>_webcam.mp4 --screen recordings/screen/<email>_screen.mp4
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
