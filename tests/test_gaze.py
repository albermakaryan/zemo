"""Simple test for EyeTracker class.

Usage
-----
    uv run python -m tests gaze              # load saved model + track
    uv run python -m tests gaze --calibrate  # calibrate first, then track
"""

import argparse
import sys
import time
from pathlib import Path

if __name__ == "__main__":
    _root = Path(__file__).resolve().parent.parent
    if str(_root) not in sys.path:
        sys.path.insert(0, str(_root))


def run_gaze(force_calibrate: bool = False) -> int:
    import cv2
    from gazer.eye_tracker import EyeTracker

    # Calibrate or load
    if force_calibrate or not EyeTracker.is_model_saved():
        print("Calibrating...")
        tracker = EyeTracker.calibrate_and_create()
        print("Done. Model saved.")
    else:
        print("Loading saved model...")
        tracker = EyeTracker()
        print("Done.")

    # Open webcam
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("FAIL: could not open webcam")
        return 1

    print("Tracking — press Q to quit\n")
    while True:
        ret, frame = cap.read()
        if not ret:
            continue

        x, y = tracker.track_eyes(frame)
        print(f"gaze: ({x:.0f}, {y:.0f})" if x is not None else "gaze: blink / no face")

        cv2.imshow("gaze test", frame)
        if cv2.waitKey(1) & 0xFF in (ord("q"), 27):
            break

    cap.release()
    cv2.destroyAllWindows()
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--calibrate", action="store_true")
    args = parser.parse_args()
    sys.exit(run_gaze(force_calibrate=args.calibrate))
