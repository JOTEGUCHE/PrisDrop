"""Reproductor multimedia integrado (video y música) con cola, pantalla completa y recomendaciones."""
import logging
import math
import random
import sys
import time

from PySide6.QtCore import QCoreApplication, QEvent, QRectF, QSize, Qt, QTimer, QUrl
from PySide6.QtGui import (QColor, QCursor, QGuiApplication, QIcon, QLinearGradient, QPainter,
                           QPainterPath, QPen, QPixmap)
from PySide6.QtMultimedia import (QAudioBuffer, QAudioBufferOutput, QAudioFormat, QAudioOutput,
                                  QMediaPlayer)
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (QApplication, QComboBox, QFrame, QGraphicsBlurEffect, QHBoxLayout,
                               QLabel, QListWidget, QListWidgetItem, QMainWindow,
                               QPushButton, QSlider,
                               QStackedWidget, QVBoxLayout, QWidget)

from ..settings import Settings
from ..themes import WINDOWS95_THEME
from .icons import asset_pixmap, bind_icon, svg_icon
from .text_effects import apply_text_effect
from .widgets import SeekSlider, fmt_duration, rounded_pixmap

REPEAT_LABELS = ["No", "Lista", "Uno"]
HIDE_AFTER = 2.5        # segundos sin mover el mouse para ocultar los controles en pantalla completa
AUDIO_VISUALIZER_BARS = 36
logger = logging.getLogger(__name__)


def _audio_buffer_levels(buffer: QAudioBuffer) -> list[float]:
    if not buffer.isValid() or buffer.frameCount() <= 0:
        return [0.0] * AUDIO_VISUALIZER_BARS

    audio_format = buffer.format()
    channels = audio_format.channelCount()
    if channels <= 0:
        return [0.0] * AUDIO_VISUALIZER_BARS

    sample_format = audio_format.sampleFormat()
    data = memoryview(buffer.constData())
    try:
        if sample_format == QAudioFormat.SampleFormat.UInt8:
            samples = data.cast("B")
            normalize = lambda value: (value - 128) / 128
        elif sample_format == QAudioFormat.SampleFormat.Int16:
            samples = data.cast("h")
            normalize = lambda value: value / 32768
        elif sample_format == QAudioFormat.SampleFormat.Int32:
            samples = data.cast("i")
            normalize = lambda value: value / 2147483648
        elif sample_format == QAudioFormat.SampleFormat.Float:
            samples = data.cast("f")
            normalize = lambda value: max(-1.0, min(1.0, value))
        else:
            return [0.0] * AUDIO_VISUALIZER_BARS
    except (TypeError, ValueError):
        return [0.0] * AUDIO_VISUALIZER_BARS

    frame_count = min(buffer.frameCount(), len(samples) // channels)
    if frame_count <= 0:
        return [0.0] * AUDIO_VISUALIZER_BARS

    bar_count = min(AUDIO_VISUALIZER_BARS, frame_count)
    levels = []
    for bar in range(bar_count):
        first_frame = bar * frame_count // bar_count
        last_frame = (bar + 1) * frame_count // bar_count
        energy = 0.0
        sample_total = 0
        for frame in range(first_frame, last_frame):
            for channel in range(channels):
                sample = normalize(samples[frame * channels + channel])
                energy += sample * sample
                sample_total += 1
        rms = math.sqrt(energy / sample_total) if sample_total else 0.0
        levels.append(min(1.0, rms * 5.0))
    return levels + [0.0] * (AUDIO_VISUALIZER_BARS - len(levels))


def _apply_media_text_style(label: QLabel, app: QCoreApplication | None) -> None:
    text_color = app.property("theme_media_text_color") if app else None
    shadow_enabled = app.property("theme_media_shadow_enabled") if app else False
    shadow_color = app.property("theme_media_shadow_color") if app else None
    shadow_opacity = app.property("theme_media_shadow_opacity") if app else None
    shadow_blur = app.property("theme_media_shadow_blur") if app else None
    shadow_size = app.property("theme_media_shadow_size") if app else None
    shadow_offset_x = app.property("theme_media_shadow_offset_x") if app else None
    shadow_offset_y = app.property("theme_media_shadow_offset_y") if app else None
    outline_enabled = app.property("theme_media_outline_enabled") if app else False
    outline_color = app.property("theme_media_outline_color") if app else None
    outline_size = app.property("theme_media_outline_size") if app else None
    outline_offset_x = app.property("theme_media_outline_offset_x") if app else None
    outline_offset_y = app.property("theme_media_outline_offset_y") if app else None
    label.setStyleSheet(f"color: {text_color or '#f1f1f1'}; background: transparent;")
    apply_text_effect(
        label,
        outline_enabled=bool(outline_enabled),
        outline_color=outline_color or "#000000",
        outline_size=float(outline_size if outline_size is not None else 1),
        shadow_enabled=bool(shadow_enabled),
        shadow_color=shadow_color or "#000000",
        shadow_opacity=int(shadow_opacity if shadow_opacity is not None else 75),
        shadow_blur=int(shadow_blur if shadow_blur is not None else 8),
        shadow_size=float(shadow_size if shadow_size is not None else 2),
        shadow_offset_x=float(shadow_offset_x if shadow_offset_x is not None else 0),
        shadow_offset_y=float(shadow_offset_y if shadow_offset_y is not None else 0),
        outline_offset_x=float(outline_offset_x if outline_offset_x is not None else 0),
        outline_offset_y=float(outline_offset_y if outline_offset_y is not None else 0),
    )


class HStrip(QListWidget):
    """Lista horizontal que se desplaza con la rueda del mouse."""

    def wheelEvent(self, e):
        bar = self.horizontalScrollBar()
        bar.setValue(bar.value() - e.angleDelta().y())
        e.accept()


class AudioVisualizer(QWidget):
    """Visualizador de niveles de audio para la vista a pantalla completa."""
    def __init__(self):
        super().__init__()
        self._targets = [0.0] * AUDIO_VISUALIZER_BARS
        self._levels = [0.0] * AUDIO_VISUALIZER_BARS
        self.timer = QTimer(self)
        self.timer.setInterval(45)
        self.timer.timeout.connect(self.update)

    def set_levels(self, levels: list[float]):
        self._targets = levels[:AUDIO_VISUALIZER_BARS]
        self._targets.extend([0.0] * (AUDIO_VISUALIZER_BARS - len(self._targets)))
        self.update()

    def clear_levels(self):
        self.set_levels([])

    def showEvent(self, event):
        self.timer.start()
        super().showEvent(event)

    def hideEvent(self, event):
        self.timer.stop()
        super().hideEvent(event)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        app = QApplication.instance()
        accent = app.property("theme_accent") if app else None
        painter.setBrush(QColor(accent or "#ff0000"))
        count = AUDIO_VISUALIZER_BARS
        width = self.width() / (count * 1.65)
        gap = width * 0.65
        for i in range(count):
            target = self._targets[i]
            self._levels[i] += (target - self._levels[i]) * (
                0.48 if target > self._levels[i] else 0.18)
            height = max(3, self.height() * self._levels[i] * 0.92)
            x = i * (width + gap)
            painter.drawRoundedRect(x, (self.height() - height) / 2, width, height, width / 2, width / 2)


class ArtworkWidget(QWidget):
    def __init__(self, size: int, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self._pixmap = QPixmap()
        self._circle = True
        self._rotation_enabled = True
        self._playing = False
        self._angle = 0
        self._timer = QTimer(self)
        self._timer.setInterval(40)
        self._timer.timeout.connect(self._rotate)

    def set_pixmap(self, pixmap: QPixmap):
        self._pixmap = pixmap
        self.update()

    def set_appearance(self, circle: bool, rotation_enabled: bool):
        self._circle = circle
        self._rotation_enabled = rotation_enabled
        self._update_timer()
        self.update()

    def set_playing(self, playing: bool):
        self._playing = playing
        self._update_timer()

    def _update_timer(self):
        if self._playing and self._rotation_enabled:
            self._timer.start()
        else:
            self._timer.stop()

    def _rotate(self):
        self._angle = (self._angle + 1.5) % 360
        self.update()

    def paintEvent(self, _event):
        if self._pixmap.isNull():
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        side = min(self.width(), self.height())
        rect = QRectF((self.width() - side) / 2, (self.height() - side) / 2, side, side)
        clip = QPainterPath()
        if self._circle:
            clip.addEllipse(rect)
        else:
            clip.addRoundedRect(rect, side * 0.08, side * 0.08)
        painter.setClipPath(clip)
        draw_side = int(side * math.sqrt(2)) if self._playing and self._rotation_enabled else side
        scaled = self._pixmap.scaled(
            draw_side, draw_side, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation)
        crop_x = (scaled.width() - draw_side) // 2
        crop_y = (scaled.height() - draw_side) // 2
        painter.translate(rect.center())
        if self._playing and self._rotation_enabled:
            painter.rotate(self._angle)
        painter.drawPixmap(QRectF(-draw_side / 2, -draw_side / 2, draw_side, draw_side),
                           scaled, QRectF(crop_x, crop_y, draw_side, draw_side))


class CoverStage(QWidget):
    """Miniatura enmarcada del reproductor, con su fondo difuminado."""

    def __init__(self):
        super().__init__()
        self.setObjectName("cover")
        self.background = QLabel(self)
        self.background.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.background.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.background_blur = QGraphicsBlurEffect(self.background)
        self.background.setGraphicsEffect(self.background_blur)
        self.overlay = QWidget(self)
        self.overlay.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.art = ArtworkWidget(300, self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.art, 0, Qt.AlignmentFlag.AlignCenter)
        self._background_source = QPixmap()
        self._frame_enabled = False
        self._frame_color = QColor("#ffffff")
        self.apply_theme()

    def apply_theme(self):
        app = QApplication.instance()
        radius = app.property("theme_audio_blur_radius") if app else None
        opacity = app.property("theme_audio_overlay_opacity") if app else None
        overlay_color = app.property("theme_audio_overlay_color") if app else None
        surface = app.property("theme_surface") if app else None
        frame_enabled = app.property("theme_audio_artwork_frame") if app else False
        circle = app.property("theme_audio_artwork_circle") if app else True
        rotate = app.property("theme_audio_artwork_rotate") if app else True
        self._frame_enabled = bool(frame_enabled)
        self._frame_color = QColor(surface or "#ffffff")
        self.background_blur.setBlurRadius(int(radius if radius is not None else 24))
        color = QColor(overlay_color or "#000000")
        self.overlay.setStyleSheet(
            f"background-color: rgba({color.red()}, {color.green()}, {color.blue()}, "
            f"{round(255 * int(opacity if opacity is not None else 58) / 100)});")
        self.setStyleSheet("background: transparent; border: none;")
        self.update()
        self.art.set_appearance(bool(circle), bool(rotate))
        self._render_background()

    def set_media(self, pixmap: QPixmap, backdrop: bool = True):
        self.art.set_pixmap(pixmap)
        self._background_source = pixmap if backdrop else QPixmap()
        self._render_background()

    def set_playing(self, playing: bool):
        self.art.set_playing(playing)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._render_background()

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self._frame_enabled:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        width = 4.0
        rect = self.rect().adjusted(width / 2, width / 2, -width / 2, -width / 2)
        radius = min(155.0, rect.height() / 2)
        path = QPainterPath()
        path.addRoundedRect(rect, radius, radius)
        gradient = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        color = QColor(self._frame_color)
        for position, alpha in ((0.0, 230), (0.35, 90), (0.65, 90), (1.0, 230)):
            color.setAlpha(alpha)
            gradient.setColorAt(position, color)
        painter.setPen(QPen(gradient, width))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)

    def _render_background(self):
        content = self.rect().adjusted(5, 5, -5, -5)
        self.background.setGeometry(content)
        self.overlay.setGeometry(content)
        show_background = self._frame_enabled and not self._background_source.isNull()
        self.background.setVisible(show_background)
        self.overlay.setVisible(show_background)
        if show_background and content.width() and content.height():
            scaled = self._background_source.scaled(
                content.size(), Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation)
            self.background.setPixmap(scaled)
        else:
            self.background.clear()
        self.background.lower()
        self.overlay.raise_()
        self.art.raise_()


class AudioStage(QWidget):
    def __init__(self):
        super().__init__()
        self.background = QLabel(self)
        self.background.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.background.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.background_blur = QGraphicsBlurEffect(self.background)
        self.background.setGraphicsEffect(self.background_blur)
        self.background_overlay = QWidget(self)
        self.background_overlay.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.background_overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._background_source = QPixmap()
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setContentsMargins(40, 35, 40, 24)
        self.art = ArtworkWidget(320)
        self.title = QLabel()
        self.title.setObjectName("heading")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.artist = QLabel()
        self.artist.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.visualizer = AudioVisualizer()
        self.visualizer.setFixedHeight(72)
        layout.addWidget(self.art, 0, Qt.AlignmentFlag.AlignCenter)
        layout.addSpacing(20)
        layout.addWidget(self.title)
        layout.addWidget(self.artist)
        layout.addSpacing(16)
        layout.addWidget(self.visualizer)
        self.background.lower()
        self.background_overlay.raise_()
        for widget in (self.art, self.title, self.artist, self.visualizer):
            widget.raise_()
        self.apply_theme()

    def apply_theme(self):
        app = QApplication.instance()
        theme = app.property("theme_audio_blur_radius") if app else None
        opacity = app.property("theme_audio_overlay_opacity") if app else None
        overlay_color = app.property("theme_audio_overlay_color") if app else None
        circle = app.property("theme_audio_artwork_circle") if app else True
        rotate = app.property("theme_audio_artwork_rotate") if app else True
        blur_radius = int(theme if theme is not None else 24)
        opacity = int(opacity if opacity is not None else 58)
        color = QColor(overlay_color or "#000000")
        self.setStyleSheet("background: transparent;")
        self.background_blur.setBlurRadius(blur_radius)
        self.background_overlay.setStyleSheet(
            f"background-color: rgba({color.red()}, {color.green()}, {color.blue()}, "
            f"{round(255 * opacity / 100)});")
        self.art.set_appearance(bool(circle), bool(rotate))
        _apply_media_text_style(self.title, app)
        _apply_media_text_style(self.artist, app)
        self._render_background()

    def set_media(self, item):
        self.apply_theme()
        pixmap = QPixmap(item.thumb) if item.thumb else QPixmap()
        if pixmap.isNull():
            app = QApplication.instance()
            assets = app.property("theme_assets") if app else {}
            empty_assets = app.property("theme_empty_assets") if app else []
            custom = asset_pixmap(
                "" if "player_art" in (empty_assets or []) else
                (assets or {}).get("player_art", ""), 320, 320)
            if custom.isNull() and "player_art" not in (empty_assets or []):
                custom = svg_icon("music", "#aaaaaa", 96).pixmap(96, 96)
            self._background_source = custom
            self.art.set_pixmap(custom)
        else:
            self._background_source = pixmap
            self.art.set_pixmap(pixmap)
        self.title.setText(item.title)
        self.artist.setText(item.artist or "Audio")
        self._render_background()

    def set_playing(self, playing: bool):
        self.art.set_playing(playing)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._render_background()

    def _render_background(self):
        self.background.setGeometry(self.rect())
        self.background_overlay.setGeometry(self.rect())
        if not self._background_source.isNull() and self.width() and self.height():
            scaled = self._background_source.scaled(
                self.size(), Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation)
            self.background.setPixmap(scaled)
        self.background.lower()
        self.background_overlay.raise_()
        for widget in (self.art, self.title, self.artist, self.visualizer):
            widget.raise_()


class FsWindow(QWidget):
    """Ventana negra a pantalla completa para video o audio."""

    def __init__(self):
        super().__init__(None, Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.setStyleSheet("background: black;")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.pages = QStackedWidget()
        self.video = QVideoWidget()
        self.video.setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatio)   # videos verticales (Shorts) con barras negras
        self.audio = AudioStage()
        self.pages.addWidget(self.video)
        self.pages.addWidget(self.audio)
        lay.addWidget(self.pages)


class FsControls(QFrame):
    """Barra de controles flotante (aparece al mover el cursor, como en YouTube)."""
    HEIGHT = 118

    def __init__(self, page: "PlayerPage"):
        flags = (Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint
                 | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.WindowDoesNotAcceptFocus)
        super().__init__(None, flags)
        self.setObjectName("fsbar")
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        player = page.player

        v = QVBoxLayout(self)
        v.setContentsMargins(26, 10, 26, 12)
        v.setSpacing(6)
        self.lbl_title = QLabel()
        self.lbl_title.setObjectName("heading")
        v.addWidget(self.lbl_title)

        row = QHBoxLayout()
        self.lbl_cur = QLabel("0:00")
        self.lbl_total = QLabel("0:00")
        self.seek = SeekSlider(Qt.Orientation.Horizontal)
        self.seek.setRange(0, 0)
        row.addWidget(self.lbl_cur)
        row.addWidget(self.seek, 1)
        row.addWidget(self.lbl_total)
        v.addLayout(row)

        btns = QHBoxLayout()
        btns.setSpacing(8)
        self.btn_prev = QPushButton()
        self.btn_play = QPushButton()
        self.btn_next = QPushButton()
        self.btn_prev.setObjectName("ctl")
        self.btn_next.setObjectName("ctl")
        self.btn_play.setObjectName("play")
        bind_icon(self.btn_prev, "action_previous", "previous")
        bind_icon(self.btn_play, "action_pause", "pause")
        bind_icon(self.btn_next, "action_next", "next")
        self.vol = QSlider(Qt.Orientation.Horizontal)
        self.vol.setRange(0, 100)
        self.vol.setValue(page.vol.value())
        self.vol.setMaximumWidth(120)
        self.btn_exit = QPushButton("Salir de pantalla completa  (Esc)")
        btns.addWidget(self.btn_prev)
        btns.addWidget(self.btn_play)
        btns.addWidget(self.btn_next)
        btns.addSpacing(16)
        self.btn_volume_icon = QPushButton()
        self.btn_volume_icon.setEnabled(False)
        self.btn_volume_icon.setObjectName("ctl")
        bind_icon(self.btn_volume_icon, "action_volume", "volume")
        btns.addWidget(self.btn_volume_icon)
        btns.addWidget(self.vol)
        btns.addStretch(1)
        btns.addWidget(self.btn_exit)
        v.addLayout(btns)

        self.btn_prev.clicked.connect(page.prev)
        self.btn_next.clicked.connect(page.next)
        self.btn_play.clicked.connect(page.toggle)
        self.btn_exit.clicked.connect(page.exit_fullscreen)
        self.seek.sliderMoved.connect(player.setPosition)
        self.seek.sliderReleased.connect(lambda: player.setPosition(self.seek.value()))
        self.vol.valueChanged.connect(page.vol.setValue)
        self.vol.sliderReleased.connect(lambda: page.settings.set("volume", self.vol.value()))
        page.vol.valueChanged.connect(self._sync_vol)
        player.positionChanged.connect(self._on_pos)
        player.durationChanged.connect(self._on_dur)
        player.playbackStateChanged.connect(self._on_state)

    def _sync_vol(self, v):
        self.vol.blockSignals(True)
        self.vol.setValue(v)
        self.vol.blockSignals(False)

    def _on_pos(self, pos):
        if not self.seek.isSliderDown():
            self.seek.setValue(pos)
        self.lbl_cur.setText(fmt_duration(pos // 1000))

    def _on_dur(self, dur):
        self.seek.setRange(0, dur)
        self.lbl_total.setText(fmt_duration(dur // 1000))

    def _on_state(self, state):
        bind_icon(self.btn_play, "action_pause" if state == QMediaPlayer.PlaybackState.PlayingState
                  else "action_play", "pause" if state == QMediaPlayer.PlaybackState.PlayingState else "play")

    def dragging(self) -> bool:
        return self.seek.isSliderDown() or self.vol.isSliderDown()

    def place(self, geo):
        self.setFixedSize(geo.width(), self.HEIGHT)
        self.move(geo.x(), geo.y() + geo.height() - self.HEIGHT)


class PlayerPage(QWidget):
    def __init__(self, settings: Settings):
        super().__init__()
        self.setObjectName("playerPage")
        self.settings = settings
        self.queue = []
        self.index = -1
        self.repeat = 0
        self.library_items = []
        self._sug_items = []
        self._sug_icons = {}
        self.fs_active = False
        self._fs_last_move = 0.0
        self._fs_last_pos = None
        self._fs_bar_visible = False
        self._player_backdrop_pixmap = QPixmap()
        self.player_backdrop = QLabel(self)
        self.player_backdrop.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.player_backdrop.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.player_backdrop_blur = QGraphicsBlurEffect(self.player_backdrop)
        self.player_backdrop.setGraphicsEffect(self.player_backdrop_blur)
        self.player_backdrop_overlay = QWidget(self)
        self.player_backdrop_overlay.setObjectName("playerBackdropOverlay")
        self.player_backdrop_overlay.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.player_backdrop_overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.player_backdrop.hide()
        self.player_backdrop_overlay.hide()

        self.player = QMediaPlayer(self)
        self.audio = QAudioOutput(self)
        self.player.setAudioOutput(self.audio)
        self.audio_buffer_output = QAudioBufferOutput(self)
        self.player.setAudioBufferOutput(self.audio_buffer_output)
        self.audio.setVolume(settings.get("volume") / 100)
        self._windows_media_controls = None
        self._windows_media_controls_attempted = False

        root = QHBoxLayout(self)
        root.setContentsMargins(24, 18, 24, 14)
        root.setSpacing(20)

        # ------------------------------------------------ zona principal
        left = QVBoxLayout()
        left.setSpacing(8)
        self.view = QStackedWidget()
        self.view.setObjectName("mediaView")
        self.view.setMinimumHeight(240)
        self.cover = CoverStage()
        self.video = QVideoWidget()
        self.video.setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatio)
        self.video.setStyleSheet("background: black;")
        self.video.installEventFilter(self)          # doble clic → pantalla completa
        self.view.addWidget(self.cover)
        self.view.addWidget(self.video)
        self.cover.installEventFilter(self)
        self.cover.art.installEventFilter(self)
        self.player.setVideoOutput(self.video)
        self.btn_queue = QPushButton("Ocultar cola")
        bind_icon(self.btn_queue, "action_queue", "queue")
        self.btn_queue.setToolTip("Mostrar u ocultar la cola de reproducción")
        left.addWidget(self.btn_queue, 0, Qt.AlignmentFlag.AlignRight)
        left.addWidget(self.view, 1)

        self.lbl_title = QLabel("Nada en reproducción")
        self.lbl_title.setObjectName("title")
        self.lbl_title.setWordWrap(True)
        self.lbl_artist = QLabel("Elige algo en la Biblioteca para empezar.")
        self.lbl_artist.setObjectName("muted")
        left.addWidget(self.lbl_title)
        left.addWidget(self.lbl_artist)

        seek_row = QHBoxLayout()
        self.lbl_cur = QLabel("0:00")
        self.lbl_total = QLabel("0:00")
        self.seek = SeekSlider(Qt.Orientation.Horizontal)
        self.seek.setRange(0, 0)
        seek_row.addWidget(self.lbl_cur)
        seek_row.addWidget(self.seek, 1)
        seek_row.addWidget(self.lbl_total)
        left.addLayout(seek_row)

        ctl = QHBoxLayout()
        ctl.setSpacing(8)
        self.btn_shuffle = self._ctl("", "Aleatorio", checkable=True)
        bind_icon(self.btn_shuffle, "action_shuffle", "shuffle")
        self.btn_prev = self._ctl("", "Anterior")
        bind_icon(self.btn_prev, "action_previous", "previous")
        self.btn_play = QPushButton()
        self.btn_play.setObjectName("play")
        bind_icon(self.btn_play, "action_play", "play")
        self.btn_play.setToolTip("Reproducir / pausar")
        self.btn_next = self._ctl("", "Siguiente")
        bind_icon(self.btn_next, "action_next", "next")
        self.btn_repeat = QPushButton(REPEAT_LABELS[0])
        bind_icon(self.btn_repeat, "action_repeat", "repeat")
        self.btn_repeat.setToolTip("Modo de repetición")
        self.vol = QSlider(Qt.Orientation.Horizontal)
        self.vol.setRange(0, 100)
        self.vol.setValue(int(settings.get("volume")))
        self.vol.setMaximumWidth(110)
        self.speed = QComboBox()
        self.speed.setMinimumWidth(70)
        for s in (0.5, 0.75, 1.0, 1.25, 1.5, 2.0):
            self.speed.addItem(f"{s:g}x", s)
        self.speed.setCurrentIndex(2)
        self.btn_full = self._ctl("", "Pantalla completa para video o audio")
        bind_icon(self.btn_full, "action_fullscreen", "fullscreen")
        ctl.addWidget(self.btn_shuffle)
        ctl.addWidget(self.btn_prev)
        ctl.addWidget(self.btn_play)
        ctl.addWidget(self.btn_next)
        ctl.addWidget(self.btn_repeat)
        ctl.addStretch(1)
        volume_icon = QPushButton()
        volume_icon.setEnabled(False)
        volume_icon.setObjectName("ctl")
        bind_icon(volume_icon, "action_volume", "volume")
        ctl.addWidget(volume_icon)
        ctl.addWidget(self.vol)
        ctl.addWidget(self.speed)
        ctl.addWidget(self.btn_full)
        left.addLayout(ctl)

        # ---------------------------------------------- recomendaciones
        head = QHBoxLayout()
        self.sug_title = QLabel("Más para ver y escuchar")
        self.sug_title.setObjectName("heading")
        self.btn_mix = QPushButton("Mezclar")
        bind_icon(self.btn_mix, "action_mix", "mix")
        self.btn_mix.clicked.connect(self.refresh_suggestions)
        head.addWidget(self.sug_title)
        head.addStretch(1)
        head.addWidget(self.btn_mix)
        left.addSpacing(6)
        left.addLayout(head)
        self.sug = HStrip()
        self.sug.setObjectName("grid")
        self.sug.setViewMode(QListWidget.ViewMode.IconMode)
        self.sug.setFlow(QListWidget.Flow.LeftToRight)
        self.sug.setWrapping(False)
        self.sug.setMovement(QListWidget.Movement.Static)
        self.sug.setIconSize(QSize(176, 99))
        self.sug.setGridSize(QSize(196, 172))
        self.sug.setWordWrap(True)
        self.sug.setUniformItemSizes(True)
        self.sug.setFixedHeight(196)
        self.sug.itemClicked.connect(self._play_suggestion)
        left.addWidget(self.sug)
        root.addLayout(left, 1)

        # ------------------------------------------------------- cola
        side = QFrame()
        self.queue_panel = side
        side.setObjectName("queue")
        side.setFixedWidth(320)
        sl = QVBoxLayout(side)
        sl.setContentsMargins(14, 14, 14, 14)
        qhead = QLabel("Cola de reproducción")
        qhead.setObjectName("heading")
        sl.addWidget(qhead)
        self.qlist = QListWidget()
        self.qlist.setObjectName("plain")
        self.qlist.setIconSize(QSize(52, 52))
        self.qlist.itemDoubleClicked.connect(lambda it: self.play_index(self.qlist.row(it)))
        sl.addWidget(self.qlist, 1)
        row = QHBoxLayout()
        b_rm = QPushButton("Quitar")
        b_clear = QPushButton("Vaciar")
        b_rm.clicked.connect(self._remove_selected)
        b_clear.clicked.connect(self._clear)
        row.addWidget(b_rm)
        row.addWidget(b_clear)
        sl.addLayout(row)
        root.addWidget(side)

        # ------------------------------------------- pantalla completa
        self.fs_win = FsWindow()
        self.fs_bar = FsControls(self)
        self._fs_timer = QTimer(self)
        self._fs_timer.setInterval(120)
        self._fs_timer.timeout.connect(self._fs_tick)
        self._click_timer = QTimer(self)
        self._click_timer.setSingleShot(True)
        self._click_timer.setInterval(260)
        self._click_timer.timeout.connect(self._fs_click)

        # ------------------------------------------------ conexiones
        self.btn_play.clicked.connect(self.toggle)
        self.btn_next.clicked.connect(self.next)
        self.btn_prev.clicked.connect(self.prev)
        self.btn_repeat.clicked.connect(self._cycle_repeat)
        self.btn_full.clicked.connect(self.enter_fullscreen)
        self.btn_queue.clicked.connect(self._toggle_queue)
        self.vol.valueChanged.connect(lambda v: self.audio.setVolume(v / 100))
        self.vol.sliderReleased.connect(lambda: self.settings.set("volume", self.vol.value()))
        self.speed.currentIndexChanged.connect(lambda _: self.player.setPlaybackRate(self.speed.currentData()))
        self.seek.sliderMoved.connect(self.player.setPosition)
        self.seek.sliderReleased.connect(lambda: self.player.setPosition(self.seek.value()))
        self.player.positionChanged.connect(self._on_position)
        self.player.durationChanged.connect(self._on_duration)
        self.player.playbackStateChanged.connect(self._on_state)
        self.player.mediaStatusChanged.connect(self._on_status)
        self.player.errorOccurred.connect(self._on_error)
        self.audio_buffer_output.audioBufferReceived.connect(self._on_audio_buffer)
        self._show_cover(None)
        self.refresh_suggestions()

    def _ctl(self, text, tip, checkable=False) -> QPushButton:
        b = QPushButton(text)
        b.setObjectName("ctl")
        b.setToolTip(tip)
        b.setCheckable(checkable)
        return b

    def _toggle_queue(self):
        visible = not self.queue_panel.isVisible()
        self.queue_panel.setVisible(visible)
        self.btn_queue.setText("Ocultar cola" if visible else "Mostrar cola")

    # ------------------------------------------------------------ cola
    def set_queue(self, items, index=0):
        self.queue = list(items)
        self._fill_queue()
        self.play_index(index)

    def enqueue(self, items):
        was_empty = not self.queue
        self.queue += list(items)
        self._fill_queue()
        if was_empty:
            self.play_index(0)

    def _fill_queue(self):
        self.qlist.clear()
        for i, it in enumerate(self.queue, 1):
            pixmap = QPixmap(it.thumb) if it.thumb else QPixmap()
            icon = QIcon(rounded_pixmap(pixmap, 52, 52, 10, "▶" if it.kind == "video" else "♪"))
            details = it.artist or ("Video" if it.kind == "video" else "Audio")
            item = QListWidgetItem(icon, f"{i:02d}  {it.title}\n{details}")
            item.setToolTip(it.title)
            self.qlist.addItem(item)
        if 0 <= self.index < len(self.queue):
            self.qlist.setCurrentRow(self.index)

    def _remove_selected(self):
        row = self.qlist.currentRow()
        if row < 0:
            return
        del self.queue[row]
        if row == self.index:
            self.player.stop()
            self.index = -1
            self.lbl_title.setText("Nada en reproducción")
            self.lbl_artist.setText("")
            self._clear_windows_media_controls()
        elif row < self.index:
            self.index -= 1
        self._fill_queue()

    def _clear(self):
        self.exit_fullscreen()
        self.player.stop()
        self._clear_windows_media_controls()
        self.queue.clear()
        self.index = -1
        self._fill_queue()
        self.lbl_title.setText("Nada en reproducción")
        self.lbl_artist.setText("")
        self._show_cover(None)

    # ------------------------------------------------------ recomendaciones
    def set_library(self, items):
        self.library_items = list(items)
        self.refresh_suggestions()

    def refresh_suggestions(self):
        cur = self.queue[self.index].path if 0 <= self.index < len(self.queue) else None
        pool = [i for i in self.library_items if i.path != cur]
        picks = random.sample(pool, min(12, len(pool)))
        self._sug_items = picks
        self.sug.clear()
        for it in picks:
            key = (it.thumb, it.kind)
            icon = self._sug_icons.get(key)
            if icon is None:
                pix = QPixmap(it.thumb) if it.thumb else QPixmap()
                icon = QIcon(rounded_pixmap(pix, 176, 99, 10, "▶" if it.kind == "video" else "♪"))
                self._sug_icons[key] = icon
            li = QListWidgetItem(icon, f"{it.title}\n{it.artist}" if it.artist else it.title)
            li.setToolTip(it.title)
            li.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
            self.sug.addItem(li)
        has = bool(picks)
        self.sug.setVisible(has)
        self.sug_title.setVisible(has)
        self.btn_mix.setVisible(has)

    def _play_suggestion(self, item):
        row = self.sug.row(item)
        if not 0 <= row < len(self._sug_items):
            return
        media = self._sug_items[row]
        for i, q in enumerate(self.queue):
            if q.path == media.path:
                self.play_index(i)
                return
        pos = self.index + 1 if self.index >= 0 else len(self.queue)
        self.queue.insert(pos, media)
        self._fill_queue()
        self.play_index(pos)

    # ------------------------------------------------------- reproducción
    def play_index(self, i: int):
        if not 0 <= i < len(self.queue):
            return
        self.index = i
        it = self.queue[i]
        self._update_windows_media_metadata(it)
        self._player_backdrop_pixmap = QPixmap(it.thumb) if it.thumb else QPixmap()
        if self._player_backdrop_pixmap.isNull():
            app = QApplication.instance()
            assets = app.property("theme_assets") if app else {}
            empty_assets = app.property("theme_empty_assets") if app else []
            self._player_backdrop_pixmap = asset_pixmap(
                "" if "player_art" in (empty_assets or []) else
                (assets or {}).get("player_art", ""), 320, 320)
        self._update_player_backdrop()
        video_output = self.fs_win.video if self.fs_active else self.video
        self.player.setVideoOutput(video_output if it.kind == "video" else None)
        self.player.setSource(QUrl.fromLocalFile(it.path))
        self.player.play()
        self.lbl_title.setText(it.title)
        self.lbl_artist.setText(it.artist or ("Video" if it.kind == "video" else "Audio"))
        self.fs_bar.lbl_title.setText(it.title)
        if it.kind == "video":
            self.view.setCurrentWidget(self.video)
        else:
            self._show_cover(it)
        if self.fs_active:
            if it.kind == "video":
                self.fs_win.pages.setCurrentWidget(self.fs_win.video)
            else:
                self.fs_win.audio.set_media(it)
                self.fs_win.audio.set_playing(
                    self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState)
                self.fs_win.pages.setCurrentWidget(self.fs_win.audio)
        self.qlist.setCurrentRow(i)
        self.refresh_suggestions()
        if self.fs_active:
            self._fs_poke()

    def _show_cover(self, item):
        pix = QPixmap(item.thumb) if item is not None and item.thumb else QPixmap()
        if pix.isNull():
            app = QApplication.instance()
            assets = app.property("theme_assets") if app else {}
            empty_assets = app.property("theme_empty_assets") if app else []
            pix = asset_pixmap(
                "" if "player_art" in (empty_assets or []) else
                (assets or {}).get("player_art", ""), 300, 300)
            if pix.isNull() and "player_art" not in (empty_assets or []):
                pix = svg_icon("music", "#aaaaaa", 96).pixmap(96, 96)
        self.cover.apply_theme()
        self.cover.set_media(pix, backdrop=item is not None)
        self.cover.set_playing(
            item is not None
            and item.kind == "audio"
            and self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState)
        self.view.setCurrentWidget(self.cover)

    def toggle(self):
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        elif self.queue:
            if self.index < 0:
                self.play_index(0)
            else:
                self.player.play()

    def next(self):
        if not self.queue:
            return
        if self.btn_shuffle.isChecked() and len(self.queue) > 1:
            choices = [i for i in range(len(self.queue)) if i != self.index]
            self.play_index(random.choice(choices))
        elif self.index + 1 < len(self.queue):
            self.play_index(self.index + 1)
        elif self.repeat == 1:
            self.play_index(0)
        else:
            self.exit_fullscreen()
            self.player.stop()

    def prev(self):
        if not self.queue:
            return
        if self.player.position() > 3000:
            self.player.setPosition(0)
        else:
            self.play_index(max(0, self.index - 1))

    def _cycle_repeat(self):
        self.repeat = (self.repeat + 1) % 3
        self.btn_repeat.setText(REPEAT_LABELS[self.repeat])

    def pause_if_video(self):
        """Se llama al salir de la página: un video no debe seguir sonando 'por detrás'."""
        if (0 <= self.index < len(self.queue) and self.queue[self.index].kind == "video"
                and self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState):
            self.player.pause()

    # --------------------------------------------------- pantalla completa
    def enter_fullscreen(self):
        if self.fs_active or not (0 <= self.index < len(self.queue)):
            return
        screen = self.screen() or QGuiApplication.primaryScreen()
        geo = screen.geometry()
        self.fs_active = True
        self._fs_bar_visible = False
        self.fs_win.setGeometry(geo)
        item = self.queue[self.index]
        if item.kind == "video":
            self.fs_win.pages.setCurrentWidget(self.fs_win.video)
        else:
            self.fs_win.audio.set_media(item)
            self.fs_win.audio.set_playing(
                self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState)
            self.fs_win.pages.setCurrentWidget(self.fs_win.audio)
        self.fs_win.showFullScreen()
        self.player.setVideoOutput(self.fs_win.video if item.kind == "video" else None)
        self.fs_bar.lbl_title.setText(item.title)
        self.fs_bar.place(geo)
        self._fs_last_pos = None
        app = QApplication.instance()
        if app:
            app.installEventFilter(self)
        for widget in [self.fs_win, *self.fs_win.findChildren(QWidget)]:
            widget.installEventFilter(self)
        self._fs_timer.start()
        self.fs_win.activateWindow()
        self._fs_poke()

    def exit_fullscreen(self):
        if not self.fs_active:
            return
        self.fs_active = False
        self._fs_timer.stop()
        self._click_timer.stop()
        app = QApplication.instance()
        if app:
            app.removeEventFilter(self)
        for widget in [self.fs_win, *self.fs_win.findChildren(QWidget)]:
            widget.removeEventFilter(self)
        self._fs_bar_visible = False
        self._fs_last_pos = None
        if 0 <= self.index < len(self.queue) and self.queue[self.index].kind == "audio":
            self.player.setVideoOutput(None)
            self._show_cover(self.queue[self.index])
        else:
            self.player.setVideoOutput(self.video)
        self.fs_bar.hide()
        self.fs_win.unsetCursor()
        self.fs_win.video.unsetCursor()
        self.fs_win.hide()
        if 0 <= self.index < len(self.queue) and self.queue[self.index].kind == "audio":
            self.view.setCurrentWidget(self.cover)
        else:
            self.view.setCurrentWidget(self.video)
        w = self.window()
        w.activateWindow()
        w.raise_()

    def _fs_poke(self):
        """Muestra los controles y reinicia el temporizador de ocultado."""
        self._fs_last_move = time.monotonic()
        if not self._fs_bar_visible:
            self._fs_bar_visible = True
            self.fs_bar.show()
            self.fs_bar.raise_()
            self.fs_win.unsetCursor()
            self.fs_win.video.unsetCursor()

    def _fs_hide_bar(self):
        self._fs_bar_visible = False
        self.fs_bar.hide()
        self.fs_win.setCursor(Qt.CursorShape.BlankCursor)
        self.fs_win.video.setCursor(Qt.CursorShape.BlankCursor)

    def _fs_tick(self):
        pos = QCursor.pos()
        if pos != self._fs_last_pos:
            self._fs_last_pos = pos
            self._fs_poke()
        elif (self._fs_bar_visible and time.monotonic() - self._fs_last_move > HIDE_AFTER
              and not self.fs_bar.geometry().contains(pos) and not self.fs_bar.dragging()):
            self._fs_hide_bar()

    def _fs_click(self):
        self.toggle()
        self._fs_poke()

    def eventFilter(self, obj, ev):
        t = ev.type()
        if obj in (self.video, self.cover, self.cover.art):
            if t == QEvent.Type.MouseButtonDblClick:
                self.enter_fullscreen()
                return True
            return False
        if not self.fs_active:
            return False
        if t == QEvent.Type.KeyPress:
            k = ev.key()
            if k in (Qt.Key.Key_Escape, Qt.Key.Key_F):
                self.exit_fullscreen()
                return True
            if k == Qt.Key.Key_Space:
                self.toggle()
                self._fs_poke()
                return True
            if k == Qt.Key.Key_Left:
                self.player.setPosition(max(0, self.player.position() - 5000))
                self._fs_poke()
                return True
            if k == Qt.Key.Key_Right:
                self.player.setPosition(min(self.player.duration(), self.player.position() + 5000))
                self._fs_poke()
                return True
            if k in (Qt.Key.Key_Up, Qt.Key.Key_Down):
                self.vol.setValue(self.vol.value() + (5 if k == Qt.Key.Key_Up else -5))
                self._fs_poke()
                return True
        elif obj in (self.fs_win, self.fs_win.video):
            if t == QEvent.Type.MouseButtonDblClick:
                self._click_timer.stop()
                self.exit_fullscreen()
                return True
            if t == QEvent.Type.MouseButtonRelease and ev.button() == Qt.MouseButton.LeftButton:
                self._click_timer.start()
                return True
        return False

    # --------------------------------------------------------- señales
    def _on_position(self, pos):
        if not self.seek.isSliderDown():
            self.seek.setValue(pos)
        self.lbl_cur.setText(fmt_duration(pos // 1000))

    def _on_duration(self, dur):
        self.seek.setRange(0, dur)
        self.lbl_total.setText(fmt_duration(dur // 1000))

    def _on_state(self, state):
        playing = state == QMediaPlayer.PlaybackState.PlayingState
        if self._windows_media_controls is not None:
            playback_status = (
                "playing" if playing else
                "paused" if state == QMediaPlayer.PlaybackState.PausedState else
                "stopped"
            )
            try:
                self._windows_media_controls.set_playback_state(playback_status)
            except (OSError, RuntimeError, ValueError) as error:
                self._report_windows_media_controls_error(error)
        if not playing:
            self.fs_win.audio.visualizer.clear_levels()
        bind_icon(self.btn_play, "action_pause" if playing else "action_play",
                  "pause" if playing else "play")
        self.cover.set_playing(playing and 0 <= self.index < len(self.queue)
                               and self.queue[self.index].kind == "audio")
        self.fs_win.audio.set_playing(playing and 0 <= self.index < len(self.queue)
                                      and self.queue[self.index].kind == "audio")
        self._update_player_backdrop()

    def _on_audio_buffer(self, buffer: QAudioBuffer):
        if (0 <= self.index < len(self.queue)
                and self.queue[self.index].kind == "audio"):
            self.fs_win.audio.visualizer.set_levels(_audio_buffer_levels(buffer))

    def _update_windows_media_metadata(self, item):
        if sys.platform != "win32":
            return
        if not self._windows_media_controls_attempted:
            self._windows_media_controls_attempted = True
            try:
                from ..windows_media_controls import WindowsMediaControls

                self._windows_media_controls = WindowsMediaControls(
                    int(self.window().winId()), self)
                self._windows_media_controls.button_pressed.connect(
                    self._on_windows_media_button)
            except (ImportError, OSError, RuntimeError) as error:
                self._report_windows_media_controls_error(error)
                return
        if self._windows_media_controls is None:
            return
        try:
            self._windows_media_controls.set_media(
                item.title, item.artist or ("Video" if item.kind == "video" else "Audio"),
                item.kind == "video", item.thumb or "")
        except (OSError, RuntimeError, ValueError) as error:
            self._report_windows_media_controls_error(error)

    def _report_windows_media_controls_error(self, error):
        logger.warning("No se pudieron activar los controles multimedia de Windows: %s", error,
                       exc_info=True)
        controls = self._windows_media_controls
        self._windows_media_controls = None
        self._windows_media_controls_attempted = True
        if controls is not None:
            try:
                controls.close()
            except (OSError, RuntimeError, ValueError) as close_error:
                logger.warning("No se pudo cerrar la sesión multimedia de Windows: %s",
                               close_error, exc_info=True)
        window = self.window()
        if isinstance(window, QMainWindow):
            window.statusBar().showMessage(
                f"Controles multimedia de Windows no disponibles: {error}", 10000)

    def _clear_windows_media_controls(self):
        if self._windows_media_controls is None:
            return
        try:
            self._windows_media_controls.clear_media()
        except (OSError, RuntimeError, ValueError) as error:
            self._report_windows_media_controls_error(error)

    def _on_windows_media_button(self, button: str):
        if button == "play":
            if self.queue:
                self.player.play()
        elif button == "pause":
            self.player.pause()
        elif button == "next":
            self.next()
        elif button == "previous":
            self.prev()
        elif button == "stop":
            self.player.stop()

    def _update_player_backdrop(self):
        app = QApplication.instance()
        theme_name = app.property("theme_name") if app else None
        active = (
            theme_name == WINDOWS95_THEME["name"]
            and 0 <= self.index < len(self.queue)
            and self.queue[self.index].kind == "audio"
            and self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
            and not self._player_backdrop_pixmap.isNull()
        )
        self.player_backdrop.setVisible(active)
        self.player_backdrop_overlay.setVisible(active)
        if not active:
            return
        radius = app.property("theme_audio_blur_radius") if app else None
        self.player_backdrop_blur.setBlurRadius(int(radius if radius is not None else 24))
        self._render_player_backdrop()

    def apply_media_text_theme(self):
        app = QApplication.instance()
        labels = (
            self.lbl_title,
            self.lbl_artist,
            self.sug_title,
            self.lbl_cur,
            self.lbl_total,
            self.fs_bar.lbl_title,
            self.fs_bar.lbl_cur,
            self.fs_bar.lbl_total,
            self.fs_win.audio.title,
            self.fs_win.audio.artist,
        )
        for label in labels:
            _apply_media_text_style(label, app)
        self.cover.apply_theme()
        self.fs_win.audio.apply_theme()

    def _render_player_backdrop(self):
        self.player_backdrop.setGeometry(self.rect())
        self.player_backdrop_overlay.setGeometry(self.rect())
        if not self._player_backdrop_pixmap.isNull() and self.width() and self.height():
            scaled = self._player_backdrop_pixmap.scaled(
                self.size(), Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation)
            self.player_backdrop.setPixmap(scaled)
        self.player_backdrop.lower()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._render_player_backdrop()

    def _on_status(self, status):
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            if self.repeat == 2:
                self.player.setPosition(0)
                self.player.play()
            else:
                self.next()

    def _on_error(self, _err, message):
        self.lbl_artist.setText(f"No se pudo reproducir: {message}")

    def shutdown(self):
        self.exit_fullscreen()
        self.player.stop()
        if self._windows_media_controls is not None:
            try:
                self._windows_media_controls.close()
            except (OSError, RuntimeError, ValueError) as error:
                logger.warning("No se pudo cerrar la sesión multimedia de Windows: %s",
                               error, exc_info=True)
        self.fs_bar.close()
        self.fs_win.close()
