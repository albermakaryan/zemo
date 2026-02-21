# Screen & Webcam Recorder

Desktop app to record screen and/or webcam as MP4, with a floating start/stop button and optional countdown.

## Features

- **Screen** and **webcam** recording (separate or both at once, synced)
- **Audio**: screen recording captures **system/computer audio** (what you hear); webcam recording captures **microphone**
- **MP4** output (video + AAC audio when FFmpeg is available)
- **Floating button** window (always on top, draggable to any monitor) with one big Start/Stop
- **Countdown** before recording starts (default 5 seconds, configurable)
- **Recordings** saved under `recordings/webcam/` and `recordings/screen/`

## Requirements

- Python 3.7+
- Windows (tested); macOS/Linux may work with small adjustments
- **FFmpeg** on PATH for audio (download from [ffmpeg.org](https://ffmpeg.org/) or `winget install ffmpeg`). Without FFmpeg, videos are saved without sound.

## Setup (once per machine)

1. Install Python from [python.org](https://www.python.org/downloads/) and ensure **Add Python to PATH** is checked.
2. In the project folder:
   ```bash
   pip install -r requirements.txt
   ```

## Run

- **Windows:** double-click `run_recorder.bat`
- **Command line:** `python main.py`
- **Standalone .exe:** double-click `dist\Recorder.exe` after building (see below)

If Python is missing, the batch file opens the Python download page.

## Build a standalone .exe (Windows)

1. Install dependencies and run the app at least once: `pip install -r requirements.txt`
2. Double-click **`build_exe.bat`** (or in a terminal: `pyinstaller --clean Recorder.spec`)
3. The executable is created at **`dist\Recorder.exe`**

Copy `Recorder.exe` to any folder (or another PC). On first run it will create a `recordings` folder next to the exe (with `webcam/` and `screen/` inside) for saving videos. No Python installation needed on that machine.

## Project layout

```
em_det/
├── main.py              # Entry point (dependency check + launch)
├── record.py            # Legacy entry (calls main.py)
├── run_recorder.bat     # Windows launcher
├── requirements.txt
├── recorder/            # Package
│   ├── __init__.py
│   ├── config.py        # Paths, constants, theme
│   ├── recorders.py     # WebcamRecorder, ScreenRecorder
│   └── ui.py            # App, RecorderPanel, FloatButtonWindow
└── recordings/          # Output (created automatically)
    ├── webcam/          # Webcam MP4s
    └── screen/          # Screen MP4s
```

## Configuration

- **Countdown length:** edit `COUNTDOWN_SECONDS` in `recorder/config.py`.
- **Save location:** use the folder button (📁) in the app to choose a base folder; it will contain `webcam/` and `screen/` subfolders.

## License

Use as you like.
