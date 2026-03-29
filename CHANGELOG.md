# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- **Webcam horizontal flip** (`recorder/core/webcam.py`): after each frame is read from the camera, the pipeline can apply `cv2.flip(frame, 1)` so left and right match real-world orientation. The same correction is used for the live preview and for frames written to the webcam MP4, so they stay consistent.

### Changed

- **Configuration** (`recorder/config.py`): new setting `WEBCAM_FLIP_HORIZONTAL` with three modes:
  - `True`: always flip (use on any OS if the image is still mirror-like).
  - `False`: never flip.
  - `"auto"` (default): flip only when the built-in rules expect a mirrored driver stream (see below).

- **Windows camera backends** (`recorder/core/webcam.py`): opening the webcam now tries **DirectShow** first, then **Media Foundation (MSMF)**, then a plain `VideoCapture(index)` fallback, so more devices open reliably and behavior is easier to reason about than MSMF-only.

### Why

Many Windows webcam drivers deliver a **horizontally mirrored** image (like looking in a mirror: text and hands appear reversed compared to how others see you or how a normal photo looks). Without a flip, preview and recordings stay mirrored.

An earlier `"auto"` rule only flipped when using **MSMF**. The app prefers **DirectShow** when it works, so the flip often never ran and the picture stayed mirrored. The current logic flips under `"auto"` for **all** of this app’s Windows capture paths (`dshow`, `msmf`, and the generic fallback). On **Linux and macOS**, typical OpenCV capture is usually already correct, so `"auto"` leaves the image unchanged there; users with unusual drivers can set `WEBCAM_FLIP_HORIZONTAL = True`.

Keeping **`"auto"`** as the default avoids hard-coding `sys.platform` in `config.py` while still picking a sensible behavior per OS in one place (`_effective_horizontal_flip` in `webcam.py`).
