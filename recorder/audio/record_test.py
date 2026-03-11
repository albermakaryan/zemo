"""
Standalone test for internal (system) audio recording.

Run from project root:
  python -m recorder.audio.record_test

1. Recording starts.
2. You start a video (browser, VLC, etc.) — the audio from that video is captured.
3. After RECORD_SEC seconds we stop and save to recordings/audio/test_audio.wav.
"""

import sys
import time

# Ensure project root is on path
from pathlib import Path

_root = Path(__file__).resolve().parent.parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from recorder.audio import InternalAudioRecorder, is_loopback_available
from recorder.config import get_audio_dir

# Seconds to record after you start your video
RECORD_SEC = 30
# Seconds before we start recording (time to switch to browser and hit play)
GET_READY_SEC = 5


def main():
    print("Internal audio test — record audio from a video")
    print("-" * 50)

    if sys.platform != "win32":
        print("FAIL: Windows required (WASAPI loopback).")
        return 1

    if not is_loopback_available():
        print("FAIL: Loopback not available.")
        print("  Install: pip install PyAudioWPatch")
        print("  Make sure you're on Windows with audio output (speakers/headphones).")
        return 1

    print("OK: Loopback available.")
    print()
    print("Workflow:")
    print("  1. Recording will start in {} seconds.".format(GET_READY_SEC))
    print("  2. Open your video (e.g. YouTube in browser) and get ready to press Play.")
    print(
        "  3. When recording starts, press Play — we'll capture that audio for {} seconds.".format(
            RECORD_SEC
        )
    )
    print()
    for i in range(GET_READY_SEC, 0, -1):
        print("  Starting in {}...".format(i))
        time.sleep(1)
    print()
    print("  >>> Recording now. Start your video! <<<")
    print()

    save_dir = str(get_audio_dir())
    save_dir_path = Path(save_dir)
    save_dir_path.mkdir(parents=True, exist_ok=True)

    recorder = InternalAudioRecorder(
        on_status=lambda s, m: print("  [{}] {}".format(s, m)),
        on_done=lambda f: None,
    )
    recorder.start(save_dir=save_dir, email="test")
    if not recorder.recording:
        print("FAIL: Recorder did not start (check on_status message above).")
        return 1

    try:
        time.sleep(RECORD_SEC)
    except KeyboardInterrupt:
        print("\n  Stopped early.")
    finally:
        recorder.stop(stop_time=time.time())
        recorder.join()

    out_path = Path(recorder.filename)
    if out_path.exists():
        size_kb = out_path.stat().st_size / 1024
        print()
        print("Done. Saved:")
        print("  {}".format(out_path))
        print("  ({:.1f} KB)".format(size_kb))
        print("  Play the WAV to verify system audio was captured.")
        return 0
    else:
        print("FAIL: Output file was not created.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
