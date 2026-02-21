# PyInstaller spec for Recorder.exe
# Run: pyinstaller Recorder.spec

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[],
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
        'cv2',
        'numpy',
        'mss',
        'mss.windows',
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
)
