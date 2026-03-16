"""
Add audio to video: mux the recorded WAV into the screen (or webcam) MP4 using ffmpeg.

Run from project root:
  python -m recorder.audio.mux_audio_into_video [email]           # screen + webcam with audio
  python -m recorder.audio.mux_audio_into_video --screen-only [email]   # only screen with audio
  python -m recorder.audio.mux_audio_into_video --screen-only --recordings-dir dist/recordings [email]

If no email, uses the latest recording. Requires ffmpeg on PATH.

Output (default):
  recordings/screen_with_audio/<email>_screen_with_audio.mp4
  recordings/webcam/<email>_webcam_with_audio.mp4

Output (--screen-only):
  recordings/screen_with_audio/<email>_screen_with_audio.mp4
"""

import subprocess
import sys
import time
from pathlib import Path

_root = Path(__file__).resolve().parent.parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from recorder.config import RECORDINGS_DIR


def _get_ffmpeg_exe():
    """Use system ffmpeg if on PATH, else imageio-ffmpeg bundled binary."""
    import shutil

    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def _is_video_valid(video_path: Path, ffmpeg_exe: str) -> bool:
    """
    Quick sanity check that the MP4 has a valid container (moov atom etc.)
    before trying to mux. Uses ffmpeg itself to probe.
    """
    cmd = [
        ffmpeg_exe,
        "-v",
        "error",
        "-i",
        str(video_path),
        "-f",
        "null",
        "-",
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        return True
    except subprocess.CalledProcessError as e:
        err = (e.stderr or str(e)) if e.stderr is not None else str(e)
        print(f"  Invalid video file {video_path.name}:")
        print(err)
        return False


def mux_one(
    video_path: Path, audio_path: Path, out_path: Path, ffmpeg_exe: str
) -> bool:
    if not video_path.exists():
        print("  Skip (no video file): {}".format(video_path.name))
        return False
    if not audio_path.exists():
        print("  Skip (no audio): {}".format(audio_path.name))
        return False
    if not ffmpeg_exe:
        print(
            "  FAIL: ffmpeg not found. Install ffmpeg (or: pip install imageio-ffmpeg)"
        )
        return False
    if not _is_video_valid(video_path, ffmpeg_exe):
        # Don't attempt muxing with a corrupted/incomplete MP4.
        return False
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        ffmpeg_exe,
        "-y",
        "-i",
        str(video_path),
        "-i",
        str(audio_path),
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-af",
        "aresample=async=1:min_hard_comp=0.100000:first_pts=0",
        "-vsync",
        "cfr",
        str(out_path),
    ]
    try:
        # Show full ffmpeg output so failures are easy to debug.
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        if result.stderr:
            # ffmpeg prints a lot to stderr even on success; keep it visible for troubleshooting.
            print(result.stderr)
        print("  OK: {}".format(out_path.name))
        return True
    except subprocess.CalledProcessError as e:
        err = (e.stderr or str(e)) if e.stderr is not None else str(e)
        print("  FAIL: {} -".format(out_path.name))
        print(err)
        return False


def _latest_email(recordings_dir: Path) -> str:
    """Base name from newest recordings/webcam/*_webcam.mp4."""
    webcam_dir = recordings_dir / "webcam"
    if not webcam_dir.exists():
        return ""
    candidates = list(webcam_dir.glob("*_webcam.mp4"))
    if not candidates:
        return ""
    latest = max(candidates, key=lambda p: p.stat().st_mtime)
    return latest.name.replace("_webcam.mp4", "")


def main():
    args = [a for a in sys.argv[1:] if a.strip()]
    screen_only = "--screen-only" in args
    if screen_only:
        args = [a for a in args if a != "--screen-only"]

    recordings_dir = RECORDINGS_DIR
    if "--recordings-dir" in args:
        idx = args.index("--recordings-dir")
        args.pop(idx)
        if idx < len(args):
            recordings_dir = Path(args.pop(idx)).resolve()
        else:
            print("Usage: --recordings-dir requires a path (e.g. dist/recordings)")
            return 1

    email = (args[0] if args else "").strip()
    if not email:
        email = _latest_email(recordings_dir)
    if not email:
        print(
            "Usage: python -m recorder.audio.mux_audio_into_video [--screen-only] [--recordings-dir DIR] [email]"
        )
        print("  Adds audio to screen video (and optionally webcam). Needs ffmpeg.")
        return 1

    webcam_dir = recordings_dir / "webcam"
    screen_dir = recordings_dir / "screen"
    audio_dir = recordings_dir / "audio"
    screen_with_audio_dir = recordings_dir / "screen_with_audio"

    video_screen = screen_dir / "{}_screen.mp4".format(email)
    audio_wav = audio_dir / "{}_audio.wav".format(email)
    out_screen = screen_with_audio_dir / "{}_screen_with_audio.mp4".format(email)

    ffmpeg_exe = _get_ffmpeg_exe()
    if not ffmpeg_exe:
        print(
            "ffmpeg not found. Install it (https://ffmpeg.org) or run: pip install imageio-ffmpeg"
        )
        return 1

    print("Adding audio to screen video: {}".format(email))
    print("  Audio: {}".format(audio_wav))
    if not audio_wav.exists():
        print("  Audio file not found. Exiting.")
        return 1

    # Give the screen recorder extra time to finish writing/closing the MP4.
    # A longer delay helps avoid 'moov atom not found' if mux is triggered immediately.
    time.sleep(30)

    ok = mux_one(video_screen, audio_wav, out_screen, ffmpeg_exe)
    if not screen_only:
        video_webcam = webcam_dir / "{}_webcam.mp4".format(email)
        out_webcam = webcam_dir / "{}_webcam_with_audio.mp4".format(email)
        ok = mux_one(video_webcam, audio_wav, out_webcam, ffmpeg_exe) and ok

    if ok:
        print("Done. Screen+audio: {}".format(out_screen))
    else:
        print("Some steps failed (missing file or ffmpeg).")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
