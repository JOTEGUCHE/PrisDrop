"""Rutas de la aplicación (datos, herramientas y carpetas de medios)."""
import os
import sys
from pathlib import Path

APP_NAME = "PrisDrop"


def data_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", str(Path.home())))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share")))
    d = base / APP_NAME
    legacy = base / "Descargatube"
    if not d.exists() and legacy.is_dir():
        legacy.replace(d)
    d.mkdir(parents=True, exist_ok=True)
    return d


def bin_dir() -> Path:
    """Carpeta donde viven yt-dlp y FFmpeg descargados por la app."""
    d = data_dir() / "bin"
    d.mkdir(parents=True, exist_ok=True)
    return d


def default_media_dir() -> Path:
    return Path.home() / APP_NAME


def legacy_media_dirs() -> tuple[Path, Path]:
    """Carpetas predeterminadas de medios de la versión anterior."""
    legacy_root = Path.home() / "Descargatube"
    return legacy_root / "Videos", legacy_root / "Musica"
