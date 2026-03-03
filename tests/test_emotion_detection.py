# realtime_emotion_detector.py
from __future__ import annotations

import sys
import time
from pathlib import Path

import cv2
import numpy as np

# Make sure repo root (project folder) is importable so `import detector` works
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from detector.emotion_model import DeepFaceEmotionModel
except ImportError as e:
    print("DeepFace is not installed or detector package is missing.")
    print("Install with: pip install deepface tf-keras")
    sys.exit(1)


def draw_overlay(frame, result):
    """Draw face bbox (if any) and emotion label + percentage on frame."""
    if result.face_bbox is not None:
        x, y, w, h = result.face_bbox
        cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)

    label = f"{result.top_emotion or 'unknown'} {result.emotion_pct:.0f}%"
    cv2.putText(
        frame,
        label,
        (10, 30),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.0,
        (0, 255, 0),
        2,
    )


def main():
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Cannot open webcam (index 0).")
        sys.exit(1)

    model = DeepFaceEmotionModel()
    print("Press 'q' to quit.")

    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    sample_every_s = 0.5  # run detector twice per second
    sample_stride = max(1, int(fps * sample_every_s))

    frame_idx = 0
    last_result = None
    last_inference_time = 0.0

    while True:
        ok, frame = cap.read()
        if not ok:
            print("Failed to read frame from webcam.")
            break

        # Run emotion model every Nth frame for speed
        if frame_idx % sample_stride == 0:
            try:
                t0 = time.time()
                last_result = model.analyze_frame(
                    frame, time_s=frame_idx / fps
                )
                last_inference_time = time.time() - t0
            except Exception as e:
                # If DeepFace fails on a frame, just keep going
                print(f"emotion error: {e}")
                last_result = None

        if last_result is not None:
            draw_overlay(frame, last_result)
            info = f"{last_result.top_emotion} {last_result.emotion_pct:.0f}%  ({last_inference_time*1000:.0f} ms)"
            cv2.putText(
                frame,
                info,
                (10, 60),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 255, 255),
                1,
            )

        cv2.imshow("Real-time Emotion Detector (press 'q' to quit)", frame)
        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break

        frame_idx += 1

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()