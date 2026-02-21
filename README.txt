RECORDER – use on any laptop
============================

You need Python installed. If it isn’t:
  - Double‑click run_recorder.bat; it will open the Python download page.
  - Install from https://www.python.org/downloads/
  - During setup, check “Add Python to PATH”.

First time on this laptop (once):
  1. Open a terminal in this folder (e.g. right‑click → Open in Terminal).
  2. Run:  pip install -r requirements.txt
  3. If you use a virtual environment (e.g. "env"), activate it first, then run the command above.

Start the app:
  Double‑click  run_recorder.bat

Build a standalone .exe (no Python needed on other PCs):
  Double‑click  build_exe.bat
  Then use  dist\Recorder.exe

Videos are saved in the recordings folder:
  recordings/webcam/   – webcam MP4s
  recordings/screen/   – screen MP4s
