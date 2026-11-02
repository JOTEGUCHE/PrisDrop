"""Lectura y escritura de metadatos para archivos de audio locales."""
import base64
from pathlib import Path

from mutagen import File as MutagenFile
from mutagen.flac import FLAC, Picture
from mutagen.id3 import (APIC, TALB, TCOM, TCON, TDRC, TIT2, TPE1, TRCK, USLT)
from mutagen.mp3 import MP3
from mutagen.mp4 import MP4, MP4Cover
from mutagen.oggflac import OggFLAC
from mutagen.oggopus import OggOpus
from mutagen.oggvorbis import OggVorbis
from mutagen.wave import WAVE


FIELDS = ("title", "artist", "album", "date", "genre", "composer", "track", "comment", "lyrics")

_ID3_FRAMES = {
    "title": TIT2,
    "artist": TPE1,
    "album": TALB,
    "date": TDRC,
    "genre": TCON,
    "composer": TCOM,
    "track": TRCK,
}
_MP4_KEYS = {
    "title": "\xa9nam",
    "artist": "\xa9ART",
    "album": "\xa9alb",
    "date": "\xa9day",
    "genre": "\xa9gen",
    "composer": "\xa9wrt",
    "comment": "\xa9cmt",
    "lyrics": "\xa9lyr",
}


def _first(value):
    if isinstance(value, list):
        return value[0] if value else ""
    return value or ""


def read_audio_metadata(path: str) -> dict:
    audio = MutagenFile(path)
    if audio is None or audio.tags is None:
        return {}
    tags = audio.tags
    result = {}

    if isinstance(audio, (MP3, WAVE)):
        names = {field: frame.__name__ for field, frame in _ID3_FRAMES.items()}
        for field, frame_name in names.items():
            frame = tags.get(frame_name)
            if frame is not None:
                result[field] = str(_first(frame.text))
        lyrics = tags.getall("USLT")
        if lyrics:
            result["lyrics"] = lyrics[0].text
        comments = tags.getall("COMM")
        if comments:
            result["comment"] = comments[0].text
    elif isinstance(audio, MP4):
        for field, key in _MP4_KEYS.items():
            value = _first(tags.get(key))
            if value:
                result[field] = str(value)
        track = _first(tags.get("trkn"))
        if track:
            result["track"] = str(track[0])
    else:
        keys = {
            "title": "title", "artist": "artist", "album": "album",
            "date": "date", "genre": "genre", "composer": "composer",
            "track": "tracknumber", "comment": "comment", "lyrics": "lyrics",
        }
        for field, key in keys.items():
            value = _first(tags.get(key))
            if value:
                result[field] = str(value)
    return result


def read_audio_cover(path: str) -> bytes | None:
    audio = MutagenFile(path)
    if audio is None or audio.tags is None:
        return None
    if isinstance(audio, (MP3, WAVE)):
        pictures = audio.tags.getall("APIC")
        return pictures[0].data if pictures else None
    if isinstance(audio, MP4):
        pictures = audio.tags.get("covr", [])
        return bytes(pictures[0]) if pictures else None
    if hasattr(audio, "pictures") and audio.pictures:
        return audio.pictures[0].data
    encoded = _first(audio.tags.get("metadata_block_picture"))
    if encoded:
        return Picture(base64.b64decode(encoded)).data
    return None


def write_audio_metadata(path: str, values: dict, cover_path: str | None = None) -> None:
    """Escribe etiquetas y carátula en los formatos de audio compatibles."""
    audio = MutagenFile(path)
    if audio is None:
        raise ValueError(f"No se reconoce el formato de audio: {Path(path).suffix}")
    if not isinstance(audio, (MP3, WAVE, MP4, FLAC, OggFLAC, OggOpus, OggVorbis)):
        raise ValueError(f"El formato {Path(path).suffix} no admite la edición de metadatos.")
    if audio.tags is None:
        audio.add_tags()
    tags = audio.tags

    if isinstance(audio, (MP3, WAVE)):
        for field, frame_type in _ID3_FRAMES.items():
            frame_id = frame_type.__name__
            tags.delall(frame_id)
            if values.get(field):
                tags.add(frame_type(encoding=3, text=[values[field]]))
        tags.delall("COMM")
        tags.delall("USLT")
        if values.get("comment"):
            from mutagen.id3 import COMM
            tags.add(COMM(encoding=3, lang="eng", desc="", text=values["comment"]))
        if values.get("lyrics"):
            tags.add(USLT(encoding=3, lang="eng", desc="", text=values["lyrics"]))
        if cover_path is not None:
            tags.delall("APIC")
            if cover_path:
                tags.add(APIC(
                    encoding=3, mime=_image_mime(cover_path), type=3,
                    desc="Cover", data=Path(cover_path).read_bytes()))
    elif isinstance(audio, MP4):
        for field, key in _MP4_KEYS.items():
            tags.pop(key, None)
            if values.get(field):
                tags[key] = [values[field]]
        tags.pop("trkn", None)
        if values.get("track"):
            tags["trkn"] = [(int(values["track"]), 0)]
        if cover_path is not None:
            if cover_path:
                image = Path(cover_path)
                image_format = MP4Cover.FORMAT_PNG if image.suffix.lower() == ".png" else MP4Cover.FORMAT_JPEG
                tags["covr"] = [MP4Cover(image.read_bytes(), imageformat=image_format)]
            else:
                tags.pop("covr", None)
    else:
        names = {
            "title": "title", "artist": "artist", "album": "album",
            "date": "date", "genre": "genre", "composer": "composer",
            "track": "tracknumber", "comment": "comment", "lyrics": "lyrics",
        }
        for field, key in names.items():
            tags.pop(key, None)
            if values.get(field):
                tags[key] = [values[field]]
        if cover_path is not None:
            tags.pop("metadata_block_picture", None)
            if hasattr(audio, "clear_pictures") and hasattr(audio, "add_picture"):
                audio.clear_pictures()
            if cover_path:
                picture = Picture()
                picture.data = Path(cover_path).read_bytes()
                picture.type = 3
                picture.mime = _image_mime(cover_path)
                if hasattr(audio, "add_picture"):
                    audio.add_picture(picture)
                else:
                    tags["metadata_block_picture"] = [base64.b64encode(picture.write()).decode("ascii")]

    audio.save()


def _image_mime(path: str) -> str:
    suffix = Path(path).suffix.lower()
    if suffix in (".jpg", ".jpeg"):
        return "image/jpeg"
    if suffix == ".png":
        return "image/png"
    raise ValueError("La carátula debe ser una imagen PNG o JPEG.")
