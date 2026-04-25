"""Unit tests for `recorder.config` path helpers and directory creation (tmp dirs only)."""

import sys
import types
from pathlib import Path

import pytest

import recorder.config as cfg


def test_get_path_helpers_with_patched_base(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(cfg, "RECORDINGS_DIR", tmp_path)
    assert cfg.get_recordings_dir() == tmp_path
    assert cfg.get_webcam_dir() == tmp_path / cfg.WEBCAM_SUBDIR
    assert cfg.get_screen_dir() == tmp_path / cfg.SCREEN_SUBDIR
    assert cfg.get_audio_dir() == tmp_path / cfg.AUDIO_SUBDIR
    assert cfg.get_detection_dir() == tmp_path / cfg.DETECTION_SUBDIR


def test_ensure_test_recordings_dirs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(cfg, "RECORDINGS_TEST_DIR", tmp_path)
    cfg.ensure_test_recordings_dirs()
    assert (tmp_path / cfg.WEBCAM_SUBDIR).is_dir()
    assert (tmp_path / cfg.SCREEN_SUBDIR).is_dir()
    assert (tmp_path / cfg.AUDIO_SUBDIR).is_dir()


def test_ensure_recordings_dirs_creates_subdirs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(cfg, "RECORDINGS_DIR", tmp_path)
    cfg.ensure_recordings_dirs()
    for sub in (cfg.WEBCAM_SUBDIR, cfg.SCREEN_SUBDIR, cfg.AUDIO_SUBDIR, cfg.GAZE_SUBDIR):
        assert (tmp_path / sub).is_dir()
    assert (tmp_path / ".gitkeep").is_file()
    for sub in (cfg.WEBCAM_SUBDIR, cfg.SCREEN_SUBDIR, cfg.AUDIO_SUBDIR, cfg.GAZE_SUBDIR):
        assert (tmp_path / sub / ".gitkeep").is_file()


def test_fps_limits_sensible():
    assert cfg.FPS_MIN < cfg.FPS_MAX
    assert cfg.FPS_MIN <= cfg.DEFAULT_FPS <= cfg.FPS_MAX


def test_get_test_path_helpers_with_patched_base(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(cfg, "RECORDINGS_TEST_DIR", tmp_path)
    assert cfg.get_test_recordings_dir() == tmp_path
    assert cfg.get_test_webcam_dir() == tmp_path / cfg.WEBCAM_SUBDIR
    assert cfg.get_test_screen_dir() == tmp_path / cfg.SCREEN_SUBDIR
    assert cfg.get_test_audio_dir() == tmp_path / cfg.AUDIO_SUBDIR


def test_sans_font_segoe_when_tkversion_present():
    """`sans_font` uses Segoe when tkinter exposes TkVersion (inner import)."""
    fake = types.ModuleType("tkinter")
    fake.TkVersion = 8.6
    orig = sys.modules.get("tkinter")
    try:
        sys.modules["tkinter"] = fake
        assert cfg.sans_font() == ("Segoe UI", 10)
    finally:
        if orig is not None:
            sys.modules["tkinter"] = orig
        else:
            del sys.modules["tkinter"]


def test_sans_font_helvetica_when_no_tkversion():
    """No TkVersion → Helvetica branch."""
    fake = types.ModuleType("tkinter")
    orig = sys.modules.get("tkinter")
    try:
        sys.modules["tkinter"] = fake
        assert cfg.sans_font() == ("Helvetica", 10)
    finally:
        if orig is not None:
            sys.modules["tkinter"] = orig
        else:
            del sys.modules["tkinter"]
