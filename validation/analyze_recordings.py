"""
Analyze recorder output: read webcam/screen MP4s and run quality checks.

Usage:
  python -m validation.analyze_recordings [recordings_dir]
  python -m validation.analyze_recordings --recordings-dir PATH [--json]
  python -m validation.analyze_recordings --json [recordings_dir]

If recordings_dir is omitted, uses recorder.config RECORDINGS_DIR (project/recordings).

With subdirs: looks for recordings_dir/webcam/*.mp4 and recordings_dir/screen/*.mp4.
Without subdirs (flat): analyzes all *.mp4 directly in recordings_dir.
"""


import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Any

import cv2
import numpy as np


def get_actual_fps(cap: cv2.VideoCapture) -> Tuple[float, int, float]:
    """
    Measure actual FPS by reading frames and using stream duration.
    Returns (actual_fps, frame_count, duration_sec).
    Uses CAP_PROP_POS_MSEC at end for duration when reliable; else frame_count / metadata_fps.
    """
    meta_fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
    meta_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    frame_count = 0
    duration_sec = 0.0
    # Count frames by reading (reliable for AVI and when CAP_PROP_FRAME_COUNT is wrong)
    while True:
        ret = cap.read()[0]
        if not ret:
            break
        frame_count += 1
    if frame_count == 0:
        return 0.0, 0, 0.0
    # Duration: prefer stream position (ms) at end of read; else metadata-based
    pos_ms = cap.get(cv2.CAP_PROP_POS_MSEC)
    if pos_ms and pos_ms > 0:
        duration_sec = pos_ms / 1000.0
    elif meta_fps > 0:
        duration_sec = frame_count / meta_fps
    else:
        duration_sec = 0.0
    if duration_sec <= 0:
        return 0.0, frame_count, 0.0
    actual_fps = frame_count / duration_sec
    return round(actual_fps, 2), frame_count, round(duration_sec, 3)


# Allow running from project root; add parent to path if needed
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from recorder.config import (
    RECORDINGS_DIR,
    WEBCAM_SUBDIR,
    SCREEN_SUBDIR,
    FPS as EXPECTED_FPS,
)


def get_video_props(cap: cv2.VideoCapture) -> Dict[str, Any]:
    """Read standard OpenCV video properties."""
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    return {
        "width": w,
        "height": h,
        "fps": fps,
        "frame_count": frame_count,
        "duration_sec": (frame_count / fps) if fps > 0 else 0.0,
    }


def sample_frames(cap: cv2.VideoCapture, num_samples: int = 5) -> List[np.ndarray]:
    """Read a few frames spread across the video (first, spread in middle, last)."""
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    if total == 0:
        return []
    indices = []
    if total <= num_samples:
        indices = list(range(total))
    else:
        indices = [0]
        step = (total - 1) / (num_samples - 1)
        for i in range(1, num_samples - 1):
            indices.append(int(i * step))
        indices.append(total - 1)
    frames = []
    for i in indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, i)
        ret, frame = cap.read()
        if ret and frame is not None:
            frames.append(frame)
    return frames


def analyze_frame(frame: np.ndarray) -> Dict[str, Any]:
    """Basic per-frame stats: mean brightness, std (variance), all-black check."""
    if frame is None or frame.size == 0:
        return {"mean": 0, "std": 0, "is_black": True, "ok": False}
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame
    mean = float(np.mean(gray))
    std = float(np.std(gray))
    # Consider "all black" if mean very low and no variance
    is_black = mean < 5 and std < 1.0
    return {
        "mean": round(mean, 2),
        "std": round(std, 2),
        "is_black": is_black,
        "ok": not is_black,
    }


def run_checks(filepath: Path, expected_fps: float = None) -> Dict[str, Any]:
    """
    Open a single video file and run quality checks.
    Returns a result dict with props, sample frame stats, and pass/fail.
    """
    expected_fps = expected_fps or EXPECTED_FPS
    result = {
        "file": str(filepath),
        "name": filepath.name,
        "ok": False,
        "error": None,
        "props": {},
        "checks": {},
        "sample_frames": [],
    }
    cap = cv2.VideoCapture(str(filepath))
    if not cap.isOpened():
        result["error"] = "Could not open file"
        return result
    try:
        result["props"] = get_video_props(cap)
        p = result["props"]
        # Measured actual FPS (by reading frames and duration)
        actual_fps, measured_count, measured_duration = get_actual_fps(cap)
        p["actual_fps"] = actual_fps
        p["measured_frame_count"] = measured_count
        p["measured_duration_sec"] = measured_duration
        # Seek back to start for sampling
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        # Structural checks
        result["checks"]["has_frames"] = p["frame_count"] > 0 or measured_count > 0
        result["checks"]["has_resolution"] = p["width"] >= 2 and p["height"] >= 2
        result["checks"]["even_dimensions"] = (p["width"] % 2 == 0) and (
            p["height"] % 2 == 0
        )
        result["checks"]["fps_reasonable"] = 0.1 < p["fps"] < 120
        result["checks"]["fps_near_expected"] = (
            abs(p["fps"] - expected_fps) < 2.0 if p["fps"] else False
        )
        result["checks"]["duration_positive"] = (
            p["duration_sec"] > 0 or measured_duration > 0
        )
        if actual_fps > 0:
            result["checks"]["actual_fps_near_expected"] = (
                abs(actual_fps - expected_fps) < 2.0
            )

        # Sample frames for content quality
        samples = sample_frames(cap, num_samples=5)
        all_black_count = 0
        for i, frame in enumerate(samples):
            stats = analyze_frame(frame)
            result["sample_frames"].append(stats)
            if stats.get("is_black"):
                all_black_count += 1
        result["checks"]["not_all_black"] = (
            all_black_count < len(samples) if samples else False
        )
        result["checks"]["has_content"] = len(samples) > 0 and any(
            s.get("ok") for s in result["sample_frames"]
        )

        # Overall ok: no error, basic checks pass
        result["ok"] = (
            result["checks"]["has_frames"]
            and result["checks"]["has_resolution"]
            and result["checks"]["duration_positive"]
            and result["checks"]["not_all_black"]
        )
    finally:
        cap.release()
    return result


def find_recordings(recordings_dir: Path) -> Tuple[List[Path], List[Path], bool]:
    """
    Return (webcam_mp4s, screen_mp4s, flat_mode).
    If webcam/ and screen/ subdirs exist and have mp4s, use them.
    Otherwise flat_mode=True: collect all *.mp4 directly in recordings_dir.
    """
    webcam_dir = recordings_dir / WEBCAM_SUBDIR
    screen_dir = recordings_dir / SCREEN_SUBDIR
    webcam = list(webcam_dir.glob("*.mp4")) if webcam_dir.exists() else []
    screen = list(screen_dir.glob("*.mp4")) if screen_dir.exists() else []
    if webcam or screen:
        webcam.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        screen.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return webcam, screen, False
    # No subdirs or empty: treat as flat directory of videos
    flat = list(recordings_dir.glob("*.mp4"))
    flat.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return flat, [], True


def analyze_all(recordings_dir: Path, expected_fps: float = None) -> Dict[str, Any]:
    """Run run_checks on all found videos. Return full report (webcam/screen or flat 'videos')."""
    webcam_files, screen_files, flat_mode = find_recordings(recordings_dir)
    expected_fps = expected_fps or EXPECTED_FPS

    if flat_mode:
        videos = webcam_files  # in flat mode, first element is the list of all mp4s
        report = {
            "recordings_dir": str(recordings_dir),
            "flat": True,
            "expected_fps": expected_fps,
            "videos": [run_checks(p, expected_fps) for p in videos],
        }
        report["summary"] = {
            "videos_total": len(videos),
            "videos_ok": sum(1 for r in report["videos"] if r["ok"]),
        }
    else:
        report = {
            "recordings_dir": str(recordings_dir),
            "flat": False,
            "expected_fps": expected_fps,
            "webcam": [run_checks(p, expected_fps) for p in webcam_files],
            "screen": [run_checks(p, expected_fps) for p in screen_files],
        }
        report["summary"] = {
            "webcam_total": len(webcam_files),
            "webcam_ok": sum(1 for r in report["webcam"] if r["ok"]),
            "screen_total": len(screen_files),
            "screen_ok": sum(1 for r in report["screen"] if r["ok"]),
        }
    return report


def print_report(report: Dict[str, Any]) -> None:
    """Human-readable summary to stdout."""
    r = report
    print("=" * 60)
    print("RECORDING QUALITY REPORT")
    print("=" * 60)
    print(f"Recordings dir: {r['recordings_dir']}")
    if r.get("flat"):
        print("Mode: flat (videos in directory, no webcam/screen subdirs)")
    print(f"Expected FPS:  {r['expected_fps']}")
    print()

    if r.get("flat"):
        items = r["videos"]
        print(f"--- Videos ({len(items)} file(s)) ---")
        if not items:
            print("  (none)")
        else:
            for v in items:
                status = "OK" if v["ok"] else "FAIL"
                err = f"  [{v['error']}]" if v.get("error") else ""
                print(f"  {status}  {v['name']}{err}")
                if v.get("props"):
                    p = v["props"]
                    actual = p.get("actual_fps")
                    fps_str = f" @ {p['fps']:.1f} fps (metadata)"
                    if actual is not None and actual > 0:
                        fps_str += f", {actual:.2f} fps (actual)"
                    print(
                        f"       {p['width']}x{p['height']}{fps_str}, {p.get('measured_frame_count', p['frame_count'])} frames, {p.get('measured_duration_sec', p['duration_sec']):.2f}s"
                    )
                if not v["ok"] and v.get("checks"):
                    fails = [k for k, val in v["checks"].items() if val is False]
                    if fails:
                        print(f"       Failed: {', '.join(fails)}")
        print()
        s = r["summary"]
        print("Summary:")
        print(f"  Videos: {s['videos_ok']}/{s['videos_total']} ok")
    else:
        for kind, key in [("Webcam", "webcam"), ("Screen", "screen")]:
            items = r[key]
            print(f"--- {kind} ({len(items)} file(s)) ---")
            if not items:
                print("  (none)")
                print()
                continue
            for v in items:
                status = "OK" if v["ok"] else "FAIL"
                err = f"  [{v['error']}]" if v.get("error") else ""
                print(f"  {status}  {v['name']}{err}")
                if v.get("props"):
                    p = v["props"]
                    actual = p.get("actual_fps")
                    fps_str = f" @ {p['fps']:.1f} fps (metadata)"
                    if actual is not None and actual > 0:
                        fps_str += f", {actual:.2f} fps (actual)"
                    print(
                        f"       {p['width']}x{p['height']}{fps_str}, {p.get('measured_frame_count', p['frame_count'])} frames, {p.get('measured_duration_sec', p['duration_sec']):.2f}s"
                    )
                if not v["ok"] and v.get("checks"):
                    fails = [k for k, val in v["checks"].items() if val is False]
                    if fails:
                        print(f"       Failed: {', '.join(fails)}")
            print()
        s = r["summary"]
        print("Summary:")
        print(f"  Webcam: {s['webcam_ok']}/{s['webcam_total']} ok")
        print(f"  Screen: {s['screen_ok']}/{s['screen_total']} ok")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Validate recorder output quality")
    parser.add_argument(
        "recordings_dir",
        nargs="?",
        default=None,
        help="Path to recordings folder (default: project recordings)",
    )
    parser.add_argument(
        "--recordings-dir",
        dest="recordings_dir_opt",
        default=None,
        help="Path to recordings folder (same as positional)",
    )
    parser.add_argument(
        "--json", action="store_true", help="Output full report as JSON"
    )
    args = parser.parse_args()
    recordings_dir = Path(
        args.recordings_dir_opt or args.recordings_dir or RECORDINGS_DIR
    )
    if not recordings_dir.exists():
        print(f"Error: directory does not exist: {recordings_dir}", file=sys.stderr)
        sys.exit(1)
    report = analyze_all(recordings_dir)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print_report(report)
    s = report["summary"]
    if report.get("flat"):
        failed = s["videos_total"] > 0 and s["videos_ok"] == 0
    else:
        failed = (s["webcam_total"] > 0 and s["webcam_ok"] == 0) or (
            s["screen_total"] > 0 and s["screen_ok"] == 0
        )
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
