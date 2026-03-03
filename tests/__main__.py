"""Entry point for python -m tests [deps|screen|webcam|audio|ui]."""

import argparse
import sys

from tests.test_deps import run_deps
from tests.test_screen import run_screen
from tests.test_webcam import run_webcam
from tests.test_audio import run_audio
from tests.test_ui import run_ui
from tests.test_emotion_detection import run_emotion_detection


def main():
    parser = argparse.ArgumentParser(
        description="Run recorder component tests.",
        epilog="Examples: python -m tests screen --seconds 10  |  python -m tests ui",
    )
    sub = parser.add_subparsers(dest="command", help="Component to test")

    sub.add_parser("deps", help="Check dependencies")
    p_screen = sub.add_parser("screen", help="Screen recording only")
    p_screen.add_argument("--seconds", type=float, default=5.0)
    p_webcam = sub.add_parser("webcam", help="Webcam recording only")
    p_webcam.add_argument("--seconds", type=float, default=5.0)
    p_audio = sub.add_parser("audio", help="System audio only (Windows WASAPI / Linux Pulse)")
    p_audio.add_argument("--seconds", type=float, default=10.0)
    sub.add_parser("ui", help="Launch full app window")
    sub.add_parser("emotion_detection", help="Emotion detection pipeline (detector package)")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return 0

    if args.command == "deps":
        return run_deps()
    if args.command == "screen":
        return run_screen(seconds=args.seconds)
    if args.command == "webcam":
        return run_webcam(seconds=args.seconds)
    if args.command == "audio":
        return run_audio(seconds=args.seconds)
    if args.command == "ui":
        return run_ui()
    if args.command == "emotion_detection":
        return run_emotion_detection()
    return 0


if __name__ == "__main__":
    sys.exit(main())
