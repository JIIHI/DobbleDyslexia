"""File locations that work both from source and from a PyInstaller bundle."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from wordspot import APP_ID


def resource_dir() -> Path:
    """Folder holding the bundled read-only resources (fonts, data)."""
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return Path(base) / "wordspot"
    return Path(__file__).resolve().parent


def fonts_dir() -> Path:
    return resource_dir() / "fonts"


def data_dir() -> Path:
    return resource_dir() / "data"


def user_data_dir() -> Path:
    """Per-user writable folder where the SQLite database lives."""
    override = os.environ.get("WORDSPOT_DATA_DIR")
    if override:
        path = Path(override)
    elif sys.platform == "darwin":
        path = Path.home() / "Library" / "Application Support" / APP_ID
    elif sys.platform.startswith("win"):
        path = Path(os.environ.get("APPDATA", Path.home())) / APP_ID
    else:
        path = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / APP_ID
    path.mkdir(parents=True, exist_ok=True)
    return path
