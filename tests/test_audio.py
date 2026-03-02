"""System (loopback) audio recording test. Windows only."""

import argparse
import sys
import time
from pathlib import Path

if __name__ == "__main__":
    _root = Path(__file__).resolve().parent.parent
    if str(_root) not in sys.path:
        sys.path.insert(0, str(_root))


def run_audio(seconds: float = 10.0) -> int:
    """Run system audio recording for `seconds`. Returns 0 on success, 1 on failure."""
    from recorder import config
    from recorder.audio import InternalAudioRecorder, is_loopback_available

    if sys.platform != "win32":
        print("FAIL: Audio test requires Windows (WASAPI loopback).")
        return 1
    if not is_loopback_available():
        print("FAIL: Loopback not available. Install: pip install PyAudioWPatch")
        return 1

    config.ensure_test_recordings_dirs()
    save_dir = str(config.get_test_audio_dir())

    def on_status(s: str, msg: str):
        print("  [{}] {}".format(s, msg))

    print("System audio recording for {} seconds... (Ctrl+C to stop early)".format(seconds))
    print("  Play a video in browser to capture its audio.")
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
        return 0
    print("FAIL: No output file.")
    return 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test system audio recording only (Windows).")
    parser.add_argument("--seconds", type=float, default=10.0, help="Recording length")
    args = parser.parse_args()
    sys.exit(run_audio(seconds=args.seconds))
