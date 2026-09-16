# -*- mode: python ; coding: utf-8 -*-

import os

all_datas = [
    ('resources', 'resources')
]

all_binaries = []

all_hidden = [
    'win32com.client',
    'markdown.extensions.tables',
    'markdown.extensions.fenced_code',
    'markdown.extensions.nl2br',
    'markdown.extensions.sane_lists',
    'edge_tts',
    'PySide6.QtMultimedia'
]

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=all_binaries,
    datas=all_datas,
    hiddenimports=all_hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['runtime_hooks/pyside6_dll_path.py'],
    excludes=[
        'torch', 'torchvision', 'torchaudio', 'scipy', 'matplotlib', 
        'tensorboard', 'tkinter', 'piper', 'onnxruntime', 'sudachipy', 
        'pypinyin', 'g2p_en', 'pyopenjtalk', 'nltk'
    ],
    noarchive=False,
    optimize=0,
)

# PyInstaller can discover an unrelated ICU runtime through the build machine's
# PATH. Bundling that DLL overrides the Windows ICU runtime used by Qt and makes
# PySide6 fail to import. Qt on Windows should resolve ICU from System32 here.
a.binaries = [
    entry for entry in a.binaries
    if os.path.basename(entry[0]).lower() != 'icuuc.dll'
]
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Just Translate',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['resources/icon.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Just Translate',
)
