# Syncing and merging webcam, screen, and audio

Recordings are **already time-aligned**: they share the same start (barrier) and stop time, so a single **time index** (frame index or seconds) applies to all three.

---

## 1. Add audio into the video file (one file with sound)

To get a **single screen (or webcam) video that includes the audio track**:

```bash
python -m recorder.audio.mux_audio_into_video user@edu.ysu.am
```

- Requires **ffmpeg** on PATH.
- Produces:
  - `recordings/screen/<email>_screen_with_audio.mp4`
  - `recordings/webcam/<email>_webcam_with_audio.mp4`
- Original video-only and WAV files are unchanged.

Use these `*_with_audio.mp4` files when you need one file per stream with sound (e.g. for sharing or editing in a video editor).

---

## 2. Merge for analytics (same time base, three streams)

For **data analysis / ML**, treat the three streams as one aligned dataset:

- **Time base**: frame index `i` → time in seconds = `i / FPS` (e.g. 30 FPS → 1/30 s per frame).
- **Audio**: at 44.1 kHz, the audio slice for frame `i` is samples from `(i/FPS)*44100` to `((i+1)/FPS)*44100`.

### Using the merge helper

```python
from validation.merge_recordings import open_synced, SyncedRecordings

# By email (base name used for filenames)
with open_synced("albermakaryan@edu.ysu.am") as synced:
    print(synced.n_frames, synced.duration_sec)

    # Per-frame: get webcam frame, screen frame, and audio chunk for that frame
    for frame_index, webcam_bgr, screen_bgr, audio_chunk in synced.iter_frames():
        # webcam_bgr, screen_bgr: (H, W, 3) BGR or None
        # audio_chunk: (channels, samples) float32, e.g. (2, 1470) for one frame at 44.1kHz
        pass

    # Or by time range (seconds)
    audio_segment = synced.get_audio_for_time_range(0.0, 1.0)  # first second
```

### Merge semantics

| Concept        | Video                | Audio                          |
|----------------|----------------------|---------------------------------|
| Time base      | Frame index `i`      | Same: `t_sec = i / FPS`        |
| Unit           | 1 frame = 1/30 s     | Samples = `t_sec * 44100`      |
| Join key       | `frame_index` or `t_sec` | Use `frame_index_to_time_sec(i)` then sample range |

So in pandas/Spark terms: you have three “tables” (webcam frames, screen frames, audio samples) that you **join on time** (or frame index). The helper gives you aligned slices per frame or per time range.

### Example: export per-frame features for ML

```python
with open_synced("user@edu.ysu.am") as synced:
    for i, webcam, screen, audio in synced.iter_frames():
        # Extract features for frame i (aligned)
        # webcam: face/gaze model input
        # screen: content/attention model input
        # audio: transcript or embedding for same time window
        feature_vec = your_featurizer(webcam, screen, audio)
```

---

## Summary

| Goal                         | Method |
|-----------------------------|--------|
| One screen video with sound | `python -m recorder.audio.mux_audio_into_video <email>` |
| Aligned streams for analysis | `validation.merge_recordings.open_synced(email)` and `iter_frames()` or `get_audio_for_time_range()` |
