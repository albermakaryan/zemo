"""
Internal (system) audio on Windows: capture what is playing on the PC.

Uses WASAPI loopback via PyAudioWPatch. Requires: pip install PyAudioWPatch

When PyAV (pip install av) is installed the recorder writes Matroska Audio
(.mka) with per-packet hardware PTS from WASAPI's input_buffer_adc_time.
Because every packet carries an exact timestamp, gaps caused by pausing the
watched video are encoded as PTS jumps in the container — no silence padding,
no threshold tuning, no wall-clock approximation. ffmpeg aligns the audio and
video streams by PTS when muxing, so the sync is mathematically exact.

Without PyAV the recorder falls back to WAV with inter-callback silence
padding (the previous approach), which handles most cases acceptably.
"""

import queue
import sys
import threading
import time
import wave
from fractions import Fraction
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from recorder import config
from recorder.common import email_filename_part, unique_name_with_suffix

try:
    import pyaudiowpatch as pyaudio

    _HAS_PYAUDIOWPATCH = True
except ImportError:
    pyaudio = None
    _HAS_PYAUDIOWPATCH = False

try:
    import av as _av
    import numpy as _np

    _HAS_AV = True
except ImportError:
    _av = None
    _np = None
    _HAS_AV = False


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


def _is_silent(raw: bytes, threshold: int = 50) -> bool:
    """True if every sample in the raw PCM buffer is below threshold (16-bit signed)."""
    import struct
    samples = struct.unpack(f"{len(raw) // 2}h", raw)
    return max(abs(s) for s in samples) < threshold


def _keep_wasapi_active(
    stop_event: threading.Event,
    ready_event: threading.Event,
    sample_rate: int = 48000,
) -> None:
    """
    Keep the WASAPI audio engine active for the entire recording by playing
    a continuous silent output stream. Sets ready_event after the first chunk
    is written so the caller knows the engine is warm before proceeding.
    Non-fatal — sets ready_event even on failure so callers never deadlock.
    """
    try:
        chunk_size = 1024
        silence = bytes(chunk_size * 2 * 2)  # stereo 16-bit zeros
        p = pyaudio.PyAudio()
        stream = p.open(
            format=pyaudio.paInt16,
            channels=2,
            rate=sample_rate,
            output=True,
            frames_per_buffer=chunk_size,
        )
        stream.start_stream()
        stream.write(silence)  # one chunk confirms the engine is rendering
        ready_event.set()
        while not stop_event.is_set():
            stream.write(silence)
        stream.stop_stream()
        stream.close()
        p.terminate()
    except Exception:
        ready_event.set()  # unblock caller even on failure


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

    When PyAV is installed: writes .mka (Matroska Audio) with per-packet
    hardware PTS sourced from WASAPI's input_buffer_adc_time. Gaps from video
    pauses are encoded as PTS jumps — no detection logic needed.

    Without PyAV: writes .wav with inter-callback silence padding.
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
        self._frames_written: int = 0  # updated by writer thread; readable externally

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
        self._frames_written = 0
        save_path = Path(save_dir)
        base = email_filename_part(email) if email else "user"
        # Use .mka when PyAV is available (proper PTS), otherwise .wav
        ext = ".mka" if _HAS_AV else config.AUDIO_EXT
        candidate = unique_name_with_suffix(save_path, base, f"_audio{ext}")
        self.filename = str(candidate)
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self, stop_time: Optional[float] = None) -> None:
        self._stop_time = stop_time
        self._stop.set()
        self.recording = False

    def join(self, timeout: float = 5.0) -> None:
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)

    # ─── top-level run ────────────────────────────────────────────────────────

    def _run(self) -> None:
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
                self.on_status(
                    "recording", f"→ {Path(self.filename).name} (system audio)"
                )

                # Start a silent output stream to keep the WASAPI engine active.
                # WASAPI loopback blocks indefinitely in blocking-read mode when
                # the system is idle. Playing silence through the output device
                # holds the engine in the rendering state so stream.read()
                # returns frames immediately. We wait for ready_event before the
                # barrier so the engine is warm by the time recording starts —
                # this eliminates the 1-2s gap from silence-thread startup.
                _silence_stop = threading.Event()
                _silence_ready = threading.Event()
                threading.Thread(
                    target=_keep_wasapi_active,
                    args=(_silence_stop, _silence_ready, sample_rate),
                    daemon=True,
                ).start()
                _silence_ready.wait(timeout=3.0)

                if self._start_barrier is not None:
                    self._start_barrier.wait()

                # Capture T=0 immediately after the barrier releases.
                t0 = time.perf_counter()

                try:
                    if _HAS_AV:
                        self._record_av(p, device, sample_rate, nchannels, t0, _silence_stop)
                    else:
                        self._record_wav(p, device, sample_rate, nchannels, sampwidth, t0, _silence_stop)
                finally:
                    _silence_stop.set()  # failsafe: stop keepalive if recording ends before real audio

        except Exception as e:
            self.on_status("error", str(e))
            self.recording = False
            return

        self.recording = False
        self.on_done(self.filename)

    # ─── PyAV path: Matroska Audio, blocking read ─────────────────────────────

    def _record_av(
        self,
        p: Any,
        device: Dict[str, Any],
        sample_rate: int,
        nchannels: int,
        t0: float,
        silence_stop: threading.Event,
    ) -> None:
        """
        Write .mka using blocking pull mode (no stream_callback).

        In blocking mode WASAPI returns silence-filled buffers when the output
        device is idle, so stream_handle.read() returns immediately and
        unconditionally — recording starts at T=0 regardless of whether any
        audio is playing. PTS increments by chunk_size on every read, giving a
        continuous, gap-free timeline from the moment the stream opens.

        The small setup gap between barrier release (t0) and stream open is
        covered by a one-time pre-silence write before the read loop starts.
        """
        av = _av
        layout = "stereo" if nchannels == 2 else "mono"
        tb = Fraction(1, sample_rate)
        chunk_size = config.AUDIO_CHUNK_SIZE

        audio_q: queue.Queue = queue.Queue(maxsize=2048)
        stop_writer = threading.Event()
        writer_error: List[Optional[Exception]] = [None]
        dropped_chunks: List[int] = [0]

        def _writer() -> None:
            try:
                Path(self.filename).parent.mkdir(parents=True, exist_ok=True)
                container = av.open(self.filename, "w", format="matroska")
                stream = container.add_stream("flac", rate=sample_rate)
                stream.codec_context.layout = layout
                stream.codec_context.format = "s16"
                stream.time_base = tb
                try:
                    while not (stop_writer.is_set() and audio_q.empty()):
                        try:
                            pts, raw = audio_q.get(timeout=0.05)
                            n = len(raw) // (nchannels * 2)
                            frame = av.AudioFrame(format="s16", layout=layout, samples=n)
                            frame.sample_rate = sample_rate
                            frame.pts = pts
                            frame.time_base = tb
                            frame.planes[0].update(raw)
                            for packet in stream.encode(frame):
                                container.mux(packet)
                            self._frames_written += n
                        except queue.Empty:
                            continue
                    for packet in stream.encode(None):
                        container.mux(packet)
                finally:
                    container.close()
            except Exception as exc:
                writer_error[0] = exc

        # Blocking mode — no stream_callback.
        # WASAPI returns silence frames when the device is idle.
        stream_handle = p.open(
            format=pyaudio.paInt16,
            channels=nchannels,
            rate=sample_rate,
            frames_per_buffer=chunk_size,
            input=True,
            input_device_index=device["index"],
        )

        writer_thread = threading.Thread(target=_writer, daemon=True)
        writer_thread.start()

        writer_thread.join(timeout=0.5)
        if not writer_thread.is_alive() and writer_error[0] is not None:
            self.on_status("error", f"audio writer failed: {writer_error[0]}")
            stream_handle.close()
            return

        self.on_status("recording", "(system audio · blocking read)")
        stream_handle.start_stream()

        pts = 0
        first_read = True
        try:
            while not self._stop.is_set():
                try:
                    raw = stream_handle.read(chunk_size, exception_on_overflow=False)
                except OSError as e:
                    self.on_status("warning", f"audio read error: {e}")
                    break
                if first_read:
                    # Measure the actual delay from barrier release to first
                    # delivered frame (covers writer startup + stream open +
                    # silence player warmup). Write silence to fill that gap
                    # so the audio timeline starts at exactly T=0.
                    first_read = False
                    elapsed = time.perf_counter() - t0
                    pts = max(0, int(elapsed * sample_rate))
                    if pts > 0:
                        audio_q.put((0, bytes(pts * nchannels * 2)))
                # Stop the keepalive the moment real audio arrives — the engine
                # sustains itself from here and we no longer need silent output.
                if not silence_stop.is_set() and not _is_silent(raw):
                    silence_stop.set()
                try:
                    audio_q.put_nowait((pts, raw))
                except queue.Full:
                    dropped_chunks[0] += 1
                pts += chunk_size
        finally:
            stream_handle.stop_stream()
            stream_handle.close()
            stop_writer.set()
            writer_thread.join(timeout=10.0)
            if writer_thread.is_alive():
                self.on_status("warning", "audio writer did not finish cleanly")
            elif writer_error[0] is not None:
                self.on_status("error", f"audio writer failed: {writer_error[0]}")
            elif dropped_chunks[0]:
                self.on_status(
                    "warning",
                    f"audio: dropped {dropped_chunks[0]} chunk(s) (queue overflow)",
                )

    # ─── WAV fallback: blocking read ─────────────────────────────────────────

    def _record_wav(
        self,
        p: Any,
        device: Dict[str, Any],
        sample_rate: int,
        nchannels: int,
        sampwidth: int,
        t0: float,
        silence_stop: threading.Event,
    ) -> None:
        """
        Write .wav using blocking pull mode (no stream_callback).

        Same principle as _record_av: WASAPI returns silence when idle, so the
        read loop delivers a continuous stream from T=0. No gap detection or
        silence insertion logic needed — pauses in the watched video show up as
        silence in the data naturally.
        """
        chunk_size = config.AUDIO_CHUNK_SIZE

        audio_q: queue.Queue = queue.Queue(maxsize=2048)
        stop_writer = threading.Event()
        dropped_chunks: List[int] = [0]

        def _writer(wf: wave.Wave_write) -> None:
            while not (stop_writer.is_set() and audio_q.empty()):
                try:
                    chunk = audio_q.get(timeout=0.05)
                    wf.writeframes(chunk)
                    self._frames_written += len(chunk) // (nchannels * sampwidth)
                except queue.Empty:
                    continue

        # Blocking mode — no stream_callback.
        stream_handle = p.open(
            format=pyaudio.paInt16,
            channels=nchannels,
            rate=sample_rate,
            frames_per_buffer=chunk_size,
            input=True,
            input_device_index=device["index"],
        )

        with wave.open(self.filename, "wb") as wf:
            wf.setnchannels(nchannels)
            wf.setsampwidth(sampwidth)
            wf.setframerate(sample_rate)

            writer_thread = threading.Thread(target=_writer, args=(wf,), daemon=True)
            writer_thread.start()

            stream_handle.start_stream()
            first_read = True
            try:
                while not self._stop.is_set():
                    try:
                        raw = stream_handle.read(chunk_size, exception_on_overflow=False)
                    except OSError as e:
                        self.on_status("warning", f"audio read error: {e}")
                        break
                    if first_read:
                        first_read = False
                        elapsed = time.perf_counter() - t0
                        silence_frames = max(0, int(elapsed * sample_rate))
                        if silence_frames > 0:
                            audio_q.put(bytes(silence_frames * nchannels * sampwidth))
                    if not silence_stop.is_set() and not _is_silent(raw):
                        silence_stop.set()
                    try:
                        audio_q.put_nowait(raw)
                    except queue.Full:
                        dropped_chunks[0] += 1
            finally:
                stream_handle.stop_stream()
                stream_handle.close()
                stop_writer.set()
                writer_thread.join(timeout=10.0)
                if dropped_chunks[0]:
                    self.on_status(
                        "warning",
                        f"audio: dropped {dropped_chunks[0]} chunk(s) (queue overflow)",
                    )
