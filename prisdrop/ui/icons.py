"""Iconos SVG propios para controles de la interfaz."""
from PySide6.QtCore import QByteArray, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QWidget

SVG_PATHS = {
    "download": '<path d="M5 20h14v-2H5v2zM19 9h-4V3H9v6H5l7 7 7-7z"/>',
    "library": '<path d="M4 5h16v14H4z"/><path fill="#fff" d="M7 8h10v2H7zm0 4h10v2H7zm0 4h7v1H7z"/>',
    "player": '<path d="M8 5v14l11-7z"/>',
    "pages": '<path d="M4 5h16v14H4z"/><path fill="#fff" d="M7 8h10v8H7z"/><path d="M9 10h6v1H9zm0 2h6v1H9z"/>',
    "themes": '<path d="M12 3a9 9 0 1 0 0 18h1.2a2.8 2.8 0 0 0 2-4.8 1.1 1.1 0 0 1 .8-1.9H18a3 3 0 0 0 3-3C21 6.7 16.9 3 12 3zm-4 9a1.4 1.4 0 1 1 0-2.8A1.4 1.4 0 0 1 8 12zm2-4a1.4 1.4 0 1 1 0-2.8A1.4 1.4 0 0 1 10 8zm4 0a1.4 1.4 0 1 1 0-2.8A1.4 1.4 0 0 1 14 8zm3 4a1.4 1.4 0 1 1 0-2.8A1.4 1.4 0 0 1 17 12z"/>',
    "settings": '<path d="m19.4 13 .1-1-.1-1 2-1.5-2-3.5-2.4 1a7 7 0 0 0-1.7-1L15 3h-6l-.4 2.5a7 7 0 0 0-1.7 1l-2.4-1-2 3.5 2 1.5-.1 1 .1 1-2 1.5 2 3.5 2.4-1a7 7 0 0 0 1.7 1L9 21h6l.4-2.5a7 7 0 0 0 1.7-1l2.4 1 2-3.5-2.1-2zM12 15.5a3.5 3.5 0 1 1 0-7 3.5 3.5 0 0 1 0 7z"/>',
    "play": '<path d="M8 5v14l11-7z"/>',
    "pause": '<path d="M6 5h4v14H6zm8 0h4v14h-4z"/>',
    "previous": '<path d="M6 5h2v14H6zm13 0v14L9 12z"/>',
    "next": '<path d="M16 5h2v14h-2zM5 5v14l10-7z"/>',
    "fullscreen": '<path d="M4 4h6v2H6v4H4zm10 0h6v6h-2V6h-4zM4 14h2v4h4v2H4zm14 0h2v6h-6v-2h4z"/>',
    "shuffle": '<path d="M17 3h4v4h-2V6h-1.2l-4.1 4.1-1.4-1.4L16.6 5H17zm-12 3h2.5l9 12H21v2h-5.5l-9-12H5zm0 12h2.5l2.2-2.9 1.4 1.4L8.5 20H5zm11-12h5v2h-4.5l-2.3 2.3-1.4-1.4z"/>',
    "repeat": '<path d="M7 7h11l-2-2 1.4-1.4L22 8l-4.6 4.4L16 11l2-2H7a2 2 0 0 0-2 2v2H3v-2a4 4 0 0 1 4-4zm10 10H6l2 2-1.4 1.4L2 16l4.6-4.4L8 13l-2 2h11a2 2 0 0 0 2-2v-2h2v2a4 4 0 0 1-4 4z"/>',
    "volume": '<path d="M3 9v6h4l5 4V5L7 9zm13.5 3a4.5 4.5 0 0 0-2.5-4v8a4.5 4.5 0 0 0 2.5-4zm-2.5-9v2.1a7 7 0 0 1 0 13.8V21a9 9 0 0 0 0-18z"/>',
    "refresh": '<path d="M17.7 6.3A8 8 0 0 0 4 11H1l4 4 4-4H6a6 6 0 1 1 1.8 4.2l-1.4 1.4A8 8 0 1 0 17.7 6.3z"/>',
    "mix": '<path d="M17 3h4v4h-2V6h-2v2h-2V5a2 2 0 0 1 2-2zM3 6h3.5l11 12H21v2h-4.5l-11-12H3zm0 12h3.5l3-3.3 1.4 1.5L7.5 20H3zm13-6h2v3h1v-1h2v4h-4a2 2 0 0 1-2-2z"/>',
    "queue": '<path d="M4 5h16v2H4zm0 5h16v2H4zm0 5h10v2H4zm13 0 5 3-5 3z"/>',
    "music": '<path d="M12 3v12.3A4 4 0 1 1 10 12V6l10-2v9.3A4 4 0 1 1 18 10V3z"/>',
}


def svg_icon(name: str, color: str = "#f1f1f1", size: int = 20) -> QIcon:
    body = SVG_PATHS.get(name, SVG_PATHS["player"])
    svg = QByteArray(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" '
        f'viewBox="0 0 24 24" fill="{color}">{body}</svg>'.encode("utf-8"))
    renderer = QSvgRenderer(svg)
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return QIcon(pixmap)


def render_svg(path: str, width: int, height: int) -> QPixmap:
    renderer = QSvgRenderer(path)
    if not renderer.isValid():
        return QPixmap()
    pixmap = QPixmap(width, height)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return pixmap


def bind_icon(widget: QWidget, slot: str, default_icon: str, size: int = 20) -> None:
    widget.setProperty("theme_icon_slot", slot)
    widget.setProperty("theme_icon_default", default_icon)
    if isinstance(widget, QPushButton):
        widget.setIcon(svg_icon(default_icon))
        widget.setIconSize(QSize(size, size))


def apply_theme_assets(theme: dict) -> None:
    app = QApplication.instance()
    if app is None:
        return
    assets = theme.get("assets", {})
    empty_assets = set(theme.get("empty_assets", []))
    color = theme.get("text", "#f1f1f1")
    for widget in app.allWidgets():
        slot = widget.property("theme_icon_slot")
        if not slot:
            continue
        if slot in empty_assets:
            widget.setIcon(QIcon())
            continue
        path = assets.get(slot)
        if path:
            icon = QIcon(path)
            if not icon.isNull():
                widget.setIcon(icon)
                continue
        default = widget.property("theme_icon_default") or "player"
        widget.setIcon(svg_icon(default, color))


def asset_pixmap(path: str, width: int, height: int) -> QPixmap:
    if not path:
        return QPixmap()
    if path.lower().endswith(".svg"):
        return render_svg(path, width, height)
    pixmap = QPixmap(path)
    return pixmap.scaled(width, height, Qt.AspectRatioMode.KeepAspectRatio,
                         Qt.TransformationMode.SmoothTransformation) if not pixmap.isNull() else pixmap
