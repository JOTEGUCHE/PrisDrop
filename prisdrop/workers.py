"""Hilos de trabajo (QThread) para no congelar la interfaz."""
import json
import os
import re
import subprocess
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QThread, Signal

from . import tools


@dataclass
class Job:
    id: int
    url: str
    title: str
    kind: str                       # "video" | "audio"
    out_dir: str
    height: Optional[int] = None    # None = mejor disponible
    container: str = "mp4"          # mp4 | mkv
    audio_format: str = "mp3"       # best | mp3 | m4a | opus | flac | wav | vorbis
    is_playlist: bool = False
    playlist_items: str = ""        # "1,3,5"; vacío = toda la lista
    cookies_browser: str = ""       # "" | firefox | brave | chrome | edge ...


def _pct(done: int, total: int) -> int:
    return int(done * 100 / total) if total else -1


def friendly_error(raw: str) -> str:
    """Traduce los errores más comunes de yt-dlp a algo entendible."""
    low = raw.lower()
    if "not a bot" in low or "sign in to confirm" in low:
        return ("YouTube cree que la app es un robot y pide iniciar sesión.\n\n"
                "Solución: abre Ajustes → «Navegador con tu sesión de YouTube», elige el navegador "
                "donde tienes YouTube con tu cuenta (Firefox es el más fiable; con Brave/Chrome/Edge "
                "ciérralo antes) y vuelve a intentarlo.\n\n"
                "Evita lanzar muchas descargas seguidas: espera unos segundos entre una y otra.")
    if "cookie" in low and any(k in low for k in ("could not copy", "database", "decrypt", "permission", "locked")):
        return ("No se pudieron leer las cookies del navegador elegido.\n\n"
                "Cierra ese navegador por completo e inténtalo otra vez, o elige Firefox en Ajustes.\n\n"
                f"Detalle técnico: {raw}")
    return raw


def common_args() -> list:
    """Opciones comunes: runtime de JavaScript (Deno) para los retos de YouTube."""
    args = []
    deno = tools.deno_path()
    if deno:
        args += ["--js-runtimes", f"deno:{deno}"]
    return args


# --------------------------------------------------------------- herramientas
class SetupWorker(QThread):
    """Descarga yt-dlp y FFmpeg si faltan (o los reinstala si force=True)."""
    progress = Signal(str, int)     # mensaje, % (-1 = indeterminado)
    done = Signal()
    failed = Signal(str)

    def __init__(self, force: bool = False):
        super().__init__()
        self.force = force

    def run(self):
        try:
            if self.force or not tools.ytdlp_path():
                msg = "Descargando yt-dlp…"
                self.progress.emit(msg, 0)
                tools.install_ytdlp(lambda d, t: self.progress.emit(msg, _pct(d, t)))
            if self.force or not tools.ffmpeg_dir():
                msg = "Descargando FFmpeg (solo la primera vez, puede tardar)…"
                self.progress.emit(msg, 0)
                tools.install_ffmpeg(lambda d, t: self.progress.emit(msg, _pct(d, t)))
            if self.force or not tools.deno_path():
                msg = "Descargando Deno (necesario para YouTube)…"
                self.progress.emit(msg, 0)
                try:
                    tools.install_deno(lambda d, t: self.progress.emit(msg, _pct(d, t)))
                except Exception:  # noqa: BLE001  (no es fatal: se intenta seguir sin Deno)
                    pass
            self.done.emit()
        except Exception as e:  # noqa: BLE001
            self.failed.emit(str(e))


class VersionWorker(QThread):
    result = Signal(object, object, str)    # local, latest, error

    def run(self):
        local = tools.local_version()
        latest, err = None, ""
        try:
            latest = tools.latest_version()
        except Exception as e:  # noqa: BLE001
            err = str(e)
        self.result.emit(local, latest, err)


class UpdateWorker(QThread):
    progress = Signal(int)
    done = Signal(str)
    failed = Signal(str)

    def run(self):
        try:
            v = tools.install_ytdlp(lambda d, t: self.progress.emit(max(_pct(d, t), 0)))
            self.done.emit(v)
        except PermissionError:
            self.failed.emit("No se pudo reemplazar yt-dlp porque está en uso. Cierra otras descargas e inténtalo de nuevo.")
        except Exception as e:  # noqa: BLE001
            self.failed.emit(str(e))


# ------------------------------------------------------------------- análisis
class InfoWorker(QThread):
    done = Signal(dict)
    failed = Signal(str)

    def __init__(self, url: str, playlist: bool, cookies_browser: str = ""):
        super().__init__()
        self.url = url
        self.playlist = playlist
        self.cookies_browser = cookies_browser

    def run(self):
        exe = tools.ytdlp_path()
        if not exe:
            self.failed.emit("yt-dlp todavía no está instalado.")
            return
        cmd = [exe, "-J", "--no-warnings", "--encoding", "utf-8"] + common_args()
        if self.cookies_browser:
            cmd += ["--cookies-from-browser", self.cookies_browser]
        cmd += ["--flat-playlist"] if self.playlist else ["--no-playlist"]
        cmd.append(self.url)
        try:
            p = subprocess.run(cmd, capture_output=True, timeout=180, **tools.popen_flags())
        except subprocess.TimeoutExpired:
            self.failed.emit("YouTube tardó demasiado en responder. Inténtalo otra vez.")
            return
        except OSError as e:
            self.failed.emit(f"No se pudo ejecutar yt-dlp: {e}")
            return
        if p.returncode != 0:
            lines = p.stderr.decode("utf-8", "replace").strip().splitlines()
            self.failed.emit(friendly_error(lines[-1] if lines else "No se pudo analizar el enlace."))
            return
        try:
            data = json.loads(p.stdout.decode("utf-8"))
            self.done.emit(self._summarize(data))
        except Exception as e:  # noqa: BLE001
            self.failed.emit(f"Respuesta inesperada de yt-dlp: {e}")

    def _summarize(self, d: dict) -> dict:
        is_pl = d.get("_type") == "playlist"
        thumb_url = d.get("thumbnail")
        entries = []
        heights = []
        if is_pl:
            raw = [e for e in (d.get("entries") or []) if e]
            for i, e in enumerate(raw, 1):
                entries.append({"index": i,
                                "title": e.get("title") or e.get("id") or f"Elemento {i}",
                                "duration": e.get("duration") or 0})
            if not thumb_url:
                for e in raw:
                    th = e.get("thumbnails") or []
                    if th:
                        thumb_url = th[-1].get("url")
                        break
        else:
            heights = sorted({f["height"] for f in d.get("formats") or []
                              if f.get("height") and f.get("vcodec") not in (None, "none")},
                             reverse=True)
        thumb = b""
        if thumb_url:
            try:
                req = urllib.request.Request(thumb_url, headers=tools.UA)
                with urllib.request.urlopen(req, timeout=15) as r:
                    thumb = r.read()
            except Exception:  # noqa: BLE001
                pass
        return {
            "is_playlist": is_pl,
            "title": d.get("title") or "Sin título",
            "uploader": d.get("uploader") or d.get("channel") or d.get("playlist_uploader") or "",
            "upload_date": d.get("upload_date") or "",
            "duration": d.get("duration") or 0,
            "thumb": thumb,
            "heights": heights,
            "entries": entries,
            "url": d.get("webpage_url") or self.url,
        }


# ------------------------------------------------------------------ descarga
def build_command(job: Job, exe: str, ff_dir: str) -> list:
    cmd = [
        exe, "--newline", "--color", "no_color", "--no-quiet", "--no-simulate",
        "--encoding", "utf-8", "--ffmpeg-location", ff_dir,
        "--windows-filenames", "--trim-filenames", "120", "--no-mtime",
        "--retries", "5", "--fragment-retries", "5", "-N", "4",
        "--embed-metadata",                       # título, autor (artist) y fecha
        "--write-thumbnail", "--convert-thumbnails", "jpg",   # la miniatura se conserva como .jpg
        "--progress-template",
        "download:DTPROG|%(progress._percent_str)s|%(progress._speed_str)s|%(progress._eta_str)s",
        "--print", "after_move:DTJSON|%(.{id,title,uploader,upload_date,duration,filepath})j",
    ]
    cmd += common_args()
    if job.cookies_browser:
        cmd += ["--cookies-from-browser", job.cookies_browser]
    if job.is_playlist:
        cmd += ["--sleep-requests", "1", "--sleep-interval", "2", "--max-sleep-interval", "5"]
        cmd += ["--yes-playlist", "-o",
                os.path.join(job.out_dir, "%(playlist_title)s",
                             "%(playlist_index)02d - %(title)s.%(ext)s")]
        if job.playlist_items:
            cmd += ["--playlist-items", job.playlist_items]
    else:
        cmd += ["--no-playlist", "-o", os.path.join(job.out_dir, "%(title)s.%(ext)s")]

    if job.kind == "audio":
        cmd += ["-f", "bestaudio/best", "-x", "--audio-format", job.audio_format,
                "--audio-quality", "0"]
        if job.audio_format != "wav":             # WAV no admite portada incrustada
            cmd.append("--embed-thumbnail")
    else:
        if job.height:
            sel = f"bv*[height<={job.height}]+ba/b[height<={job.height}]"
        else:
            sel = "bv*+ba/b"
        cmd += ["-f", sel, "--merge-output-format", job.container, "--embed-thumbnail"]
        cmd += ["-S", "res,vcodec:h264,acodec:aac"] if job.container == "mp4" else ["-S", "res"]
    cmd.append(job.url)
    return cmd


class DownloadWorker(QThread):
    progress = Signal(int, float, str)          # job_id, % global, texto
    item_done = Signal(int, dict)               # job_id, metadatos del archivo
    finished_job = Signal(int, bool, str)       # job_id, ok, mensaje

    def __init__(self, job: Job):
        super().__init__()
        self.job = job
        self._proc: Optional[subprocess.Popen] = None
        self._cancel = False

    def cancel(self):
        self._cancel = True
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()

    def run(self):
        job = self.job
        exe, ff = tools.ytdlp_path(), tools.ffmpeg_dir()
        if not exe or not ff:
            self.finished_job.emit(job.id, False, "Faltan yt-dlp o FFmpeg. Usa Ajustes → Reparar herramientas.")
            return
        Path(job.out_dir).mkdir(parents=True, exist_ok=True)
        try:
            self._proc = subprocess.Popen(
                build_command(job, exe, ff), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace", bufsize=1, **tools.popen_flags())
        except OSError as e:
            self.finished_job.emit(job.id, False, f"No se pudo iniciar yt-dlp: {e}")
            return

        cur, total, stage = 1, 1, 0
        streams = 2 if job.kind == "video" else 1     # video+audio se bajan por separado
        items, last_error = 0, ""
        for raw in self._proc.stdout:
            line = raw.strip()
            if line.startswith("DTPROG|"):
                parts = line.split("|")
                m = re.search(r"[\d.]+", parts[1]) if len(parts) > 1 else None
                pct = float(m.group()) if m else 0.0
                speed = parts[2].strip() if len(parts) > 2 else ""
                eta = parts[3].strip() if len(parts) > 3 else ""
                st = max(stage, 1)
                overall = ((cur - 1) + ((st - 1) + pct / 100) / streams) / total * 100
                text = f"{pct:.0f}%  ·  {speed}  ·  quedan {eta}"
                if total > 1:
                    text = f"Elemento {cur} de {total}  ·  " + text
                self.progress.emit(job.id, min(overall, 99.0), text)
            elif line.startswith("[download] Destination:"):
                stage += 1
            elif line.startswith("[download] Downloading item"):
                m = re.search(r"item (\d+) of (\d+)", line)
                if m:
                    cur, total, stage = int(m.group(1)), int(m.group(2)), 0
            elif line.startswith("DTJSON|"):
                try:
                    meta = json.loads(line[len("DTJSON|"):])
                    items += 1
                    self.item_done.emit(job.id, meta)
                except json.JSONDecodeError:
                    pass
            elif line.startswith(("[ExtractAudio]", "[Merger]", "[VideoConvertor]", "[EmbedThumbnail]",
                                  "[Metadata]", "[ThumbnailsConvertor]", "[FixupM4a]")):
                self.progress.emit(job.id, 99.0, "Procesando: audio/video, metadatos y miniatura…")
            elif line.startswith("ERROR:"):
                last_error = line
        rc = self._proc.wait()
        if self._cancel:
            self.finished_job.emit(job.id, False, "Cancelado")
        elif items > 0 or rc == 0:
            msg = f"Completado ({items} archivo(s))" if rc == 0 else f"Completado con errores ({items} archivo(s))"
            self.finished_job.emit(job.id, True, msg)
        else:
            self.finished_job.emit(job.id, False, friendly_error(last_error or "La descarga falló."))


class LibraryScanWorker(QThread):
    """Escanea las carpetas de la biblioteca sin bloquear la interfaz."""
    done = Signal(list)

    def __init__(self, library, folders):
        super().__init__()
        self.library = library
        self.folders = list(folders)

    def run(self):
        try:
            self.done.emit(self.library.scan(self.folders))
        except Exception:  # noqa: BLE001
            self.done.emit([])
