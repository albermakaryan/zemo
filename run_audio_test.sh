#!/usr/bin/env bash
# Test system audio only (no full app). Records for N seconds and saves a WAV.
# Windows: WASAPI.  Linux: PulseAudio/PipeWire monitor (pip install -e ".[linux]").
# Usage: ./run_audio_test.sh [SECONDS]
set -e
cd "$(dirname "$0")"
SEC="${1:-15}"
python3 -m tests audio --seconds "$SEC"
