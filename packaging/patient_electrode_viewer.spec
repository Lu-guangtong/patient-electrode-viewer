# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path


PROJECT_ROOT = Path(SPECPATH).parent


a = Analysis(
    [str(PROJECT_ROOT / "src" / "105_patient_electrode_desktop_viewer.py")],
    pathex=[str(PROJECT_ROOT / "src")],
    binaries=[],
    datas=[
        (str(PROJECT_ROOT / "sample_data"), "sample_data"),
        (str(PROJECT_ROOT / "README.md"), "."),
        (str(PROJECT_ROOT / "docs" / "DATA_PREPARATION.md"), "docs"),
        (str(PROJECT_ROOT / "31_patient_electrode_viewer" / "patient_electrode_viewer.ico"), "."),
    ],
    hiddenimports=[
        "pyvistaqt",
        "qtpy",
        "PyQt5",
        "PyQt5.QtCore",
        "PyQt5.QtGui",
        "PyQt5.QtWidgets",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="PatientElectrodeViewer",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=str(PROJECT_ROOT / "31_patient_electrode_viewer" / "patient_electrode_viewer.ico"),
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="PatientElectrodeViewer",
)
