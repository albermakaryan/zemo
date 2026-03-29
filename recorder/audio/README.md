# Audio recording module

Records **internal (system) audio** — what is playing on the PC (e.g. an online course in the browser).

## Requirements

- **Windows**: WASAPI loopback — `pip install PyAudioWPatch` (or `pip install -e ".[windows]"`)
- **Linux / macOS**: sounddevice (PulseAudio/PipeWire on Linux) — `pip install sounddevice` (or `pip install -e ".[linux]"`)
- **PyAV** (optional but recommended for exact sync): `pip install av`

Dispatch: Windows → `internal_win`; otherwise → `internal_linux` (Linux and macOS).

## Quick test (no app integration)

From project root:

```bash
python -m recorder.audio.record_test
```

1. The script starts a **5-second countdown**. Open your video and get ready to press Play.
2. When it says **"Recording now. Start your video!"**, press Play. The recorder captures system audio for **30 seconds**.
3. Output is saved to `recordings/audio/test_audio.mka` (or `.wav`). Play it to confirm capture.

## Usage

```python
from recorder.audio import InternalAudioRecorder, is_loopback_available

if not is_loopback_available():
    print("System audio not available (Windows: PyAudioWPatch; Linux/macOS: sounddevice)")

recorder = InternalAudioRecorder(on_status=..., on_done=...)
recorder.start(save_dir="recordings/audio", email="user@example.com")
# ... later ...
recorder.stop(stop_time=time.time())
recorder.join()
# → recordings/audio/user@example.com_audio.mka  (or .wav without PyAV)
```

## Sync architecture (Windows)

The Windows backend (`internal_win.py`) uses a two-tier design to keep sync exact:

### WASAPI callback (audio thread)
- Runs in a dedicated PortAudio thread — **never touches disk**.
- Reads `time_info['input_buffer_adc_time']` (hardware ADC clock) and converts it to a PTS in sample units.
- Enqueues `(pts, raw_bytes)` into a bounded in-memory queue (max ~46 s of buffer).

### Writer thread
- Drains the queue and writes FLAC frames with explicit PTS into a Matroska container (`.mka`) via PyAV.
- Tracks `self._frames_written` so the recorder always knows its position in the audio timeline.
- On teardown, flushes the FLAC encoder and closes the container cleanly.

### Why this keeps sync through pause/resume

The WASAPI ADC clock ticks continuously even when the audio device is idle (e.g. the user pauses the watched video). When callbacks stop during a pause and then resume, `input_buffer_adc_time` of the next callback reflects the full elapsed time. That difference becomes a PTS jump in the Matroska container — the file encodes the gap as a fact, not approximated silence.

If the driver returns `input_buffer_adc_time == 0` (some WASAPI implementations), the code falls back to `time.perf_counter()` gap detection: when the inter-callback interval exceeds **8× the nominal callback period** (~186 ms at 44100 Hz / 1024 chunk), the PTS is advanced by the measured gap. Same result, slightly less precision.

Without PyAV, the recorder writes a WAV with silence padding on detected gaps.

## Output

| Condition | File | Format |
|---|---|---|
| PyAV installed | `<email>_audio.mka` | Matroska + FLAC, hardware PTS |
| No PyAV | `<email>_audio.wav` | WAV, silence-padded on gaps |

Both files start at PTS 0 aligned with the video barrier start.

## Muxing audio into video

```bash
python -m recorder.audio.mux_audio_into_video user@example.com
```

Requires **ffmpeg** on PATH (or `pip install imageio-ffmpeg`). Prefers `.mka` over `.wav` when both exist. Creates:

- `recordings/screen_with_audio/<email>_screen_with_audio.mp4`
- `recordings/webcam/<email>_webcam_with_audio.mp4` (unless `--screen-only`)

ffmpeg aligns streams by PTS — no `aresample=async` or `-vsync cfr` needed when using `.mka`.

## External (microphone) audio

Not implemented. To add: use a second `InternalAudioRecorder`-style class targeting the default input device with the same start/stop barrier.
