# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for remote_admintool.py (onedir, console)

from PyInstaller.utils.hooks import collect_submodules

hiddenimports = []
hiddenimports += ['_curses', 'curses']
hiddenimports += collect_submodules('Crypto')

a = Analysis(
    ['remote_admintool.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('client_config.ini', '.'),
    ],
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'numpy',
        'PIL',
        'sqlalchemy',
        'libs',
        'libs.PySimpleGUI',
        'PySimpleGUI',
        'pyperclip',
        'blobmgr',
        'user_management',
        'admin_management',
        'server_management',
        'misc_management',
        'consolegui_utils',
        'utilities',
        'globals',
        'base_dbdriver',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='remote_admintool',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='remote_admintool',
)
