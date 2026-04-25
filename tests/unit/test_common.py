"""Unit tests for `recorder.common` (pure helpers; I/O paths mocked or minimal)."""

import re
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

import recorder.common as common
from recorder.common import (
    create_writer,
    email_filename_part,
    fmt_time,
    frame_to_tk,
    make_even,
    open_webcam,
    resize_frame,
    sanitize_email_for_filename,
    unique_name_with_suffix,
)


def test_make_even():
    assert make_even(0) == 2
    assert make_even(1) == 2
    assert make_even(2) == 2
    assert make_even(3) == 2
    assert make_even(7) == 6
    assert make_even(100) == 100


def test_sanitize_email_for_filename():
    assert sanitize_email_for_filename("a.b@c.edu") == "a_b_at_c_edu"
    assert sanitize_email_for_filename("  A@B.C  ") == "a_at_b_c"
    assert sanitize_email_for_filename("") == ""
    assert sanitize_email_for_filename(None) == ""  # type: ignore[arg-type]
    assert sanitize_email_for_filename(42) == ""  # type: ignore[arg-type]


def test_email_filename_part():
    assert "@" in email_filename_part("a@b.com")
    assert email_filename_part("") == "user"
    assert email_filename_part('bad\\name') == "bad_name"
    assert email_filename_part(None) == "user"  # type: ignore[arg-type]
    assert email_filename_part(99) == "user"  # type: ignore[arg-type]


def test_fmt_time():
    assert fmt_time(0) == "00:00"
    assert fmt_time(65) == "01:05"
    assert fmt_time(3599) == "59:59"
    assert fmt_time(3600) == "60:00"
    assert fmt_time(3661) == "61:01"


def test_unique_name_with_suffix_fresh(tmp_path: Path):
    p = unique_name_with_suffix(tmp_path, "u", "_screen.mp4")
    assert p == tmp_path / "u_screen.mp4"
    assert not p.exists()


def test_unique_name_with_suffix_collision(tmp_path: Path):
    (tmp_path / "u_screen.mp4").write_bytes(b"")
    p = unique_name_with_suffix(tmp_path, "u", "_screen.mp4")
    assert p == tmp_path / "u_1_screen.mp4"


def test_unique_name_with_suffix_increments_numeric_base(tmp_path: Path):
    (tmp_path / "u_1_screen.mp4").write_bytes(b"")
    p = unique_name_with_suffix(tmp_path, "u_1", "_screen.mp4")
    assert p == tmp_path / "u_2_screen.mp4"


def test_unique_name_with_suffix_empty_base_uses_user(tmp_path: Path):
    p = unique_name_with_suffix(tmp_path, "", "_x.mp4")
    assert p == tmp_path / "user_x.mp4"


def test_unique_name_with_suffix_skips_filled_chain(tmp_path: Path):
    (tmp_path / "a_screen.mp4").write_bytes(b"")
    (tmp_path / "a_1_screen.mp4").write_bytes(b"")
    p = unique_name_with_suffix(tmp_path, "a", "_screen.mp4")
    assert p == tmp_path / "a_2_screen.mp4"


def test_create_writer_opens():
    writer = MagicMock()
    writer.isOpened.return_value = True
    with patch.object(common.cv2, "VideoWriter_fourcc", return_value=123), patch.object(
        common.cv2, "VideoWriter", return_value=writer
    ) as vw:
        out, ok = create_writer("/tmp/t.mp4", "mp4v", 15.0, 640, 480)
    assert ok is True
    assert out is writer
    vw.assert_called_once()


def test_create_writer_fails_to_open():
    writer = MagicMock()
    writer.isOpened.return_value = False
    with patch.object(common.cv2, "VideoWriter_fourcc", return_value=123), patch.object(
        common.cv2, "VideoWriter", return_value=writer
    ):
        out, ok = create_writer("/tmp/t.mp4", "mp4v", 15.0, 640, 480)
    assert ok is False
    assert out is writer


def test_open_webcam_first_index_opens():
    good = MagicMock()
    good.isOpened.return_value = True
    with patch.object(common.cv2, "VideoCapture", return_value=good) as vc:
        cap, idx = open_webcam(preferred_index=0, fallback_indices=[1])
    assert cap is good
    assert idx == 0
    vc.assert_called_once()


def test_open_webcam_tries_fallback_when_first_closed():
    bad = MagicMock()
    bad.isOpened.return_value = False
    good = MagicMock()
    good.isOpened.return_value = True
    with patch.object(common.cv2, "VideoCapture", side_effect=[bad, good]) as vc:
        cap, idx = open_webcam(preferred_index=0, fallback_indices=[0, 1])
    assert cap is good
    assert idx == 1
    bad.release.assert_called_once()
    assert vc.call_count == 2


def test_open_webcam_releases_on_failure():
    bad = MagicMock()
    bad.isOpened.return_value = False
    with patch.object(common.cv2, "VideoCapture", return_value=bad):
        cap, idx = open_webcam(preferred_index=0, fallback_indices=[0])
    assert cap is None
    assert idx == -1
    bad.release.assert_called_once()


def test_open_webcam_uses_msmf_on_windows_second_arg():
    if sys.platform != "win32":
        pytest.skip("MSMF branch is Windows-only")
    cv2 = pytest.importorskip("cv2", reason="opencv-python not installed")
    if not hasattr(cv2, "CAP_MSMF"):
        pytest.skip("OpenCV build has no CAP_MSMF")
    good = MagicMock()
    good.isOpened.return_value = True
    with patch.object(common.cv2, "VideoCapture", return_value=good) as vc:
        cap, idx = open_webcam(preferred_index=0, fallback_indices=[])
    assert cap is good
    assert idx == 0
    assert vc.call_args[0][0] == 0
    assert vc.call_args[0][1] == cv2.CAP_MSMF


def test_resize_frame():
    pytest.importorskip("cv2", reason="opencv-python not installed")
    frame = np.zeros((20, 30, 3), dtype=np.uint8)
    out = resize_frame(frame, 10, 8)
    assert out.shape == (8, 10, 3)


@patch("PIL.ImageTk.PhotoImage")
@patch("PIL.Image.fromarray")
def test_frame_to_tk_uses_pil(pil_fromarray, photo_image):
    pytest.importorskip("cv2", reason="opencv-python not installed")
    mock_img = MagicMock()
    pil_fromarray.return_value = mock_img
    ph = MagicMock()
    photo_image.return_value = ph
    frame = np.zeros((2, 2, 3), dtype=np.uint8)
    assert frame_to_tk(frame) is ph
    photo_image.assert_called_once_with(mock_img)


def test_timestamp_format():
    from recorder.common import timestamp

    assert re.match(r"^\d{8}_\d{6}$", timestamp())
