from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

import cv2

from .emotion_model import DeepFaceEmotionModel, EmotionResult


@dataclass
class AlignedEmotionSample:
    """
    Emotion prediction for a webcam frame, aligned to a screen timeline.
    """

    time_s: float
    webcam_frame_idx: int
    screen_frame_idx: int
    top_emotion: str
    emotion_pct: float
    face_bbox: Optional[Tuple[int, int, int, int]]  # (x, y, w, h)


def _safe_fps(cap: cv2.VideoCapture) -> float:
    fps = cap.get(cv2.CAP_PROP_FPS)
    return fps if fps and fps > 0 else 30.0


def _draw_annotations(
    frame,
    top_emotion: str,
    emotion_pct: float,
    face_bbox: Optional[Tuple[int, int, int, int]],
) -> None:
    """Draw face bounding box and emotion label + percentage on frame (in-place)."""
    if face_bbox is not None:
        x, y, w, h = face_bbox
        cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
    label = f"{top_emotion} {emotion_pct:.0f}%"
    cv2.putText(frame, label, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)


def analyze_webcam_and_screen(
    webcam_path: str,
    screen_path: str,
    output_csv: str,
    sample_every_s: float = 1.0,
    output_annotated_video: Optional[str] = None,
) -> List[AlignedEmotionSample]:
    """
    Analyze a webcam MP4 with DeepFace and align results to a parallel screen MP4.

    Writes CSV with: time_s, webcam_frame_idx, screen_frame_idx, top_emotion,
    emotion_pct, face_x, face_y, face_w, face_h.
    If output_annotated_video is set, writes a short clip with face box and emotion label.
    """
    webcam_file = Path(webcam_path)
    screen_file = Path(screen_path)
    if not webcam_file.exists():
        raise FileNotFoundError(f"Webcam video not found: {webcam_file}")
    if not screen_file.exists():
        raise FileNotFoundError(f"Screen video not found: {screen_file}")

    cap_webcam = cv2.VideoCapture(str(webcam_file))
    cap_screen = cv2.VideoCapture(str(screen_file))
    if not cap_webcam.isOpened():
        raise RuntimeError(f"Cannot open webcam video: {webcam_file}")
    if not cap_screen.isOpened():
        raise RuntimeError(f"Cannot open screen video: {screen_file}")

    try:
        fps_webcam = _safe_fps(cap_webcam)
        fps_screen = _safe_fps(cap_screen)

        model = DeepFaceEmotionModel()
        samples: List[AlignedEmotionSample] = []

        next_sample_t: float = 0.0
        frame_idx = 0

        while True:
            ok, frame = cap_webcam.read()
            if not ok:
                break
            t = frame_idx / fps_webcam

            if t + 1e-6 >= next_sample_t:
                # Analyze this frame
                emo: EmotionResult = model.analyze_frame(frame, time_s=t)

                # Map to closest screen frame index by timestamp
                screen_frame_idx = int(round(t * fps_screen))

                samples.append(
                    AlignedEmotionSample(
                        time_s=t,
                        webcam_frame_idx=frame_idx,
                        screen_frame_idx=screen_frame_idx,
                        top_emotion=emo.top_emotion,
                        emotion_pct=emo.emotion_pct,
                        face_bbox=emo.face_bbox,
                    )
                )
                next_sample_t += sample_every_s

            frame_idx += 1

        # Write CSV with bbox and emotion percentage
        out_path = Path(output_csv)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "time_s",
                    "webcam_frame_idx",
                    "screen_frame_idx",
                    "top_emotion",
                    "emotion_pct",
                    "face_x",
                    "face_y",
                    "face_w",
                    "face_h",
                ]
            )
            for s in samples:
                x, y, w, h = s.face_bbox if s.face_bbox else (0, 0, 0, 0)
                writer.writerow(
                    [
                        f"{s.time_s:.3f}",
                        s.webcam_frame_idx,
                        s.screen_frame_idx,
                        s.top_emotion,
                        f"{s.emotion_pct:.2f}",
                        x,
                        y,
                        w,
                        h,
                    ]
                )

        # Optional: write annotated video (face box + emotion label and %)
        if output_annotated_video and samples:
            out_video = Path(output_annotated_video)
            out_video.parent.mkdir(parents=True, exist_ok=True)
            cap_webcam2 = cv2.VideoCapture(str(webcam_file))
            if cap_webcam2.isOpened():
                fourcc = int(cap_webcam2.get(cv2.CAP_PROP_FOURCC))
                if fourcc == 0:
                    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
                out_w = int(cap_webcam2.get(cv2.CAP_PROP_FRAME_WIDTH))
                out_h = int(cap_webcam2.get(cv2.CAP_PROP_FRAME_HEIGHT))
                out_fps = max(1.0, 1.0 / sample_every_s)
                writer = cv2.VideoWriter(
                    str(out_video), fourcc, out_fps, (out_w, out_h)
                )
                sample_idx = 0
                for idx, s in enumerate(samples):
                    cap_webcam2.set(cv2.CAP_PROP_POS_FRAMES, s.webcam_frame_idx)
                    ok, fr = cap_webcam2.read()
                    if ok:
                        _draw_annotations(fr, s.top_emotion, s.emotion_pct, s.face_bbox)
                        writer.write(fr)
                writer.release()
                cap_webcam2.release()

        return samples
    finally:
        cap_webcam.release()
        cap_screen.release()
