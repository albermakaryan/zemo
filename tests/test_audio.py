"""System (loopback) audio recording test. Windows: WASAPI. Linux: Pulse/PipeWire monitor."""

import argparse
import sys
import time
import wave
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))


def _verify_audio_wav(path: Path) -> bool:
    """Load WAV, print duration/sample rate/channels and signal level; return True if valid."""
    try:
        import numpy as np
    except ImportError:
        print("  Verify: numpy required to inspect audio; skip.")
        return path.exists()
    if not path.exists():
        return False
    try:
        with wave.open(str(path), "rb") as w:
            sr = w.getframerate()
            nch = w.getnchannels()
            nframes = w.getnframes()
            raw = w.readframes(nframes)
        duration_sec = nframes / sr if sr else 0
        samples = np.frombuffer(raw, dtype=np.int16)
        samples = samples.reshape(-1, nch).T.astype(np.float32) / 32768.0
        rms = float(np.sqrt(np.mean(samples**2))) if samples.size else 0.0
        peak = float(np.max(np.abs(samples))) if samples.size else 0.0
        print(
            "  Verify: {:.2f} s, {} Hz, {} ch, RMS={:.4f}, peak={:.4f}".format(
                duration_sec, sr, nch, rms, peak
            )
        )
        return True
    except Exception as e:
        print("  Verify: failed to load WAV: {}".format(e))
        return False


def list_audio_devices() -> int:
    """Print default output and all input devices (for debugging 'no monitor' on Linux)."""
    try:
        import sounddevice as sd
    except ImportError:
        print('Install sounddevice: pip install -e ".[linux]"')
        return 1
    print("Default output:", sd.query_devices(kind="output"))
    print("\nInput devices (candidates for loopback/monitor):")
    for i in range(256):
        try:
            dev = sd.query_devices(i)
        except Exception:
            break
        if dev is None or not isinstance(dev, dict):
            break
        if dev.get("max_input_channels", 0) < 1:
            continue
        name = (dev.get("name") or "").strip()
        sr = dev.get("default_samplerate", "?")
        ch = dev.get("max_input_channels", 0)
        print("  [{}] {} ({} ch, {} Hz)".format(i, name, ch, sr))
    return 0


def run_audio(seconds: float = 10.0) -> int:
    """Run system audio recording for `seconds`. Returns 0 on success, 1 on failure."""
    from recorder import config
    from recorder.audio import InternalAudioRecorder, is_loopback_available

    if sys.platform == "win32":
        if not is_loopback_available():
            print('FAIL: Loopback not available. Install: pip install -e ".[windows]"')
            return 1
        print("System audio test (Windows WASAPI) — recording {} s...".format(seconds))
    elif sys.platform in ("linux", "darwin"):
        if not is_loopback_available():
            print(
                "FAIL: No internal audio (monitor/loopback). Internal = computer playback only (video, apps), not microphone."
            )
            if sys.platform == "darwin":
                print(
                    "  macOS has no built-in loopback. Install BlackHole or Loopback for internal audio."
                )
            else:
                print(
                    '  Install: pip install -e ".[linux]"  and ensure PulseAudio/PipeWire exposes a monitor source (e.g. <sink>.monitor).'
                )
            print(
                "  We only use devices that are explicitly monitor/loopback — never 'pulse' or default (usually mic)."
            )
            print("  Available input devices:")
            list_audio_devices()
            return 1
        print(
            "System audio test ({} monitor) — recording {} s...".format(
                "Linux" if sys.platform == "linux" else "macOS", seconds
            )
        )
    else:
        print("FAIL: Audio test only supported on Windows, Linux, and macOS.")
        return 1

    config.ensure_test_recordings_dirs()
    save_dir = str(config.get_test_audio_dir())

    def on_status(s: str, msg: str):
        print("  [{}] {}".format(s, msg))

    print("  Play a video in browser to capture its audio. (Ctrl+C to stop early)")
    r = InternalAudioRecorder(on_status=on_status, on_done=lambda f: None)
    r.start(save_dir=save_dir, email="test")
    if not r.recording:
        print("FAIL: Audio recorder did not start.")
        return 1
    try:
        time.sleep(seconds)
    except KeyboardInterrupt:
        print("\n  Stopped early.")
    finally:
        r.stop(stop_time=time.time())
        r.join()
    p = Path(r.filename)
    if p.exists():
        print("  Saved: {} ({:.1f} KB)".format(p, p.stat().st_size / 1024))
        if not _verify_audio_wav(p):
            print("FAIL: Audio file verification failed.")
            return 1
        print("  OK: Audio tracker verified — recording works.")
        return 0
    print("FAIL: No output file.")
    return 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Test system audio recording; runs recorder then verifies WAV."
    )
    parser.add_argument("--seconds", type=float, default=10.0, help="Recording length")
    parser.add_argument(
        "--list-devices",
        action="store_true",
        help="List input devices and exit (debug no monitor)",
    )
    args = parser.parse_args()
    if args.list_devices:
        sys.exit(list_audio_devices())
    sys.exit(run_audio(seconds=args.seconds))
