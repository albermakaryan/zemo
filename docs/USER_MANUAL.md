# Recorder – User Manual

Screen & Webcam Recorder: record your screen and webcam as separate MP4 files, with optional system audio. This document describes how to install, run, and use the tool.

---

## Quick start – .exe and UI (bullet points)

**Using the .exe**
- Double‑click **Recorder.exe** (no Python or install needed).
- On first run, a **recordings** folder is created next to the exe; all videos go there (`recordings/webcam/`, `recordings/screen/`, `recordings/audio/`).
- Copy the exe to any folder or PC; it will create a new **recordings** folder in that location.

**UI at a glance**
- **Main window**: two preview panels (webcam + screen), live only—nothing is recorded until you start.
- **Floating button** (round, usually top‑right): always on top; drag to move (e.g. to another monitor).
- **To start recording:** click the floating button → enter your **email** in the dialog → Submit → main window minimizes → **5‑second countdown** on the button → recording starts (webcam + screen + audio if available).
- **To stop:** click the floating button again (it shows ⏹); files are saved automatically.
- **Main window (when open):** 📁 = change save folder; ▶ Play = open last recording; ⏹ Stop Both = stop all.

---

## 1. What it does

- **Webcam**: records your camera (e.g. face) as MP4.
- **Screen**: records your monitor (full screen or primary display) as MP4.
- **Audio** (Windows): records **system/computer audio** (what you hear) when available; saved as WAV and can be mixed into videos with a separate tool.
- Recordings are **synced** (webcam and screen start/stop together) and saved with your **email** in the filename (e.g. `user@example.com_webcam.mp4`).

---

## 2. Requirements

- **Python 3.7+** (for running from source), or use the standalone **Recorder.exe** (no Python needed).
- **Windows** is the main supported platform.
- **FFmpeg** (optional): for mixing audio into video; if not installed, videos are saved without embedded system audio.

---

## 3. Installation

### Option A – Run from source

1. Install Python from [python.org](https://www.python.org/downloads/) and ensure **Add Python to PATH** is checked.
2. Open a terminal in the project folder and run:
   ```bash
   pip install -r requirements.txt
   ```

### Option B – Standalone .exe

1. Build the exe (from the project folder): double‑click **`build_exe.bat`** or run `pyinstaller --clean Recorder.spec`.
2. The executable is created at **`dist\Recorder.exe`** (and optionally `dist\Recorder_1.0.0.exe`).
3. Copy **Recorder.exe** to any folder or another PC. On first run it creates a **`recordings`** folder next to the exe.

---

## 4. How to run

- **Windows (from source):** double‑click **`run_recorder.bat`**, or in a terminal: `python main.py`.
- **Standalone:** double‑click **`Recorder.exe`**.

---

## 5. Using the application

### 5.1 Startup

When you start the app you see:

1. **Main window** with two panels:
   - **Webcam** – live preview of your camera (no recording yet).
   - **Screen** – live preview of your screen (no recording yet).
2. A **small floating button** (round, usually top‑right) that stays on top of other windows.

Use the previews to check the picture and adjust the camera if needed. Nothing is recorded until you start recording (see below).

### 5.2 Starting a recording

1. Click the **floating button** (⏺).
2. An **email** dialog appears. Enter your email (e.g. university or work) and click **Submit**.
   - This email is used in the filenames of the saved videos.
   - If you cancel the dialog, no recording is started.
3. After you submit:
   - The **main window minimizes** (only the small button remains visible).
   - A **5‑second countdown** runs on the button (5, 4, 3, 2, 1).
   - When the countdown reaches zero, **recording starts** (webcam + screen, and system audio if available).

You can move the floating button by dragging it (e.g. to another monitor).

### 5.3 Stopping a recording

1. Click the **floating button** again (it now shows ⏹).
2. Recording stops. Files are written to disk.
3. You can restore the main window from the taskbar to see status and open the recording folder.

### 5.4 Where files are saved

All recordings are stored in a **`recordings`** folder:

- Next to **Recorder.exe** if you run the exe.
- Next to the project folder if you run **`python main.py`** or **`run_recorder.bat`**.

Inside **`recordings`** you will find:

| Folder   | Content                                      |
|----------|----------------------------------------------|
| `webcam/`| Webcam MP4 files (e.g. `user@example.com_webcam.mp4`) |
| `screen/`| Screen MP4 files (e.g. `user@example.com_screen.mp4`) |
| `audio/` | System audio WAV files (e.g. `user@example.com_audio.wav`) |

You can change the **save location** using the **📁** button in the main window (before or after recording). The folder you choose will contain `webcam/`, `screen/`, and `audio/` subfolders.

### 5.5 Main window (when not minimized)

- **⏺ Record Both** – start recording from the main window (will ask for email if not set, then start with countdown if using the float button flow).
- **⏹ Stop Both** – stop all recordings.
- **📁** – choose the base folder for recordings.
- **▶ Play** – open the last recorded file (per panel).
- **Status** – each panel shows file name and recording status (e.g. “Recording as: user@example.com”).

---

## 6. Tips

- **Preview first:** Use the initial preview to frame your face and check the screen area before clicking the floating button to record.
- **Single visible control:** After you enter your email, only the floating button is shown so you can record without the main window in the way.
- **Clean exit:** Close the main window (or use the X button) to stop any preview/recording and exit. If you press **Ctrl+C** in a terminal, the app will also shut down cleanly.

---

## 7. Configuration (advanced)

If you run from source, you can edit **`recorder/config.py`** to change:

| Setting              | Meaning                          | Default |
|----------------------|----------------------------------|---------|
| `COUNTDOWN_SECONDS`  | Seconds before recording starts  | 5       |
| `FPS`                | Target frames per second         | 25      |
| `CAMERA_INDEX`       | Webcam device (0 = first)        | 0       |
| `MONITOR_INDEX`      | Monitor to capture (1 = primary)  | 1       |
| `RECORDING_WIDTH` / `RECORDING_HEIGHT` | Force same size for webcam and screen | None (use source size) |

Save location can always be changed from the app with the 📁 button.

---

## 8. Troubleshooting

| Problem | What to try |
|--------|-------------|
| “Missing packages” on start | Run `pip install -r requirements.txt` in the project folder. |
| No webcam preview | Check camera permissions and that no other app is using the camera; try another `CAMERA_INDEX` in config. |
| No screen preview | On Windows, screen capture usually works; ensure no blocking security software. |
| No system audio | System/loopback audio is Windows-only and may require correct playback device; see `recorder/audio/README.md` for details. |
| Recordings in wrong place | Use the 📁 button in the main window to set the base folder for `webcam/`, `screen/`, and `audio/`. |
| App does not exit cleanly | Use the window X button or Ctrl+C once; the app will stop recorders and exit. |

---

## 9. Building the .exe (for developers)

1. Install dependencies: `pip install -r requirements.txt`
2. Run **`build_exe.bat`** (or `pyinstaller --clean Recorder.spec`)
3. Output: **`dist\Recorder.exe`**. Version is read from **`VERSION`** (e.g. `1.0.0`); the batch also copies the exe to **`dist\Recorder_<version>.exe`**

---

*Recorder – Screen & Webcam Recorder*
