# Validation

Quality checks for recorder output (webcam and screen MP4s).

- **View merged data**: run `python -m validation.view_merged` to see webcam and screen side-by-side (aligned by frame). Q = quit, SPACE = pause.
- **Merge for analytics**: see `merge_recordings.py` and `docs/SYNC_AND_MERGE.md`.

## Run

From project root:

```bash
# Use default recordings folder (project/recordings)
python -m validation.analyze_recordings

# Use a specific folder
python -m validation.analyze_recordings "C:\path\to\recordings"

# Full report as JSON
python -m validation.analyze_recordings --json
```

## Checks

For each `.mp4` in `recordings/webcam/` and `recordings/screen/`:

- **Open**: File can be opened with OpenCV
- **Props**: Width, height, FPS, frame count, duration
- **Structure**: Even dimensions, positive duration, FPS near expected (20)
- **Content**: Sample frames (first, middle, last) are not all black; mean brightness and variance indicate real content

Exit code: `0` if all found files pass, `1` if any category has only failures.
