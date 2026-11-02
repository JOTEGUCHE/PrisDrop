"""Configuración del usuario guardada en JSON."""
import json
from pathlib import Path

from .paths import data_dir, default_media_dir

DEFAULTS = {
    "video_dir": str(default_media_dir() / "Videos"),
    "audio_dir": str(default_media_dir() / "Musica"),
    "kind": "video",
    "container": "mp4",
    "audio_format": "mp3",
    "volume": 70,
    "cookies_browser": "",   # "", "firefox", "brave", "chrome", "edge"...
    "pages": [],             # [{"name": ..., "url": ...}]
    "active_theme": "Predeterminado",
}


class Settings:
    def __init__(self):
        self._path = data_dir() / "settings.json"
        self._data = dict(DEFAULTS)
        try:
            self._data.update(json.loads(self._path.read_text("utf-8")))
        except Exception:
            pass
        legacy_root = default_media_dir().parent / "Descargatube"
        media_root = default_media_dir()
        migrated = False
        for key, folder in (("video_dir", "Videos"), ("audio_dir", "Musica")):
            configured = Path(self._data.get(key) or DEFAULTS[key])
            legacy_path = legacy_root / folder
            if configured.resolve() == legacy_path.resolve():
                self._data[key] = str(media_root / folder)
                migrated = True
            Path(self._data[key]).mkdir(parents=True, exist_ok=True)
        if migrated:
            self._path.write_text(
                json.dumps(self._data, indent=2, ensure_ascii=False), "utf-8")

    def get(self, key):
        return self._data.get(key, DEFAULTS.get(key))

    def set(self, key, value):
        self._data[key] = value
        try:
            self._path.write_text(json.dumps(self._data, indent=2, ensure_ascii=False), "utf-8")
        except OSError:
            pass
