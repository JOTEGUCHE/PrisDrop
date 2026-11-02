"""Gestión de yt-dlp y FFmpeg: detección, versiones, instalación y actualización.

yt-dlp se usa como ejecutable independiente (yt-dlp.exe en Windows) guardado en la
carpeta de datos de la app. Así se puede actualizar descargando el binario oficial
más reciente de GitHub, incluso cuando PrisDrop esté empaquetado como .exe.
"""
import hashlib
import json
import os
import platform
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import zipfile
from pathlib import Path
from typing import Callable, Optional

from .paths import bin_dir

IS_WIN = sys.platform == "win32"
IS_MAC = sys.platform == "darwin"

UA = {"User-Agent": "PrisDrop/1.0"}
YTDLP_ASSET = "yt-dlp.exe" if IS_WIN else ("yt-dlp_macos" if IS_MAC else "yt-dlp_linux")
YTDLP_LOCAL_NAME = "yt-dlp.exe" if IS_WIN else "yt-dlp"
FF_EXT = ".exe" if IS_WIN else ""
RELEASES_API = "https://api.github.com/repos/yt-dlp/yt-dlp/releases/latest"
YTDLP_URL = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/"
FFMPEG_URL = "https://github.com/yt-dlp/FFmpeg-Builds/releases/download/latest/"

ProgressCb = Callable[[int, int], None]

_MACHINE = platform.machine().lower()
_ARM = _MACHINE in ("arm64", "aarch64")
if IS_WIN:
    DENO_ASSET = "deno-x86_64-pc-windows-msvc.zip"
elif IS_MAC:
    DENO_ASSET = "deno-aarch64-apple-darwin.zip" if _ARM else "deno-x86_64-apple-darwin.zip"
else:
    DENO_ASSET = "deno-aarch64-unknown-linux-gnu.zip" if _ARM else "deno-x86_64-unknown-linux-gnu.zip"
DENO_URL = "https://github.com/denoland/deno/releases/latest/download/"


def popen_flags() -> dict:
    """Evita que aparezca una ventana de consola negra en Windows."""
    return {"creationflags": subprocess.CREATE_NO_WINDOW} if IS_WIN else {}


# ----------------------------------------------------------------- detección
def ytdlp_path() -> Optional[str]:
    p = bin_dir() / YTDLP_LOCAL_NAME
    return str(p) if p.exists() else None


def ffmpeg_dir() -> Optional[str]:
    local = bin_dir()
    if (local / f"ffmpeg{FF_EXT}").exists() and (local / f"ffprobe{FF_EXT}").exists():
        return str(local)
    found = shutil.which("ffmpeg")
    if found and shutil.which("ffprobe"):
        return str(Path(found).parent)
    return None


def deno_path() -> Optional[str]:
    """Deno: runtime de JavaScript que yt-dlp usa para resolver los retos de YouTube."""
    local = bin_dir() / f"deno{FF_EXT}"
    if local.exists():
        return str(local)
    return shutil.which("deno")


# ------------------------------------------------------------------ versiones
def local_version() -> Optional[str]:
    exe = ytdlp_path()
    if not exe:
        return None
    try:
        out = subprocess.run([exe, "--version"], capture_output=True, text=True,
                             timeout=60, **popen_flags())
        return out.stdout.strip() or None
    except Exception:
        return None


def latest_version() -> str:
    req = urllib.request.Request(RELEASES_API, headers={**UA, "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))["tag_name"].strip()


def _parse(version: str) -> tuple:
    try:
        return tuple(int(p) for p in version.split("."))
    except ValueError:
        return (0,)


def is_up_to_date(local: str, latest: str) -> bool:
    """True si la versión local es igual o más nueva (p. ej. un nightly) que la última."""
    return _parse(local) >= _parse(latest)


# ----------------------------------------------------------------- descargas
def download_file(url: str, dest: Path, progress: Optional[ProgressCb] = None) -> None:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r, open(dest, "wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        done = 0
        while True:
            chunk = r.read(256 * 1024)
            if not chunk:
                break
            f.write(chunk)
            done += len(chunk)
            if progress:
                progress(done, total)


def _verify_sha256(file: Path, asset: str) -> None:
    try:
        req = urllib.request.Request(YTDLP_URL + "SHA2-256SUMS", headers=UA)
        with urllib.request.urlopen(req, timeout=20) as r:
            sums = r.read().decode("utf-8", "replace")
    except Exception:
        return  # sin lista de sumas no se puede verificar; se continúa
    expected = None
    for line in sums.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[1].lstrip("*") == asset:
            expected = parts[0].lower()
    if not expected:
        return
    h = hashlib.sha256()
    with open(file, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    if h.hexdigest() != expected:
        raise RuntimeError("La descarga de yt-dlp está corrupta (la suma SHA-256 no coincide).")


def install_ytdlp(progress: Optional[ProgressCb] = None) -> str:
    """Descarga la última versión oficial de yt-dlp y reemplaza la actual."""
    dest = bin_dir() / YTDLP_LOCAL_NAME
    tmp = bin_dir() / (YTDLP_LOCAL_NAME + ".new")
    try:
        download_file(YTDLP_URL + YTDLP_ASSET, tmp, progress)
        _verify_sha256(tmp, YTDLP_ASSET)
        if not IS_WIN:
            tmp.chmod(tmp.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        os.replace(tmp, dest)
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass
    return local_version() or ""


def _extract_member(src, name: str) -> None:
    dest = bin_dir() / name
    tmp = dest.with_name(dest.name + ".new")
    with src, open(tmp, "wb") as out:
        shutil.copyfileobj(src, out)
    if not IS_WIN:
        tmp.chmod(0o755)
    os.replace(tmp, dest)


def install_ffmpeg(progress: Optional[ProgressCb] = None) -> None:
    """Descarga FFmpeg + ffprobe (builds recomendadas por yt-dlp)."""
    if IS_MAC:
        raise RuntimeError("En macOS instala FFmpeg con Homebrew:  brew install ffmpeg")
    archive = "ffmpeg-master-latest-win64-gpl.zip" if IS_WIN else "ffmpeg-master-latest-linux64-gpl.tar.xz"
    wanted = {f"ffmpeg{FF_EXT}", f"ffprobe{FF_EXT}"}
    found = set()
    with tempfile.TemporaryDirectory() as tmp:
        arc = Path(tmp) / archive
        download_file(FFMPEG_URL + archive, arc, progress)
        if IS_WIN:
            with zipfile.ZipFile(arc) as z:
                for info in z.infolist():
                    name = Path(info.filename).name
                    if name in wanted and "/bin/" in info.filename.replace("\\", "/"):
                        _extract_member(z.open(info), name)
                        found.add(name)
        else:
            with tarfile.open(arc) as t:
                for m in t.getmembers():
                    name = Path(m.name).name
                    if m.isfile() and name in wanted and "/bin/" in m.name:
                        _extract_member(t.extractfile(m), name)
                        found.add(name)
    if found != wanted:
        raise RuntimeError("No se encontró ffmpeg/ffprobe dentro del paquete descargado.")


def install_deno(progress: Optional[ProgressCb] = None) -> None:
    """Descarga Deno (un solo ejecutable) a la carpeta de herramientas."""
    name = f"deno{FF_EXT}"
    with tempfile.TemporaryDirectory() as tmp:
        arc = Path(tmp) / DENO_ASSET
        download_file(DENO_URL + DENO_ASSET, arc, progress)
        with zipfile.ZipFile(arc) as z:
            for info in z.infolist():
                if Path(info.filename).name == name:
                    _extract_member(z.open(info), name)
                    return
    raise RuntimeError("No se encontró Deno dentro del paquete descargado.")
