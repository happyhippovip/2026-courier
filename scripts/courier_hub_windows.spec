# -*- mode: python ; coding: utf-8 -*-
"""Unsigned PyInstaller spec for the Courier Desktop Hub.

The hidden-import list and the static data directory are the contract checked
by tests/test_windows_exe_build.py. PyInstaller does not see files that the
hub opens with Path(__file__) / "static", so that directory is an explicit
data path. codesign_identity stays None: nothing is signed and nothing is bought.
"""
from pathlib import Path

_spec_path = Path(SPECPATH).resolve()
ROOT = _spec_path.parents[1] if (_spec_path.is_file() or _spec_path.name.endswith(".spec")) else _spec_path.parent
ENTRY = "courier_hub/__main__.py"

hiddenimports = [
    "courier_hub",
    "courier_hub.server",
    "courier_hub.model",
    "courier_hub.kolibri_data",
    "courier_core",
    "courier_core.build",
    "courier_core.journal",
    "courier_core.projection",
    "courier_core.events",
    "courier_core.state_machine",
]

datas = [
    (str(ROOT / "courier_hub" / "static"), "courier_hub/static"),
]

a = Analysis(
    [str(ROOT / ENTRY)],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["courier_overlay"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="CourierHub",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
