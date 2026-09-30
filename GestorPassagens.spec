# -*- mode: python ; coding: utf-8 -*-
# PyInstaller: modo onedir (pasta), sem console, com ícone e a pasta recursos\.
from PyInstaller.utils.hooks import collect_data_files

datas = [("recursos", "recursos")]
datas += collect_data_files("tzdata")

a = Analysis(
    ["app.py"],
    pathex=["."],
    binaries=[],
    datas=datas,
    hiddenimports=[
        "keyring.backends.Windows",
        "win32ctypes.core",
        "zoneinfo",
        "tzdata",
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "pytest", "_pytest", "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets",
              "PySide6.Qt3DCore", "PySide6.QtMultimedia", "PySide6.QtQuick", "PySide6.QtQml"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="GestorPassagens",
    debug=False,
    strip=False,
    upx=False,
    console=False,
    icon="recursos/icone.ico",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="GestorPassagens",
)
