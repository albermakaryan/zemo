"""
Merge/sync webcam, screen, and audio for analytics.

All three recordings share the same start (barrier) and stop_time, so they are
already time-aligned. Use a common time base:
  - Video: frame index i → time_sec = i / FPS
  - Audio: time_sec → sample indices = time_sec * sample_rate (e.g. 44100)

This module lets you load the three streams and access them by frame index or time.
"""

import sys
from pathlib import Path
from typing import Optional, Tuple

import cv2
import numpy as np

_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from recorder.config import (
    get_webcam_dir,
    get_screen_dir,
    get_audio_dir,
    FPS,
)
from recorder.common import email_filename_part

# Default audio params (must match recorder)
AUDIO_SAMPLE_RATE = 44100
AUDIO_CHANNELS = 2
AUDIO_SAMPLE_WIDTH = 2  # 16-bit


def _load_audio_wav(path: Path) -> Tuple[np.ndarray, int]:
    """Load WAV as float32 array (channels, samples) and sample rate."""
    try:
        import wave

        with wave.open(str(path), "rb") as w:
            sr = w.getframerate()
            nch = w.getnchannels()
            nframes = w.getnframes()
            raw = w.readframes(nframes)
        dtype = np.int16
        samples = np.frombuffer(raw, dtype=dtype)
        samples = samples.reshape(-1, nch).T  # (channels, samples)
        samples = samples.astype(np.float32) / 32768.0
        return samples, sr
    except Exception:
        return np.zeros((2, 0), dtype=np.float32), AUDIO_SAMPLE_RATE


class SyncedRecordings:
    """
    Time-aligned view over one recording session: webcam video, screen video, audio.

    All three share the same start and end time, so:
      - frame_index 0 = t=0
      - frame_index i = t = i / FPS seconds
      - audio for frame i = samples from (i/FPS)*sr to ((i+1)/FPS)*sr
    """

    def __init__(
        self,
        webcam_path: Path,
        screen_path: Path,
        audio_path: Path,
        fps: float = FPS,
        audio_sample_rate: int = AUDIO_SAMPLE_RATE,
    ):
        self.fps = fps
        self.audio_sr = audio_sample_rate
        self._cap_webcam = (
            cv2.VideoCapture(str(webcam_path)) if webcam_path.exists() else None
        )
        self._cap_screen = (
            cv2.VideoCapture(str(screen_path)) if screen_path.exists() else None
        )
        self._audio, _ = (
            _load_audio_wav(audio_path)
            if audio_path.exists()
            else (np.zeros((2, 0), dtype=np.float32), audio_sample_rate)
        )
        self._n_frames_webcam = (
            int(self._cap_webcam.get(cv2.CAP_PROP_FRAME_COUNT))
            if self._cap_webcam and self._cap_webcam.isOpened()
            else 0
        )
        self._n_frames_screen = (
            int(self._cap_screen.get(cv2.CAP_PROP_FRAME_COUNT))
            if self._cap_screen and self._cap_screen.isOpened()
            else 0
        )
        self._n_audio_samples = self._audio.shape[1] if self._audio.size else 0
        self.duration_sec = (
            self._n_frames_webcam / fps if self._n_frames_webcam else 0.0
        )

    def __enter__(self):
        return self

    def __exit__(self, *args):
        if self._cap_webcam:
            self._cap_webcam.release()
        if self._cap_screen:
            self._cap_screen.release()

    @property
    def n_frames(self) -> int:
        """Common length: minimum of webcam/screen frame counts."""
        return min(
            self._n_frames_webcam if self._n_frames_webcam else 0,
            self._n_frames_screen if self._n_frames_screen else 0,
        )

    def frame_index_to_time_sec(self, frame_index: int) -> float:
        """Convert frame index to time in seconds (common time base)."""
        return frame_index / self.fps

    def time_sec_to_audio_sample_range(
        self, t_start: float, t_end: float
    ) -> Tuple[int, int]:
        """Convert time range (seconds) to audio sample indices [start, end)."""
        s0 = int(t_start * self.audio_sr)
        s1 = int(t_end * self.audio_sr)
        s0 = max(0, min(s0, self._n_audio_samples))
        s1 = max(0, min(s1, self._n_audio_samples))
        return s0, s1

    def get_webcam_frame(self, frame_index: int) -> Optional[np.ndarray]:
        """Get webcam frame at given frame index (BGR)."""
        if not self._cap_webcam or not self._cap_webcam.isOpened():
            return None
        self._cap_webcam.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
        ret, frame = self._cap_webcam.read()
        return frame if ret else None

    def get_screen_frame(self, frame_index: int) -> Optional[np.ndarray]:
        """Get screen frame at given frame index (BGR)."""
        if not self._cap_screen or not self._cap_screen.isOpened():
            return None
        self._cap_screen.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
        ret, frame = self._cap_screen.read()
        return frame if ret else None

    def get_audio_for_frame(self, frame_index: int) -> np.ndarray:
        """Get audio segment for this frame: (channels, samples) float32."""
        t0 = self.frame_index_to_time_sec(frame_index)
        t1 = self.frame_index_to_time_sec(frame_index + 1)
        s0, s1 = self.time_sec_to_audio_sample_range(t0, t1)
        if s0 >= s1:
            return np.zeros((self._audio.shape[0], 0), dtype=np.float32)
        return self._audio[:, s0:s1].copy()

    def get_audio_for_time_range(
        self, t_start_sec: float, t_end_sec: float
    ) -> np.ndarray:
        """Get audio for a time window in seconds: (channels, samples) float32."""
        s0, s1 = self.time_sec_to_audio_sample_range(t_start_sec, t_end_sec)
        if s0 >= s1:
            return np.zeros((self._audio.shape[0], 0), dtype=np.float32)
        return self._audio[:, s0:s1].copy()

    def iter_frames(self):
        """
        Yield (frame_index, webcam_frame, screen_frame, audio_chunk) for each frame.

        audio_chunk: (channels, samples) for that frame's time window.
        """
        n = self.n_frames
        for i in range(n):
            w = self.get_webcam_frame(i)
            s = self.get_screen_frame(i)
            a = self.get_audio_for_frame(i)
            yield i, w, s, a


def _latest_recording_base(recordings_root: Path) -> Optional[str]:
    """Find the most recent recording set: base name from newest *_webcam.mp4."""
    webcam_dir = recordings_root / "webcam"
    if not webcam_dir.exists():
        return None
    candidates = list(webcam_dir.glob("*_webcam.mp4"))
    if not candidates:
        return None
    latest = max(candidates, key=lambda p: p.stat().st_mtime)
    base = latest.name.replace("_webcam.mp4", "")
    return base if base else None


def open_synced(email: str, recordings_root: Optional[Path] = None) -> SyncedRecordings:
    """
    Open the three recordings for one session (by email base name).

    Example:
        with open_synced("user@edu.ysu.am") as synced:
            for i, webcam, screen, audio in synced.iter_frames():
                # merge for analytics: e.g. featurize webcam, screen, audio for frame i
                pass
    """
    from recorder.config import RECORDINGS_DIR

    root = Path(recordings_root) if recordings_root else RECORDINGS_DIR
    if not email or email.strip().lower() == "user":
        base = _latest_recording_base(root)
        name = base if base else "user"
    else:
        name = email_filename_part(email.strip())
    webcam_path = root / "webcam" / f"{name}_webcam.mp4"
    screen_path = root / "screen" / f"{name}_screen.mp4"
    audio_path = root / "audio" / f"{name}_audio.wav"
    return SyncedRecordings(webcam_path, screen_path, audio_path)


if __name__ == "__main__":
    from recorder.config import RECORDINGS_DIR

    email = sys.argv[1].strip() if len(sys.argv) > 1 else ""
    base = (
        _latest_recording_base(RECORDINGS_DIR)
        if not email or email.lower() == "user"
        else None
    )
    if base:
        email = base
        print("Using latest recording:", email)
    elif not email:
        print("Usage: python -m validation.merge_recordings [email]")
        print(
            "  If no email given, uses the most recent recording in recordings/webcam/"
        )
        sys.exit(1)
    with open_synced(email) as synced:
        print("FPS:", synced.fps)
        print("Duration (sec):", round(synced.duration_sec, 2))
        print("N frames (common):", synced.n_frames)
        if synced.n_frames > 0:
            a = synced.get_audio_for_frame(0)
            print("Audio shape for frame 0:", a.shape)
        else:
            print(
                "No frames found. Check that recordings/webcam/ and recordings/screen/ have matching *_webcam.mp4 and *_screen.mp4"
            )
