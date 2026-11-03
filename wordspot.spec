# PyInstaller build file:  pyinstaller wordspot.spec
# Produces dist/Word Spot.app on macOS and dist/Word Spot/Word Spot.exe on Windows.
import sys

block_cipher = None
APP = "Word Spot"

a = Analysis(
    ["run_wordspot.py"],
    pathex=[],
    datas=[("wordspot/fonts", "wordspot/fonts"), ("wordspot/data", "wordspot/data")],
    hiddenimports=[],
    excludes=["tkinter", "numpy", "lxml", "PySide6.QtWebEngineCore", "PySide6.QtQml", "PySide6.QtQuick",
              "PySide6.Qt3DCore", "PySide6.QtMultimedia", "PySide6.QtCharts"],
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

icon = "wordspot/data/icon.icns" if sys.platform == "darwin" else "wordspot/data/icon.ico"

exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name=APP,
    console=False,
    icon=icon,
)
coll = COLLECT(exe, a.binaries, a.datas, name=APP)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name=f"{APP}.app",
        icon=icon,
        bundle_identifier="org.wordspot.app",
        info_plist={
            "CFBundleShortVersionString": "1.0.0",
            "NSHighResolutionCapable": True,
            "LSApplicationCategoryType": "public.app-category.education",
        },
    )
