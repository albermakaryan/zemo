"""Unit tests for `recorder.common` (pure helpers, no I/O in these tests)."""

import re
from pathlib import Path

import pytest

from recorder.common import (
    email_filename_part,
    fmt_time,
    make_even,
    sanitize_email_for_filename,
    unique_name_with_suffix,
)


def test_make_even():
    assert make_even(1) == 2
    assert make_even(2) == 2
    assert make_even(3) == 2
    assert make_even(7) == 6
    assert make_even(100) == 100


def test_sanitize_email_for_filename():
    assert sanitize_email_for_filename("a.b@c.edu") == "a_b_at_c_edu"
    assert sanitize_email_for_filename("  A@B.C  ") == "a_at_b_c"
    assert sanitize_email_for_filename("") == ""


def test_email_filename_part():
    assert "@" in email_filename_part("a@b.com")
    assert email_filename_part("") == "user"
    assert email_filename_part('bad\\name') == "bad_name"


def test_fmt_time():
    assert fmt_time(0) == "00:00"
    assert fmt_time(65) == "01:05"
    assert fmt_time(3599) == "59:59"


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


def test_timestamp_format():
    from recorder.common import timestamp

    assert re.match(r"^\d{8}_\d{6}$", timestamp())
