"""Página de descargas: analiza el enlace, muestra opciones y gestiona la cola."""
from collections import deque
from urllib.parse import parse_qs, urlparse

from PySide6.QtCore import QUrl, Qt, Signal
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QComboBox, QFrame, QHBoxLayout, QLabel,
                               QListWidget, QListWidgetItem, QMessageBox, QProgressBar, QPushButton,
                               QScrollArea, QVBoxLayout, QWidget)

from ..library import Library, pretty_date
from ..settings import Settings
from ..workers import DownloadWorker, InfoWorker, Job
from .icons import bind_icon
from .widgets import fmt_duration, rounded_pixmap

RES_NAMES = {4320: " (8K)", 2160: " (4K)", 1440: " (2K)", 1080: " (Full HD)", 720: " (HD)"}
PLAYLIST_RESOLUTIONS = [2160, 1440, 1080, 720, 480, 360, 240]
AUDIO_FORMATS = [
    ("Original: máxima calidad, sin conversión", "best"),
    ("MP3", "mp3"),
    ("M4A (AAC)", "m4a"),
    ("OPUS", "opus"),
    ("FLAC (sin pérdida)", "flac"),
    ("WAV (sin compresión)", "wav"),
    ("OGG (Vorbis)", "vorbis"),
]


def res_label(h: int) -> str:
    return f"{h}p{RES_NAMES.get(h, '')}"


class DownloadRow(QFrame):
    """Una fila de la lista de descargas."""
    cancel_clicked = Signal(int)

    def __init__(self, job: Job, thumb: QPixmap):
        super().__init__()
        self.setObjectName("card")
        self.job = job
        self._folder = job.out_dir
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(14)
        img = QLabel()
        img.setFixedSize(96, 54)
        img.setPixmap(rounded_pixmap(thumb, 96, 54, 8, "▶" if job.kind == "video" else "♪"))
        lay.addWidget(img)

        col = QVBoxLayout()
        col.setSpacing(6)
        kind = "Video" if job.kind == "video" else "Audio"
        self.title = QLabel(f"{job.title}")
        self.title.setMinimumWidth(0)
        self.sub = QLabel(kind)
        self.sub.setObjectName("muted")
        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setTextVisible(False)
        self.status = QLabel("En cola")
        self.status.setObjectName("muted")
        self.status.setWordWrap(True)
        col.addWidget(self.title)
        col.addWidget(self.sub)
        col.addWidget(self.bar)
        col.addWidget(self.status)
        lay.addLayout(col, 1)

        self.btn_cancel = QPushButton("Cancelar")
        self.btn_cancel.clicked.connect(lambda: self.cancel_clicked.emit(job.id))
        self.btn_open = QPushButton("Abrir carpeta")
        self.btn_open.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(self._folder)))
        self.btn_open.hide()
        lay.addWidget(self.btn_cancel)
        lay.addWidget(self.btn_open)

    def set_progress(self, pct: float, text: str):
        self.bar.setValue(int(pct))
        self.status.setText(text)

    def set_done(self, ok: bool, msg: str):
        self.bar.setValue(100 if ok else self.bar.value())
        self.status.setText(("✓ " if ok else "✗ ") + msg)
        self.btn_cancel.hide()
        if ok:
            self.btn_open.show()


class DownloadPage(QWidget):
    library_changed = Signal()
    status_message = Signal(str)
    busy_changed = Signal(bool)

    def __init__(self, settings: Settings, library: Library):
        super().__init__()
        self.settings = settings
        self.library = library
        self.info = None
        self._thumb = QPixmap()
        self._source_url = ""
        self._override = False
        self._info_worker = None
        self._worker = None
        self._queue = deque()
        self._rows = {}
        self._next_id = 1
        self._build()

    # ---------------------------------------------------------------- UI
    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll)
        content = QWidget()
        scroll.setWidget(content)
        root = QVBoxLayout(content)
        root.setContentsMargins(28, 22, 28, 22)
        root.setSpacing(18)

        self.empty = QLabel("Pega el enlace de un video, canción o playlist de YouTube\n"
                            "en la barra de arriba y pulsa «Analizar».")
        self.empty.setObjectName("muted")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty.setMinimumHeight(150)
        root.addWidget(self.empty)

        # --- tarjeta de resultado
        self.card = QFrame()
        self.card.setObjectName("card")
        cl = QHBoxLayout(self.card)
        cl.setContentsMargins(18, 18, 18, 18)
        cl.setSpacing(20)
        self.thumb_lbl = QLabel()
        self.thumb_lbl.setFixedSize(320, 180)
        cl.addWidget(self.thumb_lbl, 0, Qt.AlignmentFlag.AlignTop)

        right = QVBoxLayout()
        right.setSpacing(10)
        self.lbl_title = QLabel()
        self.lbl_title.setObjectName("title")
        self.lbl_title.setWordWrap(True)
        self.lbl_meta = QLabel()
        self.lbl_meta.setObjectName("muted")
        right.addWidget(self.lbl_title)
        right.addWidget(self.lbl_meta)

        kind_row = QHBoxLayout()
        self.btn_video = QPushButton("Video")
        self.btn_audio = QPushButton("Audio (música)")
        for b in (self.btn_video, self.btn_audio):
            b.setObjectName("chip")
            b.setCheckable(True)
            kind_row.addWidget(b)
        kind_row.addStretch(1)
        grp = QButtonGroup(self)
        grp.setExclusive(True)
        grp.addButton(self.btn_video)
        grp.addButton(self.btn_audio)
        (self.btn_audio if self.settings.get("kind") == "audio" else self.btn_video).setChecked(True)
        right.addLayout(kind_row)

        # opciones de video
        self.video_opts = QWidget()
        vo = QHBoxLayout(self.video_opts)
        vo.setContentsMargins(0, 0, 0, 0)
        self.combo_res = QComboBox()
        self.combo_cont = QComboBox()
        self.combo_cont.addItem("MP4 (más compatible)", "mp4")
        self.combo_cont.addItem("MKV", "mkv")
        self._select_data(self.combo_cont, self.settings.get("container"))
        vo.addWidget(QLabel("Resolución"))
        vo.addWidget(self.combo_res)
        vo.addSpacing(10)
        vo.addWidget(QLabel("Formato"))
        vo.addWidget(self.combo_cont)
        vo.addStretch(1)
        right.addWidget(self.video_opts)

        # opciones de audio
        self.audio_opts = QWidget()
        ao = QVBoxLayout(self.audio_opts)
        ao.setContentsMargins(0, 0, 0, 0)
        ar = QHBoxLayout()
        self.combo_audio = QComboBox()
        for label, value in AUDIO_FORMATS:
            self.combo_audio.addItem(label, value)
        self._select_data(self.combo_audio, self.settings.get("audio_format"))
        ar.addWidget(QLabel("Formato de audio"))
        ar.addWidget(self.combo_audio)
        ar.addStretch(1)
        note = QLabel("Se descarga el mejor audio disponible y se guardan autor, fecha y miniatura (portada).")
        note.setObjectName("muted")
        note.setWordWrap(True)
        ao.addLayout(ar)
        ao.addWidget(note)
        right.addWidget(self.audio_opts)

        self.chk_list = QCheckBox("Este enlace pertenece a una playlist: descargar la lista completa")
        self.chk_list.toggled.connect(lambda c: self.analyze(self._source_url, c))
        self.chk_list.hide()
        right.addWidget(self.chk_list)

        self.lbl_dest = QLabel()
        self.lbl_dest.setObjectName("muted")
        right.addWidget(self.lbl_dest)

        self.btn_download = QPushButton("Descargar")
        bind_icon(self.btn_download, "action_download", "download")
        self.btn_download.setObjectName("primary")
        self.btn_download.clicked.connect(self.start_download)
        right.addWidget(self.btn_download, 0, Qt.AlignmentFlag.AlignLeft)
        right.addStretch(1)
        cl.addLayout(right, 1)
        root.addWidget(self.card)
        self.card.hide()

        # --- elementos de playlist
        self.playlist_box = QFrame()
        self.playlist_box.setObjectName("card")
        pl = QVBoxLayout(self.playlist_box)
        pl.setContentsMargins(18, 14, 18, 14)
        head = QHBoxLayout()
        self.lbl_pl = QLabel("Elementos de la playlist")
        self.lbl_pl.setObjectName("heading")
        b_all = QPushButton("Todos")
        b_none = QPushButton("Ninguno")
        b_all.clicked.connect(lambda: self._set_all(Qt.CheckState.Checked))
        b_none.clicked.connect(lambda: self._set_all(Qt.CheckState.Unchecked))
        head.addWidget(self.lbl_pl)
        head.addStretch(1)
        head.addWidget(b_all)
        head.addWidget(b_none)
        pl.addLayout(head)
        self.pl_list = QListWidget()
        self.pl_list.setObjectName("plain")
        self.pl_list.setMinimumHeight(200)
        self.pl_list.setMaximumHeight(320)
        pl.addWidget(self.pl_list)
        root.addWidget(self.playlist_box)
        self.playlist_box.hide()

        # --- lista de descargas
        self.dl_heading = QLabel("Descargas")
        self.dl_heading.setObjectName("heading")
        self.dl_heading.hide()
        root.addWidget(self.dl_heading)
        self.rows_layout = QVBoxLayout()
        self.rows_layout.setSpacing(10)
        root.addLayout(self.rows_layout)
        root.addStretch(1)

        self.btn_video.toggled.connect(self._on_kind)
        self._on_kind()

    @staticmethod
    def _select_data(combo: QComboBox, value):
        i = combo.findData(value)
        if i >= 0:
            combo.setCurrentIndex(i)

    def _on_kind(self, *_):
        video = self.btn_video.isChecked()
        self.video_opts.setVisible(video)
        self.audio_opts.setVisible(not video)
        folder = self.settings.get("video_dir" if video else "audio_dir")
        self.lbl_dest.setText(f"Se guardará en: {folder}")

    def refresh_destination(self):
        self._on_kind()

    def _set_all(self, state):
        for i in range(self.pl_list.count()):
            self.pl_list.item(i).setCheckState(state)

    # ------------------------------------------------------------ análisis
    def analyze(self, url: str, playlist_override: bool = False):
        url = url.strip()
        if not url.lower().startswith(("http://", "https://")):
            self.status_message.emit("Pega un enlace válido que empiece con http:// o https://")
            return
        if self._info_worker is not None and self._info_worker.isRunning():
            return
        parsed = urlparse(url)
        qs = parse_qs(parsed.query)
        pure_playlist = "/playlist" in parsed.path or (
            "list" in qs and "v" not in qs and "youtu.be" not in parsed.netloc)
        self._source_url = url
        self._override = playlist_override
        target = url
        if playlist_override and "list" in qs:
            target = f"https://www.youtube.com/playlist?list={qs['list'][0]}"
        self._has_list_hint = ("list" in qs) and not pure_playlist
        self.card.hide()
        self.playlist_box.hide()
        self.empty.setText("Analizando enlace…")
        self.empty.show()
        w = InfoWorker(target, pure_playlist or playlist_override, self.settings.get("cookies_browser") or "")
        w.done.connect(self._on_info)
        w.failed.connect(self._on_info_failed)
        self._info_worker = w
        self.busy_changed.emit(True)
        w.start()

    def _on_info_failed(self, msg: str):
        self.busy_changed.emit(False)
        self.empty.setText("No se pudo analizar el enlace.")
        self.empty.show()
        self.status_message.emit("No se pudo analizar el enlace.")
        QMessageBox.warning(self, "PrisDrop", f"No se pudo analizar el enlace:\n\n{msg}")

    def _on_info(self, info: dict):
        self.busy_changed.emit(False)
        self.info = info
        self.empty.hide()
        self.card.show()
        self._thumb = QPixmap()
        if info["thumb"]:
            self._thumb.loadFromData(info["thumb"])
        self.thumb_lbl.setPixmap(rounded_pixmap(self._thumb, 320, 180, 14, "▶"))
        self.lbl_title.setText(info["title"])
        parts = [info["uploader"], pretty_date(info["upload_date"])]
        if info["is_playlist"]:
            parts.append(f"{len(info['entries'])} elementos")
        elif info["duration"]:
            parts.append(fmt_duration(info["duration"]))
        self.lbl_meta.setText("  ·  ".join(p for p in parts if p))

        self.combo_res.clear()
        if info["is_playlist"]:
            self.combo_res.addItem("Mejor disponible", None)
            for h in PLAYLIST_RESOLUTIONS:
                self.combo_res.addItem(res_label(h), h)
        elif info["heights"]:
            for h in info["heights"]:
                self.combo_res.addItem(res_label(h), h)
        else:
            self.combo_res.addItem("Mejor disponible", None)

        self.playlist_box.setVisible(info["is_playlist"])
        self.pl_list.clear()
        for e in info["entries"]:
            dur = f"  ({fmt_duration(e['duration'])})" if e["duration"] else ""
            it = QListWidgetItem(f"{e['index']:02d}  {e['title']}{dur}")
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            it.setCheckState(Qt.CheckState.Checked)
            it.setData(Qt.ItemDataRole.UserRole, e["index"])
            self.pl_list.addItem(it)
        self.lbl_pl.setText(f"Elementos de la playlist ({len(info['entries'])})")

        self.chk_list.blockSignals(True)
        self.chk_list.setChecked(self._override)
        self.chk_list.blockSignals(False)
        self.chk_list.setVisible(self._has_list_hint or self._override)
        self._on_kind()

    # ------------------------------------------------------------- descarga
    def start_download(self):
        if not self.info:
            return
        video = self.btn_video.isChecked()
        info = self.info
        items = ""
        if info["is_playlist"]:
            picked = [self.pl_list.item(i).data(Qt.ItemDataRole.UserRole)
                      for i in range(self.pl_list.count())
                      if self.pl_list.item(i).checkState() == Qt.CheckState.Checked]
            if not picked:
                QMessageBox.information(self, "PrisDrop", "Marca al menos un elemento de la playlist.")
                return
            if len(picked) != self.pl_list.count():
                items = ",".join(str(i) for i in picked)

        self.settings.set("kind", "video" if video else "audio")
        self.settings.set("container", self.combo_cont.currentData())
        self.settings.set("audio_format", self.combo_audio.currentData())

        job = Job(
            id=self._next_id, url=info["url"], title=info["title"],
            kind="video" if video else "audio",
            out_dir=self.settings.get("video_dir" if video else "audio_dir"),
            height=self.combo_res.currentData(), container=self.combo_cont.currentData(),
            audio_format=self.combo_audio.currentData(),
            is_playlist=info["is_playlist"], playlist_items=items,
            cookies_browser=self.settings.get("cookies_browser") or "")
        self._next_id += 1

        row = DownloadRow(job, self._thumb)
        row.cancel_clicked.connect(self.cancel_job)
        self.rows_layout.insertWidget(0, row)
        self._rows[job.id] = row
        self.dl_heading.show()
        self._queue.append(job)
        self.status_message.emit("Descarga añadida a la cola.")
        self._pump()

    def _pump(self):
        if self._worker is not None or not self._queue:
            return
        job = self._queue.popleft()
        w = DownloadWorker(job)
        w.progress.connect(lambda jid, pct, text: self._rows[jid].set_progress(pct, text))
        w.item_done.connect(lambda _jid, meta: self.library.register(meta))
        w.finished_job.connect(self._on_job_finished)
        w.finished.connect(self._on_thread_finished)
        self._worker = w
        self._rows[job.id].set_progress(0, "Iniciando…")
        w.start()

    def _on_job_finished(self, jid: int, ok: bool, msg: str):
        self._rows[jid].set_done(ok, msg)
        self.status_message.emit(msg)
        if ok:
            self.library_changed.emit()

    def _on_thread_finished(self):
        self._worker = None
        self._pump()

    def cancel_job(self, jid: int):
        if self._worker is not None and self._worker.job.id == jid:
            self._worker.cancel()
            return
        for job in list(self._queue):
            if job.id == jid:
                self._queue.remove(job)
                self._rows[jid].set_done(False, "Cancelado")

    def active_count(self) -> int:
        return len(self._queue) + (1 if self._worker is not None else 0)

    def shutdown(self):
        self._queue.clear()
        if self._worker is not None:
            self._worker.cancel()
            self._worker.wait(5000)
        if self._info_worker is not None and self._info_worker.isRunning():
            self._info_worker.wait(5000)
