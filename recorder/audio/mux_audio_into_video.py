"""
Add audio to video: mux the recorded WAV into the screen (or webcam) MP4 using ffmpeg.

Run from project root:
  python -m recorder.audio.mux_audio_into_video [email]           # screen + webcam with audio
  python -m recorder.audio.mux_audio_into_video --screen-only [email]   # only screen with audio

If no email, uses the latest recording. Requires ffmpeg on PATH.

Output (default):
  recordings/screen_with_audio/<email>_screen_with_audio.mp4
  recordings/webcam/<email>_webcam_with_audio.mp4

Output (--screen-only):
  recordings/screen_with_audio/<email>_screen_with_audio.mp4
"""

import subprocess
import sys
from pathlib import Path

_root = Path(__file__).resolve().parent.parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from recorder.config import (
    get_webcam_dir,
    get_screen_dir,
    get_audio_dir,
    RECORDINGS_DIR,
)


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


def mux_one(
    video_path: Path, audio_path: Path, out_path: Path, ffmpeg_exe: str
) -> bool:
    if not video_path.exists():
        print("  Skip (no video): {}".format(video_path.name))
        return False
    if not audio_path.exists():
        print("  Skip (no audio): {}".format(audio_path.name))
        return False
    if not ffmpeg_exe:
        print(
            "  FAIL: ffmpeg not found. Install ffmpeg (or: pip install imageio-ffmpeg)"
        )
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
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        print("  OK: {}".format(out_path.name))
        return True
    except subprocess.CalledProcessError as e:
        err = (e.stderr or str(e)) if e.stderr is not None else str(e)
        print("  FAIL: {} - {}".format(out_path.name, err[:200]))
        return False


def _latest_email() -> str:
    """Base name from newest recordings/webcam/*_webcam.mp4."""
    webcam_dir = RECORDINGS_DIR / "webcam"
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
    email = (args[0] if args else "").strip()
    if not email:
        email = _latest_email()
    if not email:
        print(
            "Usage: python -m recorder.audio.mux_audio_into_video [--screen-only] [email]"
        )
        print("  Adds audio to screen video (and optionally webcam). Needs ffmpeg.")
        return 1

    webcam_dir = get_webcam_dir()
    screen_dir = get_screen_dir()
    audio_dir = get_audio_dir()
    screen_with_audio_dir = RECORDINGS_DIR / "screen_with_audio"

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
