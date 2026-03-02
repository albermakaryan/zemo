"""
View merged (time-aligned) webcam + screen side by side.

Run from project root:
  python -m validation.view_merged [email]
  python validation/view_merged.py

Uses the latest recording if no email given. Press Q to quit, SPACE to pause.
Audio is in recordings/audio/<email>_audio.wav — play it in a player for full sync.
"""

import sys
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

import numpy as np
import cv2
from validation.merge_recordings import open_synced, _latest_recording_base
from recorder.config import RECORDINGS_DIR


def main():
    email = sys.argv[1].strip() if len(sys.argv) > 1 else ""
    if not email or email.lower() == "user":
        base = _latest_recording_base(RECORDINGS_DIR)
        email = base if base else ""
    if not email:
        print("No recording found. Usage: python -m validation.view_merged [email]")
        sys.exit(1)

    print("Loading:", email)
    synced = open_synced(email)
    n = synced.n_frames
    if n == 0:
        print("No frames to show.")
        sys.exit(1)
    print("Frames:", n, "| Duration: {:.1f}s | Press Q to quit, SPACE to pause".format(synced.duration_sec))

    win = "Merged: Webcam | Screen (aligned)"
    cv2.namedWindow(win, cv2.WINDOW_NORMAL)
    paused = False
    i = 0
    frame_ms = int(1000 / synced.fps)

    while True:
        webcam = synced.get_webcam_frame(i)
        screen = synced.get_screen_frame(i)
        if webcam is None and screen is None:
            break
        # Resize to same height for side-by-side
        h = 360
        if webcam is not None:
            r = h / webcam.shape[0]
            webcam = cv2.resize(webcam, (int(webcam.shape[1] * r), h))
            cv2.putText(webcam, "Webcam", (8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        else:
            webcam = np.zeros((h, 320, 3), dtype=np.uint8)
            cv2.putText(webcam, "No webcam", (8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        if screen is not None:
            r = h / screen.shape[0]
            screen = cv2.resize(screen, (int(screen.shape[1] * r), h))
            cv2.putText(screen, "Screen", (8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        else:
            screen = np.zeros((h, 320, 3), dtype=np.uint8)
            cv2.putText(screen, "No screen", (8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        combined = np.hstack([webcam, screen])
        cv2.putText(
            combined, "Frame {} / {}  (t={:.2f}s)".format(i, n, i / synced.fps),
            (8, h - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2
        )
        cv2.imshow(win, combined)
        key = cv2.waitKey(frame_ms if not paused else 0)
        if key == ord("q") or key == 27:
            break
        if key == ord(" "):
            paused = not paused
        if not paused:
            i = (i + 1) % n

    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
