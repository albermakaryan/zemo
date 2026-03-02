#!/usr/bin/env bash
# Linux/macOS launcher for Screen & Webcam Recorder.
# Usage: ./run_recorder.sh   or   bash run_recorder.sh

cd "$(dirname "$0")"

if [ -x "venv/bin/python" ]; then
    PY=venv/bin/python
elif [ -x "env/bin/python" ]; then
    PY=env/bin/python
else
    PY=python3
fi

if ! command -v "$PY" &>/dev/null; then
    echo
    echo "  Python is not installed or not on PATH."
    echo "  Install Python 3.12+ and run this script again."
    echo
    exit 1
fi

"$PY" main.py
exit $?
