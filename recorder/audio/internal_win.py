"""
Internal (system) audio on Windows: capture what is playing on the PC.

Uses WASAPI loopback via PyAudioWPatch. Requires: pip install PyAudioWPatch
"""

import sys
import threading
import time
import wave
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from recorder import config
from recorder.common import email_filename_part

try:
    import pyaudiowpatch as pyaudio
    _HAS_PYAUDIOWPATCH = True
except ImportError:
    pyaudio = None
    _HAS_PYAUDIOWPATCH = False


def is_loopback_available() -> bool:
    """True if we can record system audio (Windows + PyAudioWPatch + WASAPI loopback)."""
    if not _HAS_PYAUDIOWPATCH or sys.platform != "win32":
        return False
    try:
        with pyaudio.PyAudio() as p:
            p.get_host_api_info_by_type(pyaudio.paWASAPI)
        return True
    except Exception:
        return False


def _get_loopback_device(p: "pyaudio.PyAudio") -> Optional[Dict[str, Any]]:
    """Get the default WASAPI output device in loopback mode, or None."""
    try:
        wasapi_info = p.get_host_api_info_by_type(pyaudio.paWASAPI)
    except OSError:
        return None
    default_speakers = p.get_device_info_by_index(wasapi_info["defaultOutputDevice"])
    if default_speakers.get("isLoopbackDevice"):
        return default_speakers
    for loopback in p.get_loopback_device_info_generator():
        if default_speakers["name"] in loopback["name"]:
            return loopback
    return None


class InternalAudioRecorder:
    """
    Record internal (system) audio via WASAPI loopback on Windows.

    Use case: capture audio from an online course playing in the browser
    while screen and webcam are recorded. Start/stop with the same barrier
    and stop_time as video so the WAV aligns with the video duration.
    """

    def __init__(
        self,
        on_status: Optional[Callable[[str, str], None]] = None,
        on_done: Optional[Callable[[str], None]] = None,
    ):
        self.on_status = on_status or (lambda _s, _m: None)
        self.on_done = on_done or (lambda _f: None)
        self._stop = threading.Event()
        self._stop_time: Optional[float] = None
        self._start_barrier: Optional[threading.Barrier] = None
        self._start_time_ref: Optional[List[Optional[float]]] = None
        self._thread: Optional[threading.Thread] = None
        self.recording = False
        self.filename = ""

    def start(
        self,
        save_dir: str,
        start_barrier: Optional[threading.Barrier] = None,
        start_time_ref: Optional[List[Optional[float]]] = None,
        email: Optional[str] = None,
    ) -> None:
        if not _HAS_PYAUDIOWPATCH:
            self.on_status("error", "Internal audio requires PyAudioWPatch on Windows")
            return
        if sys.platform != "win32":
            self.on_status("error", "Internal audio is Windows-only (WASAPI loopback)")
            return
        self._stop.clear()
        self._stop_time = None
        self._start_barrier = start_barrier
        self._start_time_ref = start_time_ref
        self.recording = True
        save_path = Path(save_dir)
        save_path.mkdir(parents=True, exist_ok=True)
        name_part = email_filename_part(email) if email else "user"
        self.filename = str(save_path / f"{name_part}_audio{config.AUDIO_EXT}")
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self, stop_time: Optional[float] = None) -> None:
        self._stop_time = stop_time
        self._stop.set()
        self.recording = False

    def join(self, timeout: float = 5.0) -> None:
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)

    def _run(self) -> None:
        # (timestamp, bytes) so we can place each chunk at the correct time; silence = no chunk
        chunks: List[Tuple[float, bytes]] = []
        t0: Optional[float] = None
        sample_rate = config.AUDIO_SAMPLE_RATE
        nchannels = 2
        sampwidth = 2  # 16-bit

        try:
            with pyaudio.PyAudio() as p:
                device = _get_loopback_device(p)
                if not device:
                    self.on_status("error", "No WASAPI loopback device found")
                    self.recording = False
                    return
                sample_rate = int(device["defaultSampleRate"])
                nchannels = int(device["maxInputChannels"])
                self.on_status("recording", f"→ {Path(self.filename).name} (system audio)")

                if self._start_barrier is not None:
                    self._start_barrier.wait()
                self._stream_started = False

                def callback(in_data: bytes, frame_count: int, time_info: dict, status: int) -> tuple:
                    if self._stream_started and not self._stop.is_set():
                        # Wall-clock time so (ts - t0) gives correct offset; time_info values can be 0 or wrong
                        chunks.append((time.time(), in_data))
                    return (in_data, pyaudio.paContinue)

                stream = p.open(
                    format=pyaudio.paInt16,
                    channels=nchannels,
                    rate=sample_rate,
                    frames_per_buffer=config.AUDIO_CHUNK_SIZE,
                    input=True,
                    input_device_index=device["index"],
                    stream_callback=callback,
                )
                stream.start_stream()
                t0 = time.time()
                self._stream_started = True
                ref = getattr(self, "_start_time_ref", None)
                video_t0 = (ref[0] if ref and len(ref) and ref[0] is not None else t0)
                self._video_t0 = video_t0
                try:
                    while not self._stop.is_set():
                        time.sleep(0.05)
                finally:
                    stream.stop_stream()
                    stream.close()

        except Exception as e:
            self.on_status("error", str(e))
            self.recording = False
            return

        # Place each chunk at its timestamp so silence stays in the right place; then prepend/pad for video sync
        try:
            t_final = getattr(self, "_stop_time", None) or time.time()
            t0_val = t0 if t0 is not None else time.time()
            video_t0_val = getattr(self, "_video_t0", t0_val)
            start_offset = max(0.0, t0_val - video_t0_val)
            elapsed_audio = t_final - t0_val
            bytes_per_frame = nchannels * sampwidth
            expected_body_frames = int(elapsed_audio * sample_rate) if elapsed_audio > 0 else 0
            offset_frames = int(start_offset * sample_rate)
            total_frames_video = int((t_final - video_t0_val) * sample_rate)

            # Full timeline from t0 to t_final: zeros (silence) everywhere; place each chunk at (ts - t0)
            body_len = expected_body_frames * bytes_per_frame
            audio_body = bytearray(body_len)
            for ts, data in sorted(chunks, key=lambda x: x[0]):
                frame_start = int((ts - t0_val) * sample_rate)
                n_frames_chunk = len(data) // bytes_per_frame
                if frame_start < 0:
                    skip = min(-frame_start, n_frames_chunk)
                    data = data[skip * bytes_per_frame :]
                    n_frames_chunk -= skip
                    frame_start = 0
                if frame_start >= expected_body_frames or n_frames_chunk <= 0:
                    continue
                copy_frames = min(n_frames_chunk, expected_body_frames - frame_start)
                copy_len = copy_frames * bytes_per_frame
                start_byte = frame_start * bytes_per_frame
                audio_body[start_byte : start_byte + copy_len] = data[:copy_len]

            # If no chunks were placed (e.g. no data from device), body is all zeros — that's valid
            silence_pre = b"\x00" * (offset_frames * bytes_per_frame)
            data_to_write = silence_pre + bytes(audio_body)
            frames_so_far = offset_frames + expected_body_frames
            if frames_so_far < total_frames_video:
                data_to_write += b"\x00" * ((total_frames_video - frames_so_far) * bytes_per_frame)
            frames_to_write = total_frames_video

            with wave.open(self.filename, "wb") as wf:
                wf.setnchannels(nchannels)
                wf.setsampwidth(sampwidth)
                wf.setframerate(sample_rate)
                wf.setnframes(frames_to_write)
                wf.writeframes(data_to_write)
        except Exception as e:
            self.on_status("error", f"Failed to write WAV: {e}")
        finally:
            self.recording = False
            self.on_done(self.filename)
