# PyInstaller spec for Recorder.exe
# Run: pyinstaller Recorder.spec

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('VERSION', '.'),           # make VERSION available at runtime
    ],
    hiddenimports=[
        'recorder',
        'recorder.config',
        'recorder.common',
        'recorder.recorders',
        'recorder.webcam_recorder',
        'recorder.screen_recorder',
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
    ],
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
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # No console window (GUI app)
    version='version_info.txt',  # embed Windows version resource
)
