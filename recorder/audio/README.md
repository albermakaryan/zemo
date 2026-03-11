# Audio recording module

Records **internal (system) audio** — what is playing on the PC (e.g. online course in the browser).

## Requirements

- **Windows**: WASAPI loopback — `pip install PyAudioWPatch` (or `pip install -e ".[windows]"`)
- **Linux / macOS**: sounddevice (PulseAudio/PipeWire on Linux) — `pip install sounddevice` (or `pip install -e ".[linux]"`)

Dispatch: Windows → internal_win; otherwise → internal_linux (Linux and macOS).

## Quick test (no app integration)

From project root:

```bash
python -m recorder.audio.record_test
```

1. The script starts a **5-second countdown**. Open your video (e.g. YouTube in the browser) and get ready to press Play.
2. When it says **"Recording now. Start your video!"**, press Play. The recorder captures system audio (the video’s sound) for **30 seconds**.
3. Output is saved to `recordings/audio/test_audio.wav`. Play that file to confirm the video’s audio was captured.

## Usage

```python
from recorder.audio import InternalAudioRecorder, is_loopback_available

if not is_loopback_available():
    print("System audio capture not available (Windows: PyAudioWPatch; Linux/macOS: sounddevice)")

recorder = InternalAudioRecorder(on_status=..., on_done=...)
recorder.start(save_dir="recordings/audio", email="user@example.com")
# ... later ...
recorder.stop(stop_time=time.time())
recorder.join()
# → recordings/audio/user@example.com_audio.wav
```

## Sync with video (integrated in app)

When you click **Record Both**, the app starts webcam, screen, and internal audio together (when system audio is available on your platform). All three use the same **Barrier(3)** and the same **stop_time**, so the WAV is aligned with the two videos. Outputs:

- `recordings/webcam/<email>_webcam.mp4`
- `recordings/screen/<email>_screen.mp4`
- `recordings/audio/<email>_audio.wav`

## Audio in video vs separate file

- **Separate (default)**: Webcam and screen stay video-only; audio is in `<email>_audio.wav`. You can play the WAV alongside the video in any editor, or mux later.
- **Mux into video (optional)**: To get one file per stream with sound, use ffmpeg after recording:

  ```bash
  python -m recorder.audio.mux_audio_into_video user@example.com
  ```

  Requires **ffmpeg** on PATH. Creates `*_webcam_with_audio.mp4` and `*_screen_with_audio.mp4`; originals are unchanged.

## Output

- **Path**: `recordings/audio/<email>_audio.wav`
- **Format**: WAV, 16-bit, stereo (or device default), 44.1 kHz (or device default)
- **Naming**: Same base name as webcam/screen (`email_audio.wav`) for easy pairing.

## External (microphone) audio

Not implemented yet. For “all voicing from outside” you would add a second recorder that captures the default microphone; the same start/stop sync would apply.
