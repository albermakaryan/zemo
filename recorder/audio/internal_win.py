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

                if self._start_barrier is not None:
                    self._start_barrier.wait()

                if _HAS_AV:
                    self._record_av(p, device, sample_rate, nchannels)
                else:
                    self._record_wav(p, device, sample_rate, nchannels, sampwidth)

        except Exception as e:
            self.on_status("error", str(e))
            self.recording = False
            return

        self.recording = False
        self.on_done(self.filename)

    # ─── PyAV path: Matroska Audio with hardware PTS ─────────────────────────

    def _record_av(
        self,
        p: Any,
        device: Dict[str, Any],
        sample_rate: int,
        nchannels: int,
    ) -> None:
        """
        Write .mka with per-packet PTS from WASAPI's input_buffer_adc_time.

        The hardware ADC clock ticks continuously even when the audio device is
        idle. When the user pauses the watched video and WASAPI stops delivering
        callbacks, the next callback that fires after resume will carry an
        input_buffer_adc_time that is several seconds ahead of the previous one.
        That difference becomes a PTS jump in the Matroska container. ffmpeg
        reads both streams by PTS when muxing, so the gap is preserved exactly
        with no silence padding and no threshold tuning.

        If the driver reports input_buffer_adc_time == 0 (some WASAPI
        implementations do not expose it) the code falls back to sequential
        frame counting, which keeps normal recording in sync but cannot
        reconstruct pause gaps.
        """
        av = _av
        layout = "stereo" if nchannels == 2 else "mono"
        tb = Fraction(1, sample_rate)
        chunk_size = config.AUDIO_CHUNK_SIZE

        gap_threshold = 8 * chunk_size  # frames; same rule as WAV path

        audio_q: queue.Queue = queue.Queue(maxsize=2048)
        stop_writer = threading.Event()
        pa_start_adc: List[Optional[float]] = [None]
        next_pts_fb: List[int] = [0]   # sequential PTS used when adc_time == 0
        last_cb_time: List[Optional[float]] = [None]  # for gap detection in fallback
        dropped_chunks: List[int] = [0]

        def _writer() -> None:
            container = av.open(self.filename, "w", format="matroska")
            # FLAC is lossless, natively supported in Matroska, and accepts
            # interleaved s16 input directly — no numpy reshape needed.
            # pcm_s16le is avoided: it requires explicit extradata that
            # add_stream() does not initialise, causing EINVAL on first mux.
            stream = container.add_stream("flac", rate=sample_rate)
            stream.codec_context.layout = layout  # 'stereo' or 'mono'
            stream.codec_context.format = "s16"   # interleaved; matches WASAPI output
            stream.time_base = tb                 # must match frame.time_base (1/sample_rate)
            try:
                while not (stop_writer.is_set() and audio_q.empty()):
                    try:
                        pts, raw = audio_q.get(timeout=0.05)
                        n = len(raw) // (nchannels * 2)  # samples per channel
                        # Write WASAPI's raw interleaved bytes straight into
                        # the frame — no deinterleaving or numpy required.
                        frame = av.AudioFrame(
                            format="s16", layout=layout, samples=n
                        )
                        frame.sample_rate = sample_rate
                        frame.pts = pts  # units: 1/sample_rate (sample count)
                        frame.time_base = tb
                        frame.planes[0].update(raw)
                        for packet in stream.encode(frame):
                            container.mux(packet)
                        self._frames_written += n
                    except queue.Empty:
                        continue
                # Flush encoder
                for packet in stream.encode(None):
                    container.mux(packet)
            finally:
                container.close()

        def callback(
            in_data: bytes, frame_count: int, time_info: dict, status: int
        ) -> tuple:
            adc_time: float = time_info.get("input_buffer_adc_time", 0.0)

            if pa_start_adc[0] is None:
                # Calibrate on the first callback so PTS starts at 0.
                pa_start_adc[0] = adc_time if adc_time > 0 else 0.0
                mode = "hardware PTS" if adc_time > 0 else "perf_counter fallback"
                self.on_status("recording", f"(system audio · {mode})")

            if adc_time > 0 and pa_start_adc[0] > 0:
                # Hardware clock path: PTS is exact. A pause in the watched
                # video means WASAPI stops delivering callbacks; the next
                # callback's adc_time reflects the full elapsed wall time, so
                # the PTS jump encodes the gap — no silence bytes needed.
                pts = int((adc_time - pa_start_adc[0]) * sample_rate)
            else:
                # Driver doesn't expose adc_time. Use perf_counter to detect
                # gaps (same logic as the WAV fallback) and advance PTS by the
                # measured interval. The container encodes the gap as a PTS
                # jump; the player renders it as silence.
                now = time.perf_counter()
                prev = last_cb_time[0]
                last_cb_time[0] = now
                if prev is not None:
                    measured = int((now - prev) * sample_rate)
                    gap = measured - frame_count
                    if gap > gap_threshold:
                        # Advance PTS past the silence window.
                        next_pts_fb[0] += gap
                pts = next_pts_fb[0]

            next_pts_fb[0] = pts + frame_count

            try:
                audio_q.put_nowait((pts, in_data))
            except queue.Full:
                dropped_chunks[0] += 1

            return (in_data, pyaudio.paContinue)

        writer_thread = threading.Thread(target=_writer, daemon=True)
        writer_thread.start()

        stream_handle = p.open(
            format=pyaudio.paInt16,
            channels=nchannels,
            rate=sample_rate,
            frames_per_buffer=chunk_size,
            input=True,
            input_device_index=device["index"],
            stream_callback=callback,
        )
        stream_handle.start_stream()
        try:
            while not self._stop.is_set():
                time.sleep(0.05)
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

    # ─── WAV fallback: silence padding via inter-callback gap detection ───────

    def _record_wav(
        self,
        p: Any,
        device: Dict[str, Any],
        sample_rate: int,
        nchannels: int,
        sampwidth: int,
    ) -> None:
        """
        Write .wav. Gaps are approximated by inserting silence when the
        inter-callback interval (measured with perf_counter) exceeds 8×
        the nominal callback period. This handles video pauses reasonably
        well but cannot be made exact — use the PyAV path when possible.
        """
        chunk_size = config.AUDIO_CHUNK_SIZE
        # 8× nominal callback period; immune to OS jitter (< 2 ms with a
        # non-blocking callback) while still catching sub-second pauses.
        gap_threshold = 8 * chunk_size  # frames

        audio_q: queue.Queue = queue.Queue(maxsize=2048)
        stop_writer = threading.Event()
        last_cb_time: List[Optional[float]] = [None]
        dropped_chunks: List[int] = [0]

        def _writer(wf: wave.Wave_write) -> None:
            while not (stop_writer.is_set() and audio_q.empty()):
                try:
                    chunk = audio_q.get(timeout=0.05)
                    wf.writeframes(chunk)
                    self._frames_written += len(chunk) // (nchannels * sampwidth)
                except queue.Empty:
                    continue

        def callback(
            in_data: bytes, frame_count: int, time_info: dict, status: int
        ) -> tuple:
            now = time.perf_counter()
            prev = last_cb_time[0]
            last_cb_time[0] = now

            if prev is not None:
                gap = int((now - prev) * sample_rate) - frame_count
                if gap > gap_threshold:
                    try:
                        audio_q.put_nowait(bytes(gap * nchannels * sampwidth))
                    except queue.Full:
                        dropped_chunks[0] += 1

            try:
                audio_q.put_nowait(in_data)
            except queue.Full:
                dropped_chunks[0] += 1

            return (in_data, pyaudio.paContinue)

        with wave.open(self.filename, "wb") as wf:
            wf.setnchannels(nchannels)
            wf.setsampwidth(sampwidth)
            wf.setframerate(sample_rate)

            writer_thread = threading.Thread(
                target=_writer, args=(wf,), daemon=True
            )
            writer_thread.start()

            stream_handle = p.open(
                format=pyaudio.paInt16,
                channels=nchannels,
                rate=sample_rate,
                frames_per_buffer=chunk_size,
                input=True,
                input_device_index=device["index"],
                stream_callback=callback,
            )
            stream_handle.start_stream()
            try:
                while not self._stop.is_set():
                    time.sleep(0.05)
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
