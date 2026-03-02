"""Webcam recording test: records webcam only for a few seconds."""

import argparse
import sys
import time
from pathlib import Path

if __name__ == "__main__":
    _root = Path(__file__).resolve().parent.parent
    if str(_root) not in sys.path:
        sys.path.insert(0, str(_root))


def run_webcam(seconds: float = 5.0) -> int:
    """Run webcam recording for `seconds`. Returns 0 on success, 1 on failure."""
    from recorder import config
    from recorder.recorders import WebcamRecorder

    config.ensure_test_recordings_dirs()
    save_dir = str(config.get_test_webcam_dir())

    def on_status(s: str, msg: str):
        print("  [{}] {}".format(s, msg))

    def on_done(path: str):
        print("  Done: {}".format(path))

    def on_frame(_frame, elapsed: float):
        if int(elapsed) != getattr(on_frame, "_last", -1):
            on_frame._last = int(elapsed)
            print("  frame @ {}s".format(int(elapsed)))

    on_frame._last = -1

    print("Webcam recording for {} seconds... (Ctrl+C to stop early)".format(seconds))
    r = WebcamRecorder(on_frame=on_frame, on_status=on_status, on_done=on_done)
    r.start(save_dir=save_dir, email="test")
    if not r.recording:
        print("FAIL: Webcam recorder did not start.")
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
    parser = argparse.ArgumentParser(description="Test webcam recording only.")
    parser.add_argument("--seconds", type=float, default=5.0, help="Recording length")
    args = parser.parse_args()
    sys.exit(run_webcam(seconds=args.seconds))
