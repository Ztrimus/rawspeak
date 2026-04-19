# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for building RawSpeak as a macOS .app bundle."""

import sys
from pathlib import Path

block_cipher = None

APP_ICON = "assets/RawSpeak.icns"
APP_VERSION = "0.0.0"

try:
    ns = {}
    init_path = Path(__file__).resolve().parent / "rawspeak" / "__init__.py"
    exec(init_path.read_text(encoding="utf-8"), ns)
    APP_VERSION = str(ns.get("__version__", APP_VERSION))
except Exception:
    # Keep build resilient; release CI reads version independently.
    pass

a = Analysis(
    ["app_entry.py"],
    pathex=["."],
    binaries=[],
    datas=[],
    hiddenimports=[
        "pynput",
        "pynput.keyboard",
        "pynput.keyboard._darwin",
        "pynput.mouse",
        "pynput.mouse._darwin",
        "sounddevice",
        "numpy",
        "torch",
        "transformers",
        "transformers.models.whisper",
        "pyperclip",
        "pyautogui",
        "pystray",
        "pystray._darwin",
        "PIL",
        "PIL.Image",
        "PIL.ImageDraw",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["matplotlib", "IPython", "notebook", "scipy"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="RawSpeak",
    icon=APP_ICON,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    target_arch=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name="RawSpeak",
)

app = BUNDLE(
    coll,
    name="RawSpeak.app",
    bundle_identifier="com.rawspeak.app",
    icon=APP_ICON,
    info_plist={
        "CFBundleShortVersionString": APP_VERSION,
        "CFBundleName": "RawSpeak",
        "CFBundleDisplayName": "RawSpeak",
        "NSMicrophoneUsageDescription": "RawSpeak needs microphone access to record your voice for transcription.",
        "NSAppleEventsUsageDescription": "RawSpeak needs accessibility access to paste transcribed text.",
        "LSUIElement": True,
    },
)
