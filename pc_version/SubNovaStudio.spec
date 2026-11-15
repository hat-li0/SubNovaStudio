# -*- mode: python ; coding: utf-8 -*-
import shiboken6
import os
from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

shiboken_dir = os.path.dirname(shiboken6.__file__)
shiboken_dll = os.path.join(shiboken_dir, 'shiboken6.abi3.dll')

datas = [
    ('app/resources', 'app/resources'),
]

if os.path.exists(shiboken_dll):
    datas.append((shiboken_dll, 'PySide6'))


hiddenimports = [
    'qasync',
    'pysubs2',
    'rapidfuzz',
    'pydantic',
    'pydantic_settings',
    'httpx',
    'orjson',
    'sqlite3',
    'winsound',
    'charset_normalizer',
    'unicodedata',
    'PySide6.QtCore',
    'PySide6.QtGui',
    'PySide6.QtWidgets',
    'PySide6.QtMultimedia',
    'PySide6.QtMultimediaWidgets',
]

# Ensure complete inclusion of all internal app modules and pydantic internals
hiddenimports += collect_submodules('app')
hiddenimports += collect_submodules('pydantic')
hiddenimports += collect_submodules('pydantic_settings')
hiddenimports += collect_submodules('pysubs2')

excludes = [
    'tkinter',
    'matplotlib',
    'scipy',
    'pandas',
    'numpy',
    'PIL',
    'cv2',
    'torch',
    'playwright',
    'streamlit',
    'trimesh',
    'reportlab',
    'pyarrow',
    'IPython',
    'jupyter',
]

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# 1. Onedir Mode (dist/SubNovaStudio/SubNovaStudio.exe)
# Eliminates runtime temp directory extraction (_MEI...) completely,
# loads instantly, avoids Defender temp extraction locks, and never
# triggers 'Could not create temporary directory!'.
exe_onedir = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='SubNovaStudio',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='app/resources/icons/subnova_icon.ico',
    version='version_info.txt',
)

coll = COLLECT(
    exe_onedir,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='SubNovaStudio',
)

# 2. Standalone Onefile Mode (dist/SubNovaStudio_Standalone.exe)
# Retained for single-file portable distribution with custom icon & version info.
exe_onefile = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='SubNovaStudio_Standalone',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='app/resources/icons/subnova_icon.ico',
    version='version_info.txt',
)
