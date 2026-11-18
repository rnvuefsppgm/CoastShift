# -*- mode: python ; coding: utf-8 -*-
# PyInstaller: executável único (onefile), sem console, Windows 10/11 64 bits.
from PyInstaller.utils.hooks import collect_all

datas, binaries, hidden = [], [], []
for pkg in ("rasterio", "pyproj"):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hidden += h

a = Analysis(
    ["app.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hidden + ["matplotlib.backends.backend_tkagg", "scipy.ndimage", "scipy.stats"],
    excludes=["IPython", "jupyter", "notebook", "pytest", "xarray", "geopandas", "PyQt5", "PyQt6",
              "PySide2", "PySide6", "rasterio.tests"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [],
    name="CoastShift",
    console=False,
    upx=False,
    runtime_tmpdir=None,
)
