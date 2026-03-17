"""app package: main application window split into focused modules.

Modules
-------
window.py           – App class: __init__, closeEvent, public entry-point.
_ui_mixin.py        – UIMixin: _build, _center_on_screen, _start_previews.
_recording_mixin.py – RecordingMixin: record_both, stop_both, mux helpers.
"""

from recorder.ui.app.window import App

__all__ = ["App"]
