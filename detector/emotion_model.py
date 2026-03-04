from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any, Optional, Tuple

import cv2
import numpy as np
from deepface import DeepFace


@dataclass
class EmotionResult:
    """Single-frame emotion prediction with optional face bounding box."""

    time_s: float
    top_emotion: str
    scores: Dict[str, float]
    emotion_pct: float  # 0–100, score for dominant emotion
    face_bbox: Optional[Tuple[int, int, int, int]]  # (x, y, w, h) or None if no face


class DeepFaceEmotionModel:
    """
    Thin wrapper around DeepFace for emotion analysis.

    NOTE:
    - This is CPU-heavy; by default you should not run it on every frame.
    - Use it on downsampled frames (e.g. 1 fps or 0.5 fps) and reuse
      the last prediction for intermediate frames when aligning.
    """

    def __init__(self):
        # Lazily initialized; DeepFace will download models on first call.
        self._model_loaded = False

    def _ensure_model(self) -> None:
        # DeepFace loads models lazily via analyze(), so nothing explicit here.
        if not self._model_loaded:
            self._model_loaded = True

    def analyze_frame(self, frame_bgr: np.ndarray, time_s: float) -> EmotionResult:
        """
        Run emotion analysis on a single BGR frame from OpenCV.

        Returns the dominant emotion and per-emotion scores.
        """
        self._ensure_model()
        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)

        # DeepFace returns either a dict or a list of dicts; request emotion so region is included.
        raw: Any = DeepFace.analyze(
            frame_rgb,
            actions=["emotion"],
            enforce_detection=False,
        )
        if isinstance(raw, list):
            raw = raw[0] if raw else {}

        emotions: Dict[str, float] = {}
        emotion_scores = raw.get("emotion") or {}
        for name, score in emotion_scores.items():
            try:
                emotions[name] = float(score)
            except Exception:
                continue

        top_emotion = raw.get("dominant_emotion") or ""
        if not top_emotion and emotions:
            top_emotion = max(emotions.items(), key=lambda kv: kv[1])[0]
        emotion_pct = float(emotions.get(top_emotion, 0.0))

        # Face bounding box: region can be dict with x, y, w, h
        face_bbox: Optional[Tuple[int, int, int, int]] = None
        region = raw.get("region") or raw.get("facial_area")
        if isinstance(region, dict):
            try:
                x = int(region.get("x", 0))
                y = int(region.get("y", 0))
                w = int(region.get("w", 0))
                h = int(region.get("h", 0))
                if w > 0 and h > 0:
                    face_bbox = (x, y, w, h)
            except (TypeError, ValueError):
                pass

        return EmotionResult(
            time_s=time_s,
            top_emotion=top_emotion,
            scores=emotions,
            emotion_pct=emotion_pct,
            face_bbox=face_bbox,
        )

