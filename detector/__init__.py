"""
Emotion analysis utilities for webcam/screen recordings.

Current implementation focuses on:
  - Extracting per-frame (or per-second) emotions from a webcam MP4
  - Aligning those timestamps with a parallel screen recording
"""

from .emotion_model import EmotionResult, DeepFaceEmotionModel  # noqa: F401
from .pair_analyzer import analyze_webcam_and_screen  # noqa: F401

