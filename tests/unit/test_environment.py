"""Smoke: core third-party imports the manual `tests` harness expects to exist."""

import pytest

cv2 = pytest.importorskip("cv2", reason="opencv-python not installed")
np = pytest.importorskip("numpy", reason="numpy not installed")
pytest.importorskip("mss", reason="mss not installed")
pytest.importorskip("PIL", reason="Pillow not installed")
pytest.importorskip("PySide6", reason="PySide6 not installed")

from tests.test_deps import check_deps  # noqa: E402


def test_check_deps_succeeds_with_project_environment():
    assert check_deps(verbose=False) is True
