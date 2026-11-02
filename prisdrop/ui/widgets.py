"""Widgets y utilidades compartidas."""
import sys
from pathlib import Path

from PySide6.QtCore import QEvent, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import (QLabel, QStyle, QStyleOptionSlider, QVBoxLayout, QWidget,
                               QSlider)

from .icons import asset_pixmap, svg_icon


class SeekSlider(QSlider):
    """Seek bar that jumps to and follows clicks anywhere along its track."""

    def __init__(self, orientation, parent=None):
        super().__init__(orientation, parent)
        self._track_drag = False

    def _set_value_at(self, point):
        option = QStyleOptionSlider()
        self.initStyleOption(option)
        groove = self.style().subControlRect(
            QStyle.ComplexControl.CC_Slider, option, QStyle.SubControl.SC_SliderGroove, self)
        handle = self.style().subControlRect(
            QStyle.ComplexControl.CC_Slider, option, QStyle.SubControl.SC_SliderHandle, self)
        if self.orientation() == Qt.Orientation.Horizontal:
            span = max(0, groove.width() - handle.width())
            position = point.x() - groove.x() - handle.width() // 2
        else:
            span = max(0, groove.height() - handle.height())
            position = point.y() - groove.y() - handle.height() // 2
        value = QStyle.sliderValueFromPosition(
            self.minimum(), self.maximum(), position, span, option.upsideDown)
        self.setValue(value)
        self.sliderMoved.emit(value)

    def mousePressEvent(self, event):
        option = QStyleOptionSlider()
        self.initStyleOption(option)
        sub_control = self.style().hitTestComplexControl(
            QStyle.ComplexControl.CC_Slider, option, event.position().toPoint(), self)
        if (event.button() == Qt.MouseButton.LeftButton
                and sub_control != QStyle.SubControl.SC_SliderHandle):
            self._track_drag = True
            self.setSliderDown(True)
            self._set_value_at(event.position().toPoint())
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._track_drag:
            self._set_value_at(event.position().toPoint())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._track_drag and event.button() == Qt.MouseButton.LeftButton:
            self._set_value_at(event.position().toPoint())
            self._track_drag = False
            self.setSliderDown(False)
            event.accept()
            return
        super().mouseReleaseEvent(event)


def fmt_duration(sec) -> str:
    sec = int(sec or 0)
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def rounded_pixmap(src: QPixmap, w: int, h: int, radius: int = 12, placeholder: str = "♪") -> QPixmap:
    """Miniatura recortada a w×h con esquinas redondeadas (o un marcador si no hay imagen)."""
    out = QPixmap(w, h)
    out.fill(Qt.GlobalColor.transparent)
    p = QPainter(out)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    path = QPainterPath()
    path.addRoundedRect(QRectF(0, 0, w, h), radius, radius)
    if src is None or src.isNull():
        p.fillPath(path, QColor("#272727"))
        icon_name = {"♪": "music", "▶": "player"}.get(placeholder)
        if icon_name:
            icon = svg_icon(icon_name, "#aaaaaa", max(24, min(w, h) // 3))
            icon_pixmap = icon.pixmap(max(24, min(w, h) // 3))
            p.drawPixmap((w - icon_pixmap.width()) // 2, (h - icon_pixmap.height()) // 2, icon_pixmap)
        else:
            p.setPen(QColor("#717171"))
            f = QFont("Segoe UI")
            f.setPixelSize(max(16, h // 3))
            p.setFont(f)
            p.drawText(QRectF(0, 0, w, h), Qt.AlignmentFlag.AlignCenter, placeholder)
    else:
        scaled = src.scaled(w, h, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                            Qt.TransformationMode.SmoothTransformation)
        p.setClipPath(path)
        p.drawPixmap(0, 0, scaled, (scaled.width() - w) // 2, (scaled.height() - h) // 2, w, h)
    p.end()
    return out


def _asset_path(name: str) -> Path:
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
    return root / name


def logo_path() -> Path:
    return _asset_path("PrisDrop-Logotipo.svg")


def app_icon_path() -> Path:
    return _asset_path("PrisDrop-Logo.svg")


class Logo(QWidget):
    """Logotipo de la aplicación."""

    def __init__(self):
        super().__init__()
        self.setFixedSize(200, 42)
        self.pixmap = asset_pixmap(str(logo_path()), 184, 42)
        self._brand_background = False

    def apply_theme(self, theme: dict):
        assets = theme.get("assets", {})
        empty_assets = set(theme.get("empty_assets", []))
        self._brand_background = (
            "brand_logo" not in assets and "brand_logo" not in empty_assets
            and QColor(theme.get("background", "#0f0f0f")).lightness() < 128)
        path = "" if "brand_logo" in empty_assets else assets.get("brand_logo", str(logo_path()))
        self.pixmap = asset_pixmap(path, 184, 42)
        self.update()

    def paintEvent(self, _event):
        p = QPainter(self)
        if self._brand_background:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor("#ffffff"))
            p.drawRoundedRect(4, 3, 188, 36, 5, 5)
        if not self.pixmap.isNull():
            scaled = self.pixmap.scaled(
                188, self.height(), Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation)
            p.drawPixmap(6,
                         (self.height() - scaled.height()) // 2, scaled)
        p.end()


class BusyOverlay(QWidget):
    """Capa oscura «Cargando…» que bloquea la app, pero solo si la acción tarda más de `delay_ms`."""

    def __init__(self, parent: QWidget, delay_ms: int = 1000):
        super().__init__(parent)
        self.setObjectName("busy")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label = QLabel("Cargando, espera por favor…")
        self.label.setObjectName("busytext")
        lay.addWidget(self.label)
        self._count = 0
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(delay_ms)
        self._timer.timeout.connect(self._reveal)
        parent.installEventFilter(self)
        self.hide()

    def start(self):
        self._count += 1
        if self._count == 1:
            self._timer.start()

    def stop(self):
        self._count = max(0, self._count - 1)
        if self._count == 0:
            self._timer.stop()
            if self.isVisible():
                self.releaseKeyboard()
                self.hide()

    def _reveal(self):
        parent = self.parentWidget()
        if self._count > 0 and parent is not None:
            self.setGeometry(parent.rect())
            self.raise_()
            self.show()
            self.setFocus()
            self.grabKeyboard()

    def eventFilter(self, obj, ev):
        parent = self.parentWidget()
        if parent is not None and obj is parent and ev.type() == QEvent.Type.Resize and self.isVisible():
            self.setGeometry(parent.rect())
        return False

    def mousePressEvent(self, e):
        e.accept()

    def mouseReleaseEvent(self, e):
        e.accept()

    def wheelEvent(self, e):
        e.accept()
