"""
Internal (system) audio on Linux/macOS: capture what is playing (default output monitor).

Uses PulseAudio/PipeWire monitor (Linux) or sounddevice/PortAudio (Linux/macOS).
When sounddevice does not expose monitor names (only "pulse"/"default"), we fall back
to pactl + parecord to record from the default sink's monitor by name.
Requires: pip install sounddevice  (or: pip install -e ".[linux]")
Linux fallback: pactl and parecord (pulseaudio-utils or pipewire-pulse).
"""

import subprocess
import sys
import threading
import time
import wave
from pathlib import Path
from typing import Callable, List, Optional, Tuple

from recorder import config
from recorder.common import email_filename_part

try:
    import sounddevice as sd
    import numpy as np
    _HAS_SOUNDDEVICE = True
except ImportError:
    sd = None
    np = None
    _HAS_SOUNDDEVICE = False


def _get_pulse_monitor_source_name() -> Optional[str]:
    """
    Return the default sink's monitor source name via pactl (PulseAudio/PipeWire).
    Used when sounddevice only exposes "pulse"/"default" and not the real monitor name.
    Returns e.g. "alsa_output.pci-....sink.monitor" or None if pactl unavailable.
    """
    if sys.platform != "linux":
        return None
    try:
        out = subprocess.run(
            ["pactl", "get-default-sink"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if out.returncode != 0 or not out.stdout:
            return None
        sink = out.stdout.strip()
        if not sink:
            return None
        # Monitor source name is <sink_name>.monitor
        return f"{sink}.monitor"
    except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
        return None


def is_loopback_available() -> bool:
    """True if we can record system audio (monitor via sounddevice or pactl+parecord)."""
    if sys.platform not in ("linux", "darwin"):
        return False
    try:
        if _HAS_SOUNDDEVICE and _get_monitor_device_index() is not None:
            return True
        # Sounddevice may not expose monitor names; try PulseAudio/PipeWire by name
        if sys.platform == "linux" and _get_pulse_monitor_source_name() is not None:
            import shutil
            if shutil.which("parecord"):
                return True
        return False
    except Exception:
        return False


def _get_monitor_device_index() -> Optional[int]:
    """
    Return the device index of the default output's monitor (loopback), or None.
    Only devices that are explicitly monitor/loopback are used — never microphones
    or the PulseAudio default source ("pulse"), which is usually a mic.
    Internal audio = what the computer is playing (video, apps), not room/mic.
    """
    if not _HAS_SOUNDDEVICE:
        return None
    try:
        default_out = sd.query_devices(kind="output")
        default_sink_name = (
            (default_out.get("name", "") if isinstance(default_out, dict) else "")
            .strip().lower()
        )
        first_monitor = None
        for i in range(256):
            try:
                dev = sd.query_devices(i)
            except Exception:
                continue  # skip bad index, don't stop the whole scan
            if dev is None or not isinstance(dev, dict):
                continue
            if dev.get("max_input_channels", 0) < 1:
                continue
            name = (dev.get("name") or "").strip().lower()

            # Only accept explicit monitor/loopback — never fall back to mic/pulse
            is_monitor = (
                name.endswith(".monitor")
                or "loopback" in name
                or "stereo mix" in name
                or (".monitor" in name or "monitor" in name)  # "Monitor of ..." style
            )
            if not is_monitor:
                continue

            # Prefer exact match: PulseAudio uses <sink_name>.monitor
            if default_sink_name and name == f"{default_sink_name}.monitor":
                return i
            if first_monitor is None:
                first_monitor = i

        return first_monitor
    except Exception:
        return None


class InternalAudioRecorder:
    """Record internal (system) audio on Linux/macOS via PulseAudio/PipeWire or sounddevice."""

    def __init__(self, on_status: Optional[Callable[[str, str], None]] = None, on_done: Optional[Callable[[str], None]] = None):
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
        if not _HAS_SOUNDDEVICE:
            self.on_status("error", "System audio requires: pip install sounddevice")
            return
        if sys.platform not in ("linux", "darwin"):
            self.on_status("error", "This implementation is for Linux/macOS only")
            return
        dev_idx = _get_monitor_device_index()
        pulse_monitor = _get_pulse_monitor_source_name() if dev_idx is None and sys.platform == "linux" else None
        if dev_idx is None and pulse_monitor is None:
            if sys.platform == "darwin":
                self.on_status(
                    "error",
                    "macOS has no built-in loopback. Install BlackHole or Loopback for internal audio.",
                )
            else:
                self.on_status(
                    "error",
                    "No internal audio (monitor/loopback) found — system playback only, not mic.",
                )
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
        if dev_idx is not None:
            self._thread = threading.Thread(target=self._run, args=(dev_idx,), daemon=True)
        else:
            self._thread = threading.Thread(target=self._run_parecord, args=(pulse_monitor,), daemon=True)
        self._thread.start()

    def stop(self, stop_time: Optional[float] = None) -> None:
        self._stop_time = stop_time
        self._stop.set()
        self.recording = False

    def join(self, timeout: float = 5.0) -> None:
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)

    def _run_parecord(self, monitor_source_name: str) -> None:
        """Record from PulseAudio/PipeWire monitor by name via parecord (when sounddevice has no monitor)."""
        chunks: List[Tuple[float, bytes]] = []
        t0: Optional[float] = None
        sample_rate = config.AUDIO_SAMPLE_RATE
        nchannels = 2
        sampwidth = 2
        chunk_bytes = 4096

        try:
            self.on_status("recording", f"→ {Path(self.filename).name} (system audio, parecord)")
            if self._start_barrier is not None:
                self._start_barrier.wait()
            ref = self._start_time_ref
            video_t0 = ref[0] if ref and len(ref) and ref[0] is not None else None

            proc = subprocess.Popen(
                [
                    "parecord",
                    "-d", monitor_source_name,
                    "--rate=%d" % sample_rate,
                    "--channels=%d" % nchannels,
                    "--format=s16ne",
                    "--raw",
                    "-",  # stdout
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )
            t0 = time.time()
            self._video_t0 = video_t0 if video_t0 is not None else t0
            while not self._stop.is_set() and proc.poll() is None:
                data = proc.stdout.read(chunk_bytes)  # type: ignore[union-attr]
                if not data:
                    break
                chunks.append((time.time(), data))
            try:
                proc.terminate()
                proc.wait(timeout=1.0)
            except Exception:
                proc.kill()
        except Exception as e:
            self.on_status("error", str(e))
            self.recording = False
            self.on_done(self.filename)
            return

        try:
            t_final = self._stop_time or time.time()
            t0_val = t0 or time.time()
            video_t0_val = getattr(self, "_video_t0", t0_val)
            start_offset = max(0.0, t0_val - video_t0_val)
            elapsed_audio = t_final - t0_val
            bytes_per_frame = nchannels * sampwidth
            expected_body_frames = int(elapsed_audio * sample_rate) if elapsed_audio > 0 else 0
            offset_frames = int(start_offset * sample_rate)
            total_frames_video = int((t_final - video_t0_val) * sample_rate)

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

    def _run(self, device_index: int) -> None:
        chunks: List[Tuple[float, bytes]] = []
        t0: Optional[float] = None
        sample_rate = config.AUDIO_SAMPLE_RATE
        nchannels = 2
        sampwidth = 2
        # Larger blocks reduce underruns/crackling; 2048 is a good default for loopback
        blocksize = getattr(config, "AUDIO_CHUNK_SIZE", 1024)
        if blocksize < 2048:
            blocksize = 2048

        try:
            dev = sd.query_devices(device_index)
            sr = int(dev.get("default_samplerate", sample_rate))
            ch = min(int(dev.get("max_input_channels", 2)), 2)
            sample_rate = sr
            nchannels = ch
            self.on_status("recording", f"→ {Path(self.filename).name} (system audio)")

            if self._start_barrier is not None:
                self._start_barrier.wait()
            ref = self._start_time_ref
            video_t0 = ref[0] if ref and len(ref) and ref[0] is not None else None

            def stream_callback(indata, frames, time_info, status):
                if status:
                    return
                if not self._stop.is_set() and indata is not None and indata.size:
                    # Copy: callback buffer may be reused by sounddevice after return
                    data_f32 = np.ascontiguousarray(indata.copy())
                    # Scale to int16: clip then round to reduce quantization noise (no dither for speed)
                    scaled = np.clip(data_f32 * 32767.0, -32768.0, 32767.0)
                    scaled = np.round(scaled).astype(np.int16)
                    chunks.append((time.time(), scaled.tobytes()))

            with sd.InputStream(
                device=device_index,
                channels=nchannels,
                samplerate=sample_rate,
                blocksize=blocksize,
                dtype="float32",
                callback=stream_callback,
            ):
                t0 = time.time()
                self._video_t0 = video_t0 if video_t0 is not None else t0
                while not self._stop.is_set():
                    time.sleep(0.05)

        except Exception as e:
            self.on_status("error", str(e))
            self.recording = False
            self.on_done(self.filename)
            return

        try:
            t_final = self._stop_time or time.time()
            t0_val = t0 or time.time()
            video_t0_val = getattr(self, "_video_t0", t0_val)
            start_offset = max(0.0, t0_val - video_t0_val)
            elapsed_audio = t_final - t0_val
            bytes_per_frame = nchannels * sampwidth
            expected_body_frames = int(elapsed_audio * sample_rate) if elapsed_audio > 0 else 0
            offset_frames = int(start_offset * sample_rate)
            total_frames_video = int((t_final - video_t0_val) * sample_rate)

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
