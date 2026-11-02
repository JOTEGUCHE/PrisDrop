"""Ajustes: carpetas, sesión de YouTube (cookies) y estado de las herramientas."""
from PySide6.QtCore import QUrl, Qt, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QComboBox, QFileDialog, QFrame, QGridLayout, QHBoxLayout, QLabel,
                               QLineEdit, QPushButton, QScrollArea, QVBoxLayout, QWidget)

from .. import tools
from ..paths import bin_dir
from ..settings import Settings

BROWSERS = [
    ("Ninguno (sin iniciar sesión)", ""),
    ("Firefox (recomendado)", "firefox"),
    ("Brave", "brave"),
    ("Google Chrome", "chrome"),
    ("Microsoft Edge", "edge"),
    ("Opera", "opera"),
    ("Vivaldi", "vivaldi"),
    ("Chromium", "chromium"),
]


class SettingsPage(QWidget):
    folders_changed = Signal()
    repair_requested = Signal()

    def __init__(self, settings: Settings):
        super().__init__()
        self.settings = settings
        self._ytdlp_version = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll)
        content = QWidget()
        scroll.setWidget(content)
        lay = QVBoxLayout(content)
        lay.setContentsMargins(28, 22, 28, 22)
        lay.setSpacing(16)

        title = QLabel("Ajustes")
        title.setObjectName("title")
        lay.addWidget(title)

        # --- carpetas
        card = QFrame()
        card.setObjectName("card")
        g = QGridLayout(card)
        g.setContentsMargins(18, 18, 18, 18)
        g.setHorizontalSpacing(12)
        g.setVerticalSpacing(12)
        self._folder_row(g, 0, "Carpeta de videos", "video_dir")
        self._folder_row(g, 1, "Carpeta de música", "audio_dir")
        lay.addWidget(card)

        # --- sesión de YouTube
        ccard = QFrame()
        ccard.setObjectName("card")
        cl = QVBoxLayout(ccard)
        cl.setContentsMargins(18, 18, 18, 18)
        cl.setSpacing(10)
        head = QLabel("Navegador con tu sesión de YouTube")
        head.setObjectName("heading")
        info = QLabel(
            "Si al analizar o descargar aparece «Sign in to confirm you're not a bot» (YouTube cree que "
            "eres un robot), elige aquí el navegador donde tienes YouTube abierto con tu cuenta. "
            "PrisDrop usará esa sesión para pedir los videos.\n\n"
            "• Firefox funciona mejor y no hace falta cerrarlo.\n"
            "• Con Brave, Chrome o Edge ciérralos por completo antes de descargar.\n"
            "• Si haces muchísimas descargas seguidas, YouTube podría limitar esa cuenta: "
            "considera usar una cuenta secundaria.")
        info.setObjectName("muted")
        info.setWordWrap(True)
        self.combo_cookies = QComboBox()
        for label, value in BROWSERS:
            self.combo_cookies.addItem(label, value)
        i = self.combo_cookies.findData(settings.get("cookies_browser") or "")
        self.combo_cookies.setCurrentIndex(max(i, 0))
        self.combo_cookies.currentIndexChanged.connect(
            lambda _: self.settings.set("cookies_browser", self.combo_cookies.currentData()))
        crow = QHBoxLayout()
        crow.addWidget(QLabel("Navegador"))
        crow.addWidget(self.combo_cookies)
        crow.addStretch(1)
        cl.addWidget(head)
        cl.addWidget(info)
        cl.addLayout(crow)
        lay.addWidget(ccard)

        # --- herramientas
        tcard = QFrame()
        tcard.setObjectName("card")
        tl = QVBoxLayout(tcard)
        tl.setContentsMargins(18, 18, 18, 18)
        tl.setSpacing(8)
        thead = QLabel("Herramientas")
        thead.setObjectName("heading")
        self.lbl_ytdlp = QLabel()
        self.lbl_ffmpeg = QLabel()
        self.lbl_deno = QLabel()
        for lb in (self.lbl_ytdlp, self.lbl_ffmpeg, self.lbl_deno):
            lb.setObjectName("muted")
            lb.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        row = QHBoxLayout()
        b_fix = QPushButton("Reparar / reinstalar herramientas")
        b_fix.clicked.connect(self.repair_requested.emit)
        b_open = QPushButton("Abrir carpeta de herramientas")
        b_open.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(bin_dir()))))
        row.addWidget(b_fix)
        row.addWidget(b_open)
        row.addStretch(1)
        tl.addWidget(thead)
        tl.addWidget(self.lbl_ytdlp)
        tl.addWidget(self.lbl_ffmpeg)
        tl.addWidget(self.lbl_deno)
        tl.addLayout(row)
        lay.addWidget(tcard)
        lay.addStretch(1)
        self.refresh_tools()

    def _folder_row(self, grid, row, label, key) -> QLineEdit:
        ed = QLineEdit(self.settings.get(key))
        ed.setReadOnly(True)
        btn = QPushButton("Cambiar…")
        btn.clicked.connect(lambda: self._pick(ed, key))
        grid.addWidget(QLabel(label), row, 0)
        grid.addWidget(ed, row, 1)
        grid.addWidget(btn, row, 2)
        grid.setColumnStretch(1, 1)
        return ed

    def _pick(self, ed: QLineEdit, key: str):
        d = QFileDialog.getExistingDirectory(self, "Elige una carpeta", ed.text())
        if d:
            ed.setText(d)
            self.settings.set(key, d)
            self.folders_changed.emit()

    def set_version(self, version):
        """La versión la calcula un hilo en segundo plano; aquí solo se muestra."""
        self._ytdlp_version = version
        self.refresh_tools()

    def refresh_tools(self):
        yt = tools.ytdlp_path()
        ff = tools.ffmpeg_dir()
        dn = tools.deno_path()
        self.lbl_ytdlp.setText(f"yt-dlp: {self._ytdlp_version or ('no instalado' if not yt else 'comprobando…')}   ({yt or '—'})")
        self.lbl_ffmpeg.setText(f"FFmpeg: {ff or 'no instalado'}")
        self.lbl_deno.setText(f"Deno (runtime de JavaScript para YouTube): {dn or 'no instalado'}")
