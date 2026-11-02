"""Sección «Páginas»: accesos directos a sitios web que se abren dentro de la app."""
import hashlib
from pathlib import Path
from urllib.parse import urlparse

from PySide6.QtCore import QRectF, QSize, Qt, QTimer, QUrl
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QInputDialog, QLabel, QListWidget, QListWidgetItem,
                               QMenu, QPushButton, QStackedWidget, QVBoxLayout, QWidget)

from ..paths import data_dir
from ..settings import Settings
from .icons import bind_icon

try:
    from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile, QWebEngineSettings
    from PySide6.QtWebEngineWidgets import QWebEngineView
    HAS_WEB = True
except Exception:  # noqa: BLE001
    HAS_WEB = False

COLORS = ["#c62828", "#ad1457", "#6a1b9a", "#283593", "#1565c0",
          "#00838f", "#2e7d32", "#ef6c00", "#4e342e", "#37474f"]
SECOND_LEVEL = {"co", "com", "org", "net", "gob", "edu"}


def normalize_url(raw: str) -> str:
    raw = (raw or "").strip()
    if not raw:
        return ""
    return raw if "://" in raw else "https://" + raw


def host_of(url: str) -> str:
    host = urlparse(url).netloc.lower()
    return host[4:] if host.startswith("www.") else host


def default_name(url: str) -> str:
    parts = host_of(url).split(".")
    if len(parts) >= 3 and parts[-2] in SECOND_LEVEL:
        parts = parts[:-2]
    elif len(parts) >= 2:
        parts = parts[:-1]
    base = parts[-1] if parts else host_of(url)
    return base[:1].upper() + base[1:]


def favicon_path(url: str) -> Path:
    d = data_dir() / "icons"
    d.mkdir(parents=True, exist_ok=True)
    return d / (hashlib.md5(host_of(url).encode()).hexdigest() + ".png")


def tile_icon(name: str, url: str) -> QIcon:
    size = 96
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    path = QPainterPath()
    path.addRoundedRect(QRectF(0, 0, size, size), 22, 22)
    fav = QPixmap(str(favicon_path(url)))
    if not fav.isNull():
        p.fillPath(path, QColor("#272727"))
        fav = fav.scaled(52, 52, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        p.drawPixmap((size - fav.width()) // 2, (size - fav.height()) // 2, fav)
    else:
        idx = int(hashlib.md5(host_of(url).encode()).hexdigest(), 16) % len(COLORS)
        p.fillPath(path, QColor(COLORS[idx]))
        f = QFont("Segoe UI")
        f.setPixelSize(46)
        f.setBold(True)
        p.setFont(f)
        p.setPen(QColor("white"))
        p.drawText(QRectF(0, 0, size, size), Qt.AlignmentFlag.AlignCenter, (name[:1] or "?").upper())
    p.end()
    return QIcon(pm)


if HAS_WEB:
    class _WebPage(QWebEnginePage):
        """Los enlaces que abren «nueva pestaña» se cargan en la misma vista."""

        def createWindow(self, _type):
            tmp = QWebEnginePage(self.profile(), self)

            def redirect(url):
                self.setUrl(url)
                QTimer.singleShot(0, tmp.deleteLater)

            tmp.urlChanged.connect(redirect)
            return tmp


class PagesPage(QWidget):
    def __init__(self, settings: Settings):
        super().__init__()
        self.settings = settings
        self.page = None
        self._current_url = ""

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.stack = QStackedWidget()
        outer.addWidget(self.stack)
        self._build_home()
        self._build_web()
        self.reload_tiles()

    # ------------------------------------------------------------- inicio
    def _build_home(self):
        home = QWidget()
        hl = QVBoxLayout(home)
        hl.setContentsMargins(28, 22, 28, 12)
        hl.setSpacing(12)
        title = QLabel("Páginas")
        title.setObjectName("title")
        hint = QLabel("Pega el enlace de una página web en la barra de arriba y pulsa «Agregar a páginas». "
                      "Haz clic en un cuadro para usarla dentro de PrisDrop. "
                      "Clic derecho: cambiar nombre o quitar.")
        hint.setObjectName("muted")
        hint.setWordWrap(True)
        hl.addWidget(title)
        hl.addWidget(hint)
        self.tiles = QListWidget()
        self.tiles.setObjectName("grid")
        self.tiles.setViewMode(QListWidget.ViewMode.IconMode)
        self.tiles.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.tiles.setMovement(QListWidget.Movement.Static)
        self.tiles.setIconSize(QSize(96, 96))
        self.tiles.setGridSize(QSize(150, 150))
        self.tiles.setSpacing(8)
        self.tiles.setWordWrap(True)
        self.tiles.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tiles.customContextMenuRequested.connect(self._menu)
        self.tiles.itemClicked.connect(self._tile_clicked)
        hl.addWidget(self.tiles, 1)
        self.empty = QLabel("Todavía no agregaste ninguna página.")
        self.empty.setObjectName("muted")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hl.addWidget(self.empty)
        self.stack.addWidget(home)

    def _build_web(self):
        web = QFrame()
        web.setObjectName("web")
        self._wl = QVBoxLayout(web)
        self._wl.setContentsMargins(12, 10, 12, 10)
        self._wl.setSpacing(8)
        bar = QHBoxLayout()
        self.btn_home = QPushButton("Páginas")
        bind_icon(self.btn_home, "nav_pages", "pages")
        self.btn_home.clicked.connect(self.go_home)
        bar.addWidget(self.btn_home)
        self.lbl_title = QLabel()
        self.lbl_title.setObjectName("muted")
        if HAS_WEB:
            self.btn_back = QPushButton()
            self.btn_fwd = QPushButton()
            self.btn_reload = QPushButton()
            for b, slot, glyph in ((self.btn_back, "action_previous", "previous"),
                                   (self.btn_fwd, "action_next", "next"),
                                   (self.btn_reload, "action_refresh", "refresh")):
                b.setObjectName("ctl")
                bind_icon(b, slot, glyph)
                bar.addWidget(b)
        bar.addSpacing(8)
        bar.addWidget(self.lbl_title, 1)
        self._wl.addLayout(bar)

        if HAS_WEB:
            self.profile = QWebEngineProfile("PrisDrop", self)      # perfil persistente (conserva sesiones)
            self.page = _WebPage(self.profile, self)
            st = self.page.settings()
            st.setAttribute(QWebEngineSettings.WebAttribute.FullScreenSupportEnabled, True)
            st.setAttribute(QWebEngineSettings.WebAttribute.PlaybackRequiresUserGesture, False)
            self.view = QWebEngineView()
            self.view.setPage(self.page)
            self._wl.addWidget(self.view, 1)
            self.btn_back.clicked.connect(self.view.back)
            self.btn_fwd.clicked.connect(self.view.forward)
            self.btn_reload.clicked.connect(self.view.reload)
            self.view.titleChanged.connect(self.lbl_title.setText)
            self.view.iconChanged.connect(self._on_icon)
            self.page.fullScreenRequested.connect(self._on_fullscreen)
        else:
            msg = QLabel("Falta el componente QtWebEngine.\nInstala PySide6 completo:  pip install PySide6")
            msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._wl.addWidget(msg, 1)
        self.stack.addWidget(web)

    # -------------------------------------------------------------- datos
    def _pages(self) -> list:
        return list(self.settings.get("pages") or [])

    def reload_tiles(self):
        self.tiles.clear()
        pages = self._pages()
        for p in pages:
            it = QListWidgetItem(tile_icon(p["name"], p["url"]), p["name"])
            it.setToolTip(p["url"])
            it.setTextAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
            self.tiles.addItem(it)
        self.empty.setVisible(not pages)
        self.tiles.setVisible(bool(pages))

    def add_page(self, raw: str) -> str:
        url = normalize_url(raw)
        if not url:
            return "Pega primero el enlace de la página."
        pages = self._pages()
        if any(p["url"].rstrip("/") == url.rstrip("/") for p in pages):
            return "Esa página ya está en tu lista."
        name = default_name(url)
        pages.append({"name": name, "url": url})
        self.settings.set("pages", pages)
        self.reload_tiles()
        return f"«{name}» agregada a Páginas."

    # ----------------------------------------------------------- acciones
    def open_url(self, raw: str):
        url = normalize_url(raw)
        if not url or not HAS_WEB:
            return
        self._current_url = url
        self.view.setUrl(QUrl(url))
        self.stack.setCurrentIndex(1)

    def go_home(self):
        if HAS_WEB:
            self.view.setUrl(QUrl("about:blank"))      # detiene audio/video de la página
            self.lbl_title.clear()
        self.stack.setCurrentIndex(0)

    def _tile_clicked(self, item):
        row = self.tiles.row(item)
        pages = self._pages()
        if 0 <= row < len(pages):
            self.open_url(pages[row]["url"])

    def _menu(self, pos):
        item = self.tiles.itemAt(pos)
        if not item:
            return
        row = self.tiles.row(item)
        pages = self._pages()
        m = QMenu(self)
        a_open = m.addAction("Abrir")
        a_ren = m.addAction("Cambiar nombre…")
        a_del = m.addAction("Quitar de Páginas")
        chosen = m.exec(self.tiles.viewport().mapToGlobal(pos))
        if chosen == a_open:
            self.open_url(pages[row]["url"])
        elif chosen == a_ren:
            name, ok = QInputDialog.getText(self, "Cambiar nombre", "Nombre:", text=pages[row]["name"])
            if ok and name.strip():
                pages[row]["name"] = name.strip()
                self.settings.set("pages", pages)
                self.reload_tiles()
        elif chosen == a_del:
            del pages[row]
            self.settings.set("pages", pages)
            self.reload_tiles()

    def _on_icon(self, icon):
        if icon.isNull():
            return
        path = favicon_path(self.view.url().toString())
        if path.exists():
            return
        icon.pixmap(64, 64).save(str(path), "PNG")
        host = host_of(self.view.url().toString())
        if any(host_of(p["url"]) == host for p in self._pages()):
            self.reload_tiles()

    def _on_fullscreen(self, request):
        """Pantalla completa dentro de la página web (p. ej. el botón de YouTube)."""
        request.accept()
        if request.toggleOn():
            self._wl.removeWidget(self.view)
            self.view.setParent(None)
            self.view.showFullScreen()
        else:
            self.view.showNormal()
            self._wl.addWidget(self.view, 1)

    def shutdown(self):
        if HAS_WEB and self.page is not None:
            self.view.setPage(None)
            self.page.deleteLater()
            self.page = None
