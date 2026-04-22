# PyInstaller spec for Recorder.exe
# Run: pyinstaller Recorder.spec

import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_submodules

# eyetrax loads submodules lazily (__getattr__). PyInstaller will miss e.g. gaze,
# calibration, … unless we bundle the whole package. This is only the eyetrax
# wheel — not other dependencies.
_eyetrax_submodules = collect_submodules("eyetrax")
_eyetrax_data = collect_data_files("eyetrax")

# eyetrax → MediaPipe Tasks (FaceLandmarker). Needs .pyd/DLLs + mediapipe.tasks.c etc.
_mp_datas, _mp_binaries, _mp_hidden = collect_all("mediapipe")

block_cipher = None

# Bundle VC++ 2015-2022 runtime DLLs so the exe works on machines that don't
# have the redistributable installed. UPX must not compress them (see upx_exclude).
_vcredist_names = [
    'vcruntime140.dll',
    'vcruntime140_1.dll',
    'msvcp140.dll',
    'msvcp140_1.dll',
    'msvcp140_2.dll',
    'concrt140.dll',
]
_search_dirs = [
    Path(os.environ.get('SystemRoot', 'C:/Windows')) / 'System32',
    Path(os.environ.get('SystemRoot', 'C:/Windows')) / 'SysWOW64',
]
_found_dlls = []
for _dll in _vcredist_names:
    for _d in _search_dirs:
        _p = _d / _dll
        if _p.exists():
            _found_dlls.append((str(_p), '.'))
            break

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=_found_dlls + _mp_binaries,
    datas=[
        ('VERSION', '.'),           # make VERSION available at runtime
    ] + _eyetrax_data + _mp_datas,
    hiddenimports=[
        'recorder',
        'recorder.config',
        'recorder.common',
        'recorder.recorders',
        'recorder.core',
        'recorder.core.webcam',
        'recorder.core.screen',
        'recorder.ui',
        'recorder.ui.app',
        'recorder.ui.panels',
        'recorder.ui.float_button',
        'recorder.ui.dialogs',
        'recorder.audio',
        'recorder.audio.internal',
        'recorder.audio.internal_win',
        'recorder.audio.internal_linux',
        'pyaudiowpatch',
        'cv2',
        'numpy',
        'mss',
        'mss.windows',
        # Screen capture: dynamically imported in screen_recorder (dxcam preferred over mss on Windows)
        'dxcam_cpp',
        'dxcam',
        'PIL',
        'PIL._tkinter_finder',
        'PIL.Image',
        'PIL.ImageTk',
        'imageio_ffmpeg',
    ] + _eyetrax_submodules + _mp_hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='Recorder',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[
        # UPX breaks these DLLs — must be left uncompressed
        'vcruntime140.dll',
        'vcruntime140_1.dll',
        'msvcp140.dll',
        'msvcp140_1.dll',
        'msvcp140_2.dll',
        'concrt140.dll',
        'python3*.dll',
    ],
    runtime_tmpdir=None,
    console=False,  # No console window (GUI app)
    version='version_info.txt',  # embed Windows version resource
)
