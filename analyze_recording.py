"""
Quick CLI to run emotion detection on a webcam recording and align it with a screen recording.

Usage examples (from repo root):

  python analyze_recording.py \
      --webcam recordings/webcam/user_webcam.mp4 \
      --screen recordings/screen/user_screen.mp4 \
      --out analysis/emotions.csv

If --out is omitted, a CSV will be written next to the webcam file.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from detector import analyze_webcam_and_screen


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze emotions and align webcam/screen videos.")
    parser.add_argument(
        "--webcam",
        required=True,
        help="Path to webcam video MP4 (e.g. recordings/webcam/xxx_webcam.mp4)",
    )
    parser.add_argument(
        "--screen",
        required=True,
        help="Path to screen video MP4 (e.g. recordings/screen/xxx_screen.mp4)",
    )
    parser.add_argument(
        "--out",
        help="Output CSV path (default: <webcam_basename>_emotions.csv next to webcam video)",
    )
    parser.add_argument(
        "--step",
        type=float,
        default=1.0,
        help="Sample interval in seconds (default: 1.0)",
    )

    args = parser.parse_args()

    webcam_path = Path(args.webcam)
    screen_path = Path(args.screen)

    if args.out:
        out_csv = Path(args.out)
    else:
        out_csv = webcam_path.with_suffix("").with_name(webcam_path.stem + "_emotions.csv")

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    out_video = out_csv.parent / (webcam_path.stem + "_annotated.mp4")

    print(f"[analyze_recording] Webcam : {webcam_path}")
    print(f"[analyze_recording] Screen : {screen_path}")
    print(f"[analyze_recording] CSV    : {out_csv}")
    print(f"[analyze_recording] Video  : {out_video}")
    print(f"[analyze_recording] Step   : {args.step} s")

    samples = analyze_webcam_and_screen(
        webcam_path=str(webcam_path.resolve()),
        screen_path=str(screen_path.resolve()),
        output_csv=str(out_csv),
        sample_every_s=args.step,
        output_annotated_video=str(out_video),
    )

    print(f"[analyze_recording] Done. Samples: {len(samples)}. CSV: {out_csv}")


if __name__ == "__main__":
    main()

