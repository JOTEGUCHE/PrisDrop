"""Biblioteca local: índice de metadatos y escaneo de las carpetas de descarga."""
import json
import os
from dataclasses import dataclass
from pathlib import Path

from .paths import data_dir

VIDEO_EXT = {".mp4", ".mkv", ".webm", ".mov", ".avi", ".m4v"}
AUDIO_EXT = {".mp3", ".m4a", ".opus", ".ogg", ".flac", ".wav", ".aac"}


@dataclass
class MediaItem:
    path: str
    title: str
    artist: str
    date: str          # AAAAMMDD tal como lo entrega YouTube
    duration: int      # segundos (0 si se desconoce)
    kind: str          # "video" | "audio"
    thumb: str         # ruta a la miniatura .jpg o ""
    mtime: float
    album: str = ""
    genre: str = ""
    lyrics: str = ""
    composer: str = ""
    comment: str = ""


def pretty_date(raw: str) -> str:
    raw = (raw or "").strip()
    if len(raw) == 8 and raw.isdigit():
        return f"{raw[6:]}/{raw[4:6]}/{raw[:4]}"
    return raw


def _key(path) -> str:
    return os.path.normcase(os.path.abspath(str(path)))


class Library:
    def __init__(self):
        self._file = data_dir() / "library.json"
        self._index: dict = {}
        try:
            self._index = json.loads(self._file.read_text("utf-8"))
        except Exception:
            pass

    def _save(self):
        try:
            self._file.write_text(json.dumps(self._index, ensure_ascii=False, indent=1), "utf-8")
        except OSError:
            pass

    def register(self, meta: dict):
        """Guarda autor, fecha y duración de un archivo recién descargado."""
        path = meta.get("filepath")
        if not path:
            return
        self._index[_key(path)] = {
            "title": meta.get("title", ""),
            "artist": meta.get("uploader", "") or "",
            "date": meta.get("upload_date", "") or "",
            "duration": int(meta.get("duration") or 0),
        }
        self._save()

    def update_metadata(self, path: str, values: dict, thumb: str = ""):
        key = _key(path)
        current = self._index.get(key, {})
        current.update({
            "title": values.get("title", ""),
            "artist": values.get("artist", ""),
            "album": values.get("album", ""),
            "date": values.get("date", ""),
            "genre": values.get("genre", ""),
            "composer": values.get("composer", ""),
            "comment": values.get("comment", ""),
            "lyrics": values.get("lyrics", ""),
        })
        if thumb:
            current["thumb"] = thumb
        else:
            current.pop("thumb", None)
        self._index[key] = current
        self._file.write_text(json.dumps(self._index, ensure_ascii=False, indent=1), "utf-8")

    def scan(self, folders) -> list:
        items, seen = [], set()
        for folder in folders:
            root = Path(folder)
            if not root.exists():
                continue
            for p in root.rglob("*"):
                ext = p.suffix.lower()
                if ext in VIDEO_EXT:
                    kind = "video"
                elif ext in AUDIO_EXT:
                    kind = "audio"
                else:
                    continue
                key = _key(p)
                if key in seen:
                    continue
                seen.add(key)
                meta = self._index.get(key, {})
                thumb = p.with_suffix(".jpg")
                try:
                    mtime = p.stat().st_mtime
                except OSError:
                    continue
                items.append(MediaItem(
                    path=str(p), title=meta.get("title") or p.stem,
                    artist=meta.get("artist", ""), date=meta.get("date", ""),
                    duration=meta.get("duration", 0), kind=kind,
                    thumb=meta.get("thumb") if meta.get("thumb") and Path(meta["thumb"]).exists()
                    else str(thumb) if thumb.exists() else "", mtime=mtime,
                    album=meta.get("album", ""), genre=meta.get("genre", ""),
                    lyrics=meta.get("lyrics", ""), composer=meta.get("composer", ""),
                    comment=meta.get("comment", "")))
        items.sort(key=lambda i: i.mtime, reverse=True)
        return items
