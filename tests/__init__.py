"""
Test module: run each recorder component separately.

Test recordings are saved under recordings_test/ (webcam/, screen/, audio/).

  python -m tests deps       # Check dependencies
  python -m tests screen     # Screen recording (~5 s)
  python -m tests webcam    # Webcam recording (~5 s)
  python -m tests audio     # System audio (~10 s, Windows)
  python -m tests ui        # Full app window

Or run one test file:

  python -m tests.test_deps
  python -m tests.test_screen --seconds 10
  python -m tests.test_webcam
  python -m tests.test_audio
  python -m tests.test_ui
"""

from tests.test_deps import run_deps

__all__ = ["run_deps"]
