"""Efectos de contorno y sombra para etiquetas de texto."""
import math

from PySide6.QtCore import QCoreApplication, QPoint, QPointF, Qt
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QGraphicsEffect, QLabel, QWidget


class TextDecorationEffect(QGraphicsEffect):
    def __init__(
        self,
        parent: QWidget,
        outline_color: str = "#000000",
        outline_size: float = 0,
        shadow_color: str = "#000000",
        shadow_opacity: int = 0,
        shadow_blur: int = 0,
        shadow_size: float = 0,
        shadow_offset_x: float = 0,
        shadow_offset_y: float = 0,
        outline_offset_x: float = 0,
        outline_offset_y: float = 0,
    ):
        super().__init__(parent)
        self.outline_color = QColor(outline_color)
        self.outline_size = outline_size
        self.shadow_color = QColor(shadow_color)
        self.shadow_opacity = shadow_opacity
        self.shadow_blur = shadow_blur
        self.shadow_size = shadow_size
        self.shadow_offset_x = shadow_offset_x
        self.shadow_offset_y = shadow_offset_y
        self.outline_offset_x = outline_offset_x
        self.outline_offset_y = outline_offset_y

    def boundingRectFor(self, rect):
        outline_margin_x = self.outline_size + abs(self.outline_offset_x)
        outline_margin_y = self.outline_size + abs(self.outline_offset_y)
        shadow_margin_x = (
            self.shadow_size + self.shadow_blur + abs(self.shadow_offset_x)
            if self.shadow_opacity else 0
        )
        shadow_margin_y = (
            self.shadow_size + self.shadow_blur + abs(self.shadow_offset_y)
            if self.shadow_opacity else 0
        )
        return rect.adjusted(
            -max(outline_margin_x, shadow_margin_x),
            -max(outline_margin_y, shadow_margin_y),
            max(outline_margin_x, shadow_margin_x),
            max(outline_margin_y, shadow_margin_y),
        )

    @staticmethod
    def _tint(pixmap: QPixmap, color: QColor) -> QPixmap:
        tinted = QPixmap(pixmap.size())
        tinted.fill(Qt.GlobalColor.transparent)
        painter = QPainter(tinted)
        painter.drawPixmap(0, 0, pixmap)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        painter.fillRect(tinted.rect(), color)
        painter.end()
        return tinted

    @staticmethod
    def _ring_offsets(radius: int) -> list[tuple[int, int]]:
        if radius <= 0:
            return [(0, 0)]
        steps = 8
        return [
            (round(math.cos(index * math.tau / steps) * radius),
             round(math.sin(index * math.tau / steps) * radius))
            for index in range(steps)
        ]

    @staticmethod
    def _outline_offsets(radius: float) -> list[tuple[float, float]]:
        if radius == 0:
            return [(0.0, 0.0)]
        whole_radius = math.floor(radius)
        positions = [
            (float(x), float(y))
            for y in range(-whole_radius, whole_radius + 1)
            for x in range(-whole_radius, whole_radius + 1)
            if x * x + y * y <= radius * radius
        ]
        steps = max(16, math.ceil(math.tau * radius * 4))
        if steps % 2:
            steps += 1
        positions.extend(
            (math.cos(index * math.tau / steps) * radius,
             math.sin(index * math.tau / steps) * radius)
            for index in range(steps)
        )
        return positions

    def draw(self, painter: QPainter) -> None:
        offset = QPoint()
        pixmap = self.sourcePixmap(
            Qt.CoordinateSystem.LogicalCoordinates,
            offset,
            QGraphicsEffect.PixmapPadMode.PadToEffectiveBoundingRect,
        )
        if pixmap.isNull():
            return

        if self.shadow_opacity > 0:
            shadow = QColor(self.shadow_color)
            shadow.setAlpha(round(255 * self.shadow_opacity / 100))
            shadow_mask_color = QColor(shadow)
            shadow_mask_color.setAlpha(255)
            shadow_pixmap = self._tint(pixmap, shadow_mask_color)
            positions = []
            positions.extend(self._outline_offsets(self.shadow_size))
            if self.shadow_blur:
                for radius in range(1, self.shadow_blur + 1, 2):
                    positions.extend(self._ring_offsets(radius))
            shadow_layer = QPixmap(pixmap.size())
            shadow_layer.fill(Qt.GlobalColor.transparent)
            shadow_painter = QPainter(shadow_layer)
            shadow_painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            shadow_painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            shadow_painter.setOpacity(1 / max(1, len(positions)) if self.shadow_blur else 1)
            for x, y in positions:
                shadow_painter.drawPixmap(
                    QPointF(x + self.shadow_offset_x, y + self.shadow_offset_y),
                    shadow_pixmap,
                )
            shadow_painter.end()
            painter.save()
            painter.setOpacity(shadow.alphaF())
            painter.drawPixmap(offset, shadow_layer)
            painter.restore()

        if self.outline_size > 0:
            outline = QColor(self.outline_color)
            outline_mask_color = QColor(outline)
            outline_mask_color.setAlpha(255)
            outline_pixmap = self._tint(pixmap, outline_mask_color)
            outline_layer = QPixmap(pixmap.size())
            outline_layer.fill(Qt.GlobalColor.transparent)
            outline_painter = QPainter(outline_layer)
            outline_painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            outline_painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            for x, y in self._outline_offsets(self.outline_size):
                outline_painter.drawPixmap(
                    QPointF(x + self.outline_offset_x, y + self.outline_offset_y),
                    outline_pixmap,
                )
            outline_painter.end()
            painter.save()
            painter.setOpacity(outline.alphaF())
            painter.drawPixmap(offset, outline_layer)
            painter.restore()

        painter.drawPixmap(offset, pixmap)


def apply_text_effect(
    widget: QWidget,
    *,
    outline_enabled: bool = False,
    outline_color: str = "#000000",
    outline_size: float = 0,
    shadow_enabled: bool = False,
    shadow_color: str = "#000000",
    shadow_opacity: int = 0,
    shadow_blur: int = 0,
    shadow_size: float = 0,
    shadow_offset_x: float = 0,
    shadow_offset_y: float = 0,
    outline_offset_x: float = 0,
    outline_offset_y: float = 0,
) -> None:
    active = outline_enabled and outline_size > 0 or shadow_enabled and shadow_opacity > 0
    current = widget.graphicsEffect()
    if active:
        if isinstance(current, TextDecorationEffect):
            current.setEnabled(False)
        widget.setGraphicsEffect(TextDecorationEffect(
            widget,
            outline_color=outline_color if outline_enabled else "#000000",
            outline_size=outline_size if outline_enabled else 0,
            shadow_color=shadow_color,
            shadow_opacity=shadow_opacity if shadow_enabled else 0,
            shadow_blur=shadow_blur,
            shadow_size=shadow_size,
            shadow_offset_x=shadow_offset_x,
            shadow_offset_y=shadow_offset_y,
            outline_offset_x=outline_offset_x,
            outline_offset_y=outline_offset_y,
        ))
    elif isinstance(current, TextDecorationEffect):
        current.setEnabled(False)


def apply_general_text_outline(app: QCoreApplication | None) -> None:
    if not isinstance(app, QApplication):
        return
    enabled = bool(app.property("theme_general_outline_enabled"))
    color = app.property("theme_general_outline_color") or "#000000"
    size = float(app.property("theme_general_outline_size") or 0)
    offset_x = float(app.property("theme_general_outline_offset_x") or 0)
    offset_y = float(app.property("theme_general_outline_offset_y") or 0)
    bold = bool(app.property("theme_general_text_bold"))
    for label in app.allWidgets():
        if isinstance(label, QLabel) and label.text().strip() and not label.pixmap():
            original_bold = label.property("theme_general_original_bold")
            if original_bold is None:
                original_bold = label.font().bold()
                label.setProperty("theme_general_original_bold", original_bold)
            font = label.font()
            font.setBold(bold or bool(original_bold))
            label.setFont(font)
            apply_text_effect(
                label,
                outline_enabled=enabled,
                outline_color=color,
                outline_size=size,
                outline_offset_x=offset_x,
                outline_offset_y=offset_y,
            )
