"""Interfaz para crear, importar, exportar y aplicar temas."""
import json
import re
import shutil
import uuid
import zipfile
from copy import deepcopy
from pathlib import Path

from PySide6.QtCore import QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (QColorDialog, QFileDialog, QFormLayout, QFrame, QGridLayout, QHBoxLayout,
                               QCheckBox, QLabel, QLineEdit, QListWidget, QListWidgetItem,
                               QMessageBox, QInputDialog,
                               QDoubleSpinBox, QPlainTextEdit, QPushButton, QScrollArea, QSpinBox,
                               QStackedWidget, QToolButton, QVBoxLayout, QWidget)

from ..themes import BUILTIN_THEMES, DEFAULT_THEME, ThemeManager, build_stylesheet
from .icons import asset_pixmap, svg_icon
from .widgets import app_icon_path, logo_path, rounded_pixmap

ASSET_SLOTS = (
    ("brand_logo", "Logotipo de la barra superior"),
    ("app_icon", "Icono de la aplicación"),
    ("player_art", "Imagen de respaldo del reproductor"),
    ("nav_download", "Icono: Descargar"),
    ("nav_library", "Icono: Biblioteca"),
    ("nav_player", "Icono: Reproductor"),
    ("nav_pages", "Icono: Páginas"),
    ("nav_themes", "Icono: Temas"),
    ("nav_settings", "Icono: Ajustes"),
    ("action_download", "Icono: acción Descargar"),
    ("action_play", "Icono: Reproducir"),
    ("action_pause", "Icono: Pausar"),
    ("action_previous", "Icono: Anterior"),
    ("action_next", "Icono: Siguiente"),
    ("action_fullscreen", "Icono: Pantalla completa"),
    ("action_shuffle", "Icono: Aleatorio"),
    ("action_repeat", "Icono: Repetición"),
    ("action_volume", "Icono: Volumen"),
    ("action_mix", "Icono: Mezclar"),
    ("action_queue", "Icono: Cola"),
    ("action_refresh", "Icono: Actualizar"),
)


def _fit_asset_preview(path: str, width: int, height: int) -> QPixmap:
    if not path:
        return QPixmap()
    bounds = QSize(width, height)
    if path.lower().endswith(".svg"):
        renderer = QSvgRenderer(path)
        if not renderer.isValid():
            return QPixmap()
        source_size = renderer.defaultSize()
        if not source_size.isValid() or source_size.isEmpty():
            view_box = renderer.viewBoxF()
            source_size = QSize(round(view_box.width()), round(view_box.height()))
        if not source_size.isValid() or source_size.isEmpty():
            source_size = bounds
        fitted = source_size.scaled(bounds, Qt.AspectRatioMode.KeepAspectRatio)
        pixmap = QPixmap(width, height)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        target = QRectF(
            (width - fitted.width()) / 2,
            (height - fitted.height()) / 2,
            fitted.width(),
            fitted.height(),
        )
        renderer.render(painter, target)
        painter.end()
        return pixmap
    source = QPixmap(path)
    if source.isNull():
        return source
    return source.scaled(bounds, Qt.AspectRatioMode.KeepAspectRatio,
                         Qt.TransformationMode.SmoothTransformation)


class ThemeCard(QToolButton):
    def __init__(self, theme: dict, selected: bool, active: bool, on_click):
        super().__init__()
        self.setFixedSize(224, 178)
        self.setIconSize(QSize(196, 150))
        self.setText("")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clicked.connect(on_click)
        pixmap = self._preview(theme)
        self.setIcon(QIcon(pixmap))
        self.setToolTip(theme["name"] + (" (Actual)" if active else ""))
        border = theme.get("accent", "#6c2fd3") if selected else theme.get("border_color", "#d7c4f1")
        background = theme.get("surface", "#ffffff")
        foreground = theme.get("text", "#321957")
        self.setStyleSheet(
            "QToolButton {"
            f"background-color: {background}; color: {foreground};"
            f"border: 3px solid {border}; border-radius: 20px;"
            "padding: 8px; }"
            "QToolButton:hover { border-width: 4px; }")

    @staticmethod
    def _preview(theme: dict) -> QPixmap:
        width, height = 196, 150
        assets = theme.get("assets", {})
        source = _fit_asset_preview(assets.get("theme_thumbnail", ""), width, height)
        if not source.isNull():
            return rounded_pixmap(source, width, height, 14, "")
        background = QColor(theme.get("background", "#6c2fd3"))
        pixmap = QPixmap(width, height)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(background)
        painter.drawRoundedRect(0, 0, width, height, 14, 14)
        font = QFont("Segoe UI", 44, QFont.Weight.Bold)
        painter.setFont(font)
        painter.setPen(QColor("#ffffff" if background.lightness() < 140 else "#000000"))
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "P")
        painter.end()
        return pixmap


class ThemesPage(QWidget):
    theme_applied = Signal(str, int, dict)

    def __init__(self, settings, manager: ThemeManager):
        super().__init__()
        self.settings = settings
        self.manager = manager
        self._selected = None
        self._assets = {}
        self._empty_assets = set()
        self._current_resource = None

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 22, 28, 18)
        root.setSpacing(14)
        self.pages = QStackedWidget()
        root.addWidget(self.pages, 1)

        gallery = QWidget()
        gallery_layout = QVBoxLayout(gallery)
        gallery_layout.setContentsMargins(0, 0, 0, 0)
        gallery_layout.setSpacing(14)
        gallery_header = QHBoxLayout()
        heading = QVBoxLayout()
        title = QLabel("Temas")
        title.setObjectName("title")
        heading.addWidget(title)
        heading.addWidget(QLabel(
            "Elige un diseño, edítalo o crea tu propio tema."))
        gallery_header.addLayout(heading, 1)
        self.btn_import = QPushButton("Importar")
        self.btn_export = QPushButton("Exportar")
        gallery_header.addWidget(self.btn_import)
        gallery_header.addWidget(self.btn_export)
        gallery_layout.addLayout(gallery_header)
        self.gallery_scroll = QScrollArea()
        self.gallery_scroll.setWidgetResizable(True)
        self.gallery_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.gallery_content = QWidget()
        self.gallery_grid = QGridLayout(self.gallery_content)
        self.gallery_grid.setContentsMargins(10, 10, 10, 10)
        self.gallery_grid.setHorizontalSpacing(30)
        self.gallery_grid.setVerticalSpacing(24)
        self.gallery_scroll.setWidget(self.gallery_content)
        gallery_layout.addWidget(self.gallery_scroll, 1)
        gallery_actions = QHBoxLayout()
        gallery_actions.addStretch(1)
        self.btn_edit_selected = QPushButton("Editar tema")
        self.btn_apply_selected = QPushButton("Aplicar tema")
        self.btn_remove = QPushButton("Eliminar")
        self.btn_edit_selected.setObjectName("primary")
        gallery_actions.addWidget(self.btn_edit_selected)
        gallery_actions.addWidget(self.btn_apply_selected)
        gallery_actions.addWidget(self.btn_remove)
        gallery_layout.addLayout(gallery_actions)
        self.pages.addWidget(gallery)

        self.btn_import.clicked.connect(self._import)
        self.btn_export.clicked.connect(self._export)
        self.btn_edit_selected.clicked.connect(self._edit_selected)
        self.btn_apply_selected.clicked.connect(self._apply_selected)
        self.btn_remove.clicked.connect(self._remove)

        editor = QFrame()
        editor.setObjectName("card")
        ev = QVBoxLayout(editor)
        ev.setContentsMargins(16, 14, 16, 14)
        editor_header = QHBoxLayout()
        self.btn_back = QPushButton("‹ Temas")
        self.editor_title = QLabel("Editar tema")
        self.editor_title.setObjectName("heading")
        editor_header.addWidget(self.btn_back)
        editor_header.addWidget(self.editor_title)
        editor_header.addStretch(1)
        ev.addLayout(editor_header)
        editor_content = QWidget()
        content_layout = QVBoxLayout(editor_content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        form = QFormLayout()
        self.name = QLineEdit()
        form.addRow("Nombre", self.name)
        self.colors = {}
        for key, label in (("background", "Fondo"), ("surface", "Superficies"),
                           ("text", "Texto"), ("muted", "Texto secundario"),
                           ("accent", "Color de énfasis"),
                           ("control_background", "Fondo de controles"),
                           ("control_hover", "Controles al pasar el cursor"),
                           ("border_color", "Bordes y separadores"),
                           ("disabled_text", "Texto deshabilitado"),
                           ("selection_background", "Selección de listas"),
                           ("audio_overlay_color", "Color de oscurecimiento del audio"),
                           ("media_text_color", "Color de títulos e información"),
                           ("media_shadow_color", "Color de la sombra del texto"),
                           ("media_outline_color", "Color del contorno de títulos e información"),
                           ("general_outline_color", "Color del contorno del texto general")):
            button = QPushButton()
            button.clicked.connect(lambda _=False, k=key: self._choose_color(k))
            self.colors[key] = button
            form.addRow(label, button)
        self.font_family = QLineEdit()
        form.addRow("Tipografía", self.font_family)
        self.font_size = QSpinBox()
        self.font_size.setRange(9, 28)
        form.addRow("Tamaño de texto", self.font_size)
        self.animation = QSpinBox()
        self.animation.setRange(0, 1200)
        self.animation.setSuffix(" ms")
        form.addRow("Duración de animación", self.animation)
        self.audio_blur = QSpinBox()
        self.audio_blur.setRange(0, 80)
        self.audio_blur.setSuffix(" px")
        form.addRow("Difuminado del fondo de audio", self.audio_blur)
        self.audio_opacity = QSpinBox()
        self.audio_opacity.setRange(0, 100)
        self.audio_opacity.setSuffix(" %")
        form.addRow("Opacidad del oscurecimiento", self.audio_opacity)
        self.media_shadow_enabled = QCheckBox("Aplicar sombra a títulos e información")
        form.addRow("Sombra de texto", self.media_shadow_enabled)
        self.media_shadow_opacity = QSpinBox()
        self.media_shadow_opacity.setRange(0, 100)
        self.media_shadow_opacity.setSuffix(" %")
        form.addRow("Opacidad de la sombra", self.media_shadow_opacity)
        self.media_shadow_blur = QSpinBox()
        self.media_shadow_blur.setRange(0, 50)
        self.media_shadow_blur.setSuffix(" px")
        form.addRow("Difuminado de la sombra", self.media_shadow_blur)
        self.media_shadow_size = QDoubleSpinBox()
        self.media_shadow_size.setRange(0, 30)
        self.media_shadow_size.setDecimals(2)
        self.media_shadow_size.setSingleStep(0.1)
        self.media_shadow_size.setSuffix(" px")
        form.addRow("Tamaño de la sombra", self.media_shadow_size)
        self.media_shadow_offset_x = self._offset_control()
        form.addRow("Desplazamiento horizontal de la sombra", self.media_shadow_offset_x)
        self.media_shadow_offset_y = self._offset_control()
        form.addRow("Desplazamiento vertical de la sombra", self.media_shadow_offset_y)
        self.media_outline_enabled = QCheckBox("Aplicar contorno a títulos e información")
        form.addRow("Contorno del reproductor", self.media_outline_enabled)
        self.audio_artwork_frame = QCheckBox("Mantener el marco de reproducción")
        self.audio_artwork_frame.setToolTip(
            "Muestra u oculta el fondo rectangular difuminado de la miniatura de audio.")
        form.addRow("Marco de audio", self.audio_artwork_frame)
        self.audio_artwork_circle = QCheckBox("Mostrar la miniatura circular (desactivado: cuadrada con bordes suaves)")
        form.addRow("Forma de la miniatura de audio", self.audio_artwork_circle)
        self.audio_artwork_rotate = QCheckBox("Girar la miniatura mientras se reproduce")
        form.addRow("Animación de la miniatura", self.audio_artwork_rotate)
        self.media_outline_size = QDoubleSpinBox()
        self.media_outline_size.setRange(0.01, 10)
        self.media_outline_size.setDecimals(2)
        self.media_outline_size.setSingleStep(0.1)
        self.media_outline_size.setSuffix(" px")
        form.addRow("Grosor del contorno del reproductor", self.media_outline_size)
        self.media_outline_offset_x = self._offset_control()
        form.addRow("Desplazamiento horizontal del contorno", self.media_outline_offset_x)
        self.media_outline_offset_y = self._offset_control()
        form.addRow("Desplazamiento vertical del contorno", self.media_outline_offset_y)
        self.general_outline_enabled = QCheckBox("Aplicar contorno al texto general")
        form.addRow("Contorno general", self.general_outline_enabled)
        self.general_text_bold = QCheckBox("Mostrar el texto general en negrita")
        form.addRow("Negrita general", self.general_text_bold)
        self.general_outline_size = QDoubleSpinBox()
        self.general_outline_size.setRange(0.01, 10)
        self.general_outline_size.setDecimals(2)
        self.general_outline_size.setSingleStep(0.1)
        self.general_outline_size.setSuffix(" px")
        form.addRow("Grosor del contorno general", self.general_outline_size)
        self.general_outline_offset_x = self._offset_control()
        form.addRow("Desplazamiento horizontal del contorno general", self.general_outline_offset_x)
        self.general_outline_offset_y = self._offset_control()
        form.addRow("Desplazamiento vertical del contorno general", self.general_outline_offset_y)
        self.media_shadow_enabled.toggled.connect(self._set_media_effect_controls_enabled)
        self.media_outline_enabled.toggled.connect(self._set_media_effect_controls_enabled)
        self.general_outline_enabled.toggled.connect(self._set_general_outline_controls_enabled)
        content_layout.addLayout(form)
        thumbnail_row = QHBoxLayout()
        self.thumbnail_preview = QLabel()
        self.thumbnail_preview.setFixedSize(96, 96)
        self.thumbnail_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumbnail_preview.setObjectName("themeThumbnailPreview")
        self.thumbnail_path = QLineEdit()
        self.thumbnail_path.setReadOnly(True)
        self.thumbnail_path.setPlaceholderText("Miniatura opcional")
        self.btn_thumbnail = QPushButton("Añadir miniatura…")
        self.btn_thumbnail_clear = QPushButton("Quitar")
        thumbnail_row.addWidget(self.thumbnail_preview)
        thumbnail_row.addWidget(self.thumbnail_path, 1)
        thumbnail_row.addWidget(self.btn_thumbnail)
        thumbnail_row.addWidget(self.btn_thumbnail_clear)
        content_layout.addLayout(thumbnail_row)
        content_layout.addWidget(QLabel("Imágenes e iconos del tema"))
        self.btn_edit_assets = QPushButton("Editar imágenes e iconos del tema…")
        content_layout.addWidget(self.btn_edit_assets)
        content_layout.addWidget(QLabel("QSS avanzado (opcional; compatible con Qt Style Sheets)"))
        self.qss = QPlainTextEdit()
        self.qss.setPlaceholderText("QPushButton { border-radius: 12px; }")
        self.qss.setMinimumHeight(140)
        content_layout.addWidget(self.qss, 1)
        editor_scroll = QScrollArea()
        editor_scroll.setWidgetResizable(True)
        editor_scroll.setFrameShape(QFrame.Shape.NoFrame)
        editor_scroll.setWidget(editor_content)
        ev.addWidget(editor_scroll, 1)
        buttons = QHBoxLayout()
        self.btn_save = QPushButton("Guardar tema")
        self.btn_duplicate = QPushButton("Duplicar tema")
        self.btn_apply = QPushButton("Aplicar tema")
        self.btn_save.setObjectName("primary")
        buttons.addStretch(1)
        buttons.addWidget(self.btn_save)
        buttons.addWidget(self.btn_duplicate)
        buttons.addWidget(self.btn_apply)
        ev.addLayout(buttons)
        self.pages.addWidget(editor)

        resources = QWidget()
        resources_layout = QVBoxLayout(resources)
        resources_header = QHBoxLayout()
        self.btn_resources_back = QPushButton("‹ Volver al tema")
        self.resources_title = QLabel("Imágenes e iconos del tema")
        self.resources_title.setObjectName("heading")
        resources_header.addWidget(self.btn_resources_back)
        resources_header.addWidget(self.resources_title)
        resources_header.addStretch(1)
        resources_layout.addLayout(resources_header)
        resource_columns = QHBoxLayout()
        self.resource_list = QListWidget()
        self.resource_list.setObjectName("plain")
        self.resource_list.setMinimumWidth(240)
        resource_columns.addWidget(self.resource_list, 1)
        resource_detail = QFrame()
        resource_detail.setObjectName("card")
        detail_layout = QVBoxLayout(resource_detail)
        self.resource_name = QLabel()
        self.resource_name.setObjectName("heading")
        self.resource_type = QLabel()
        self.resource_type.setObjectName("muted")
        self.resource_preview = QLabel("Sin vista previa")
        self.resource_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.resource_preview.setMinimumSize(320, 260)
        self.resource_preview.setMaximumSize(520, 360)
        self.resource_preview.setScaledContents(False)
        self.resource_path = QLabel()
        self.resource_path.setWordWrap(True)
        self.resource_replace = QPushButton("Reemplazar imagen o icono…")
        self.resource_empty = QPushButton("Dejar vacío")
        detail_layout.addWidget(self.resource_name)
        detail_layout.addWidget(self.resource_type)
        detail_layout.addWidget(self.resource_preview, 1, Qt.AlignmentFlag.AlignCenter)
        detail_layout.addWidget(self.resource_path)
        resource_buttons = QHBoxLayout()
        resource_buttons.addWidget(self.resource_replace)
        resource_buttons.addWidget(self.resource_empty)
        detail_layout.addLayout(resource_buttons)
        resource_columns.addWidget(resource_detail, 2)
        resources_layout.addLayout(resource_columns, 1)
        self.pages.addWidget(resources)

        self.btn_back.clicked.connect(self._show_gallery)
        self.btn_thumbnail.clicked.connect(self._choose_thumbnail)
        self.btn_thumbnail_clear.clicked.connect(self._clear_thumbnail)
        self.btn_edit_assets.clicked.connect(self._show_resources)
        self.btn_resources_back.clicked.connect(lambda: self.pages.setCurrentIndex(1))
        self.resource_list.currentItemChanged.connect(self._select_resource)
        self.resource_replace.clicked.connect(self._replace_resource)
        self.resource_empty.clicked.connect(self._empty_resource)
        self.btn_save.clicked.connect(self._save)
        self.btn_duplicate.clicked.connect(self._duplicate)
        self.btn_apply.clicked.connect(self._apply)
        self.refresh()

    def refresh(self):
        selected = self._selected or self.settings.get("active_theme") or DEFAULT_THEME["name"]
        themes = self.manager.all()
        names = {theme["name"] for theme in themes}
        if selected not in names:
            selected = self.settings.get("active_theme") or DEFAULT_THEME["name"]
        if self._selected not in names:
            self._selected = selected
        while self.gallery_grid.count():
            item = self.gallery_grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        for index, theme in enumerate(themes):
            name = theme["name"]
            active = name == (self.settings.get("active_theme") or DEFAULT_THEME["name"])
            cell = QWidget()
            cell_layout = QVBoxLayout(cell)
            cell_layout.setContentsMargins(0, 0, 0, 0)
            cell_layout.setSpacing(6)
            label = QLabel(name + ("  ·  Actual" if active else ""))
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setWordWrap(True)
            card = ThemeCard(
                theme,
                selected=name == self._selected,
                active=active,
                on_click=lambda _checked=False, theme_name=name: self._select_theme(theme_name))
            cell_layout.addWidget(label)
            cell_layout.addWidget(card, 0, Qt.AlignmentFlag.AlignCenter)
            self.gallery_grid.addWidget(cell, index // 3, index % 3, Qt.AlignmentFlag.AlignCenter)
        create_card = self._create_card()
        create_card.clicked.connect(self._new)
        create_cell = QWidget()
        create_layout = QVBoxLayout(create_cell)
        create_layout.setContentsMargins(0, 0, 0, 0)
        create_layout.setSpacing(6)
        create_layout.addWidget(QLabel(""), 0, Qt.AlignmentFlag.AlignCenter)
        create_layout.addWidget(create_card, 0, Qt.AlignmentFlag.AlignCenter)
        index = len(themes)
        self.gallery_grid.addWidget(
            create_cell, index // 3, index % 3, Qt.AlignmentFlag.AlignCenter)
        for column in range(3):
            self.gallery_grid.setColumnStretch(column, 1)
        self._update_gallery_actions()
        self.pages.setCurrentIndex(0)

    @staticmethod
    def _create_card() -> QToolButton:
        card = QToolButton()
        card.setFixedSize(224, 178)
        card.setIconSize(QSize(196, 150))
        card.setText("")
        card.setToolTip("Crear tema")
        card.setCursor(Qt.CursorShape.PointingHandCursor)
        pixmap = QPixmap(196, 150)
        pixmap.fill(QColor("#f3edff"))
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QColor("#6c2fd3"))
        painter.setFont(QFont("Segoe UI", 56, QFont.Weight.Light))
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "+")
        painter.end()
        card.setIcon(QIcon(pixmap))
        card.setStyleSheet(
            "QToolButton { background: #f3edff; color: #321957;"
            "border: 3px solid #d7c4f1; border-radius: 20px; padding: 8px;"
            "} QToolButton:hover { border-color: #6c2fd3; }")
        return card

    def _select_theme(self, name):
        self._selected = name
        self._update_gallery_actions()
        self.refresh()

    def _update_gallery_actions(self):
        selected = next(
            (theme for theme in self.manager.all() if theme["name"] == self._selected), None)
        self.btn_edit_selected.setEnabled(selected is not None)
        self.btn_apply_selected.setEnabled(selected is not None)
        self.btn_export.setEnabled(selected is not None)
        removable = selected is not None and selected["name"] not in {
            theme["name"] for theme in BUILTIN_THEMES}
        self.btn_remove.setEnabled(removable)

    def _show_gallery(self):
        self.refresh()

    def _edit_selected(self):
        theme = next(
            (item for item in self.manager.all() if item["name"] == self._selected), None)
        if theme is None:
            return
        self._load(theme)
        self.editor_title.setText(f"Editar tema: {theme['name']}")
        self.pages.setCurrentIndex(1)

    def _load(self, theme):
        self.name.setText(theme["name"])
        for key, button in self.colors.items():
            color = theme.get(key, DEFAULT_THEME[key])
            button.setText(color)
            button.setStyleSheet(f"background-color: {color}; color: {theme['text']};")
        self.font_family.setText(theme.get("font_family", DEFAULT_THEME["font_family"]))
        self.font_size.setValue(int(theme.get("font_size", DEFAULT_THEME["font_size"])))
        self.animation.setValue(int(theme.get("animation_duration", DEFAULT_THEME["animation_duration"])))
        self.audio_blur.setValue(int(theme.get("audio_blur_radius", DEFAULT_THEME["audio_blur_radius"])))
        self.audio_opacity.setValue(
            int(theme.get("audio_overlay_opacity", DEFAULT_THEME["audio_overlay_opacity"])))
        self.media_shadow_enabled.setChecked(
            bool(theme.get("media_shadow_enabled", DEFAULT_THEME["media_shadow_enabled"])))
        self.media_shadow_opacity.setValue(
            int(theme.get("media_shadow_opacity", DEFAULT_THEME["media_shadow_opacity"])))
        self.media_shadow_blur.setValue(
            int(theme.get("media_shadow_blur", DEFAULT_THEME["media_shadow_blur"])))
        self.media_shadow_size.setValue(
            float(theme.get("media_shadow_size", DEFAULT_THEME["media_shadow_size"])))
        self.media_shadow_offset_x.setValue(
            float(theme.get("media_shadow_offset_x", DEFAULT_THEME["media_shadow_offset_x"])))
        self.media_shadow_offset_y.setValue(
            float(theme.get("media_shadow_offset_y", DEFAULT_THEME["media_shadow_offset_y"])))
        self.media_outline_enabled.setChecked(
            bool(theme.get("media_outline_enabled", DEFAULT_THEME["media_outline_enabled"])))
        self.audio_artwork_frame.setChecked(
            bool(theme.get("audio_artwork_frame", DEFAULT_THEME["audio_artwork_frame"])))
        self.audio_artwork_frame.setEnabled(True)
        self.audio_artwork_circle.setChecked(
            bool(theme.get("audio_artwork_circle", DEFAULT_THEME["audio_artwork_circle"])))
        self.audio_artwork_rotate.setChecked(
            bool(theme.get("audio_artwork_rotate", DEFAULT_THEME["audio_artwork_rotate"])))
        self.media_outline_size.setValue(
            float(theme.get("media_outline_size", DEFAULT_THEME["media_outline_size"])))
        self.media_outline_offset_x.setValue(
            float(theme.get("media_outline_offset_x", DEFAULT_THEME["media_outline_offset_x"])))
        self.media_outline_offset_y.setValue(
            float(theme.get("media_outline_offset_y", DEFAULT_THEME["media_outline_offset_y"])))
        self.general_outline_enabled.setChecked(
            bool(theme.get("general_outline_enabled", DEFAULT_THEME["general_outline_enabled"])))
        self.general_text_bold.setChecked(
            bool(theme.get("general_text_bold", DEFAULT_THEME["general_text_bold"])))
        self.general_outline_size.setValue(
            float(theme.get("general_outline_size", DEFAULT_THEME["general_outline_size"])))
        self.general_outline_offset_x.setValue(
            float(theme.get("general_outline_offset_x", DEFAULT_THEME["general_outline_offset_x"])))
        self.general_outline_offset_y.setValue(
            float(theme.get("general_outline_offset_y", DEFAULT_THEME["general_outline_offset_y"])))
        self._set_media_effect_controls_enabled()
        self._set_general_outline_controls_enabled(self.general_outline_enabled.isChecked())
        self.qss.setPlainText(theme.get("qss", ""))
        self._assets = dict(theme.get("assets", {}))
        self._empty_assets = set(theme.get("empty_assets", []))
        self._show_thumbnail()
        self._populate_resources()

    def _show_thumbnail(self):
        path = self._assets.get("theme_thumbnail", "")
        self.thumbnail_path.setText(path)
        pixmap = _fit_asset_preview(path, 88, 88)
        self.thumbnail_preview.setPixmap(
            rounded_pixmap(pixmap, 88, 88, 12, "") if not pixmap.isNull() else QPixmap())

    def _choose_thumbnail(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Elegir miniatura del tema", "",
            "Imágenes (*.png *.jpg *.jpeg *.webp *.svg)")
        if path:
            self._assets["theme_thumbnail"] = path
            self._show_thumbnail()

    def _clear_thumbnail(self):
        self._assets.pop("theme_thumbnail", None)
        self._show_thumbnail()

    def _populate_resources(self):
        current = self._current_resource
        self.resource_list.blockSignals(True)
        self.resource_list.clear()
        for key, label in ASSET_SLOTS:
            path = self._assets.get(key, "")
            status = " (Vacío)" if key in self._empty_assets else (
                " (Personalizado)" if path else " (Integrado)")
            item = QListWidgetItem(label + status)
            item.setData(Qt.ItemDataRole.UserRole, key)
            self.resource_list.addItem(item)
            if key == current:
                self.resource_list.setCurrentItem(item)
        self.resource_list.blockSignals(False)
        if self.resource_list.currentItem() is None and self.resource_list.count():
            self.resource_list.setCurrentRow(0)
        self._select_resource(self.resource_list.currentItem(), None)

    def _show_resources(self):
        self._populate_resources()
        self.pages.setCurrentIndex(2)

    def _select_resource(self, current, _previous):
        if current is None:
            self._current_resource = None
            return
        key = current.data(Qt.ItemDataRole.UserRole)
        self._current_resource = key
        label = dict(ASSET_SLOTS)[key]
        path = self._assets.get(key, "")
        self.resource_name.setText(label)
        self.resource_path.setText(path or (
            "El espacio quedará vacío." if key in self._empty_assets
            else "Se usará el recurso integrado."))
        suffix = (Path(path).suffix.lower().lstrip(".").upper() if path
                  else "Ninguno" if key in self._empty_assets else "Integrado")
        dimensions = ""
        if path and suffix != "SVG":
            image = QPixmap(path)
            if not image.isNull():
                dimensions = f" · {image.width()} × {image.height()} px"
        resize_note = (
            " · se ajustará a 512 × 512 px al guardar"
            if path and dimensions and (image.width() > 512 or image.height() > 512)
            else "")
        self.resource_type.setText(f"Tipo de archivo: {suffix}{dimensions}{resize_note}")
        pixmap = _fit_asset_preview(path, 480, 320)
        if pixmap.isNull() and not path and key not in self._empty_assets:
            if key == "brand_logo":
                pixmap = _fit_asset_preview(str(logo_path()), 480, 320)
            elif key == "app_icon":
                pixmap = _fit_asset_preview(str(app_icon_path()), 480, 320)
            else:
                default_icons = {
                    "nav_download": "download", "nav_library": "library",
                    "nav_player": "player", "nav_pages": "pages",
                    "nav_themes": "themes", "nav_settings": "settings",
                    "action_download": "download", "action_play": "play",
                    "action_pause": "pause", "action_previous": "previous",
                    "action_next": "next", "action_fullscreen": "fullscreen",
                    "action_shuffle": "shuffle", "action_repeat": "repeat",
                    "action_volume": "volume", "action_mix": "mix",
                    "action_queue": "queue", "action_refresh": "refresh",
                }
                icon_name = default_icons.get(key)
                if key == "player_art":
                    icon_name = "music"
                if icon_name:
                    pixmap = svg_icon(icon_name, "#6c2fd3", 96).pixmap(96, 96)
        if pixmap.isNull():
            self.resource_preview.setPixmap(QPixmap())
            self.resource_preview.setText(
                "Espacio vacío" if key in self._empty_assets else "Sin vista previa")
        else:
            self.resource_preview.setText("")
            self.resource_preview.setPixmap(pixmap)

    @staticmethod
    def _offset_control() -> QDoubleSpinBox:
        control = QDoubleSpinBox()
        control.setRange(-30, 30)
        control.setDecimals(2)
        control.setSingleStep(0.1)
        control.setSuffix(" px")
        return control

    def _replace_resource(self):
        key = self._current_resource
        if not key:
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Reemplazar imagen o icono", "",
            "Imágenes e iconos (*.png *.jpg *.jpeg *.webp *.svg)")
        if path:
            self._assets[key] = path
            self._empty_assets.discard(key)
            self._populate_resources()

    def _empty_resource(self):
        key = self._current_resource
        if not key:
            return
        self._assets.pop(key, None)
        self._empty_assets.add(key)
        self._populate_resources()

    def _choose_color(self, key):
        current = QColor(self.colors[key].text())
        color = QColorDialog.getColor(current, self, "Elige un color")
        if color.isValid():
            self.colors[key].setText(color.name())
            self.colors[key].setStyleSheet(f"background-color: {color.name()};")

    def _set_media_effect_controls_enabled(self, *_):
        shadow_enabled = self.media_shadow_enabled.isChecked()
        outline_enabled = self.media_outline_enabled.isChecked()
        self.colors["media_shadow_color"].setEnabled(shadow_enabled)
        self.media_shadow_opacity.setEnabled(shadow_enabled)
        self.media_shadow_blur.setEnabled(shadow_enabled)
        self.media_shadow_size.setEnabled(shadow_enabled)
        self.media_shadow_offset_x.setEnabled(shadow_enabled)
        self.media_shadow_offset_y.setEnabled(shadow_enabled)
        self.colors["media_outline_color"].setEnabled(outline_enabled)
        self.media_outline_size.setEnabled(outline_enabled)
        self.media_outline_offset_x.setEnabled(outline_enabled)
        self.media_outline_offset_y.setEnabled(outline_enabled)

    def _set_general_outline_controls_enabled(self, enabled):
        self.colors["general_outline_color"].setEnabled(enabled)
        self.general_outline_size.setEnabled(enabled)
        self.general_outline_offset_x.setEnabled(enabled)
        self.general_outline_offset_y.setEnabled(enabled)

    def _form_data(self):
        return {
            "name": self.name.text().strip(),
            **{key: button.text() for key, button in self.colors.items()},
            "font_family": self.font_family.text().strip() or DEFAULT_THEME["font_family"],
            "font_size": self.font_size.value(),
            "animation_duration": self.animation.value(),
            "audio_blur_radius": self.audio_blur.value(),
            "audio_overlay_opacity": self.audio_opacity.value(),
            "media_shadow_enabled": self.media_shadow_enabled.isChecked(),
            "media_shadow_opacity": self.media_shadow_opacity.value(),
            "media_shadow_blur": self.media_shadow_blur.value(),
            "media_shadow_size": self.media_shadow_size.value(),
            "media_shadow_offset_x": self.media_shadow_offset_x.value(),
            "media_shadow_offset_y": self.media_shadow_offset_y.value(),
            "media_outline_enabled": self.media_outline_enabled.isChecked(),
            "audio_artwork_frame": self.audio_artwork_frame.isChecked(),
            "audio_artwork_circle": self.audio_artwork_circle.isChecked(),
            "audio_artwork_rotate": self.audio_artwork_rotate.isChecked(),
            "media_outline_size": self.media_outline_size.value(),
            "media_outline_offset_x": self.media_outline_offset_x.value(),
            "media_outline_offset_y": self.media_outline_offset_y.value(),
            "general_outline_enabled": self.general_outline_enabled.isChecked(),
            "general_outline_size": self.general_outline_size.value(),
            "general_outline_offset_x": self.general_outline_offset_x.value(),
            "general_outline_offset_y": self.general_outline_offset_y.value(),
            "general_text_bold": self.general_text_bold.isChecked(),
            "qss": self.qss.toPlainText(),
            "assets": dict(self._assets),
            "empty_assets": sorted(self._empty_assets),
        }

    def _save(self):
        data = self._form_data()
        try:
            data = self.manager.save(data)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "No se pudo guardar el tema", str(exc))
            return
        self._selected = data["name"]
        self.refresh()
        self._load(data)
        self.editor_title.setText(f"Editar tema: {data['name']}")
        self.pages.setCurrentIndex(1)

    def _apply(self):
        data = self._form_data()
        if not data["name"]:
            QMessageBox.warning(self, "Tema sin nombre", "Escribe un nombre antes de aplicar el tema.")
            return
        try:
            data = self.manager.save(data)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "No se pudo guardar el tema", str(exc))
            return
        self.settings.set("active_theme", data["name"])
        self._selected = data["name"]
        self.theme_applied.emit(build_stylesheet(data), data["animation_duration"], data)
        self.refresh()
        self._load(data)
        self.editor_title.setText(f"Editar tema: {data['name']}")
        self.pages.setCurrentIndex(1)

    def _apply_selected(self):
        data = next(
            (theme for theme in self.manager.all() if theme["name"] == self._selected), None)
        if data is None:
            return
        self.settings.set("active_theme", data["name"])
        self.theme_applied.emit(build_stylesheet(data), data["animation_duration"], data)
        self.refresh()

    def _new(self):
        data = deepcopy(self.manager.current())
        data["name"] = "Mi tema"
        data["assets"] = dict(data.get("assets", {}))
        data["assets"].pop("theme_thumbnail", None)
        self._selected = None
        self._load(data)
        self.editor_title.setText("Crear tema")
        self.pages.setCurrentIndex(1)
        self.name.setFocus()
        self.name.selectAll()

    def _duplicate(self):
        data = self._form_data()
        default_name = f"Copia de {data['name']}".strip()
        name, accepted = QInputDialog.getText(
            self, "Duplicar tema", "Nombre para la copia:", text=default_name)
        if not accepted:
            return
        name = name.strip()
        if not name:
            QMessageBox.warning(self, "Nombre requerido", "Escribe un nombre para la copia.")
            return
        if any(theme["name"].casefold() == name.casefold() for theme in self.manager.all()):
            QMessageBox.warning(self, "El tema ya existe", "Elige un nombre que no esté en uso.")
            return
        data["name"] = name
        self._load(data)
        self.editor_title.setText(f"Duplicar tema: {name}")
        self.pages.setCurrentIndex(1)

    def _remove(self):
        if not self._selected:
            return
        if self._selected in {theme["name"] for theme in BUILTIN_THEMES}:
            QMessageBox.information(self, "Tema integrado", "Los temas integrados no se pueden eliminar.")
            return
        was_active = self.settings.get("active_theme") == self._selected
        try:
            self.manager.remove(self._selected)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "No se pudo eliminar el tema", str(exc))
            return
        self._selected = DEFAULT_THEME["name"]
        if was_active:
            theme = self.manager.current()
            self.theme_applied.emit(build_stylesheet(theme), theme["animation_duration"], theme)
        self.refresh()

    def _import(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Importar tema", "", "Temas (*.zip *.json *.qss);;Todos los archivos (*.*)")
        if not path:
            return
        staging = self.manager.directory / f"import-{uuid.uuid4().hex}"
        try:
            if path.lower().endswith(".zip"):
                with zipfile.ZipFile(path) as archive:
                    data = json.loads(archive.read("theme.json").decode("utf-8"))
                    if not isinstance(data, dict):
                        raise ValueError("El archivo theme.json debe contener un objeto de tema.")
                    theme_assets = data.get("assets", {})
                    if not isinstance(theme_assets, dict):
                        raise ValueError("Los recursos del tema deben ser un objeto de rutas.")
                    imported_assets = {}
                    for slot, member in theme_assets.items():
                        if not re.fullmatch(r"[a-zA-Z0-9_-]+", str(slot)):
                            raise ValueError(f"El identificador del recurso no es válido: {slot}")
                        if not isinstance(member, str) or not member.startswith(f"assets/{slot}."):
                            raise ValueError(f"La ruta del recurso «{slot}» no es válida.")
                        suffix = Path(member).suffix.lower()
                        if suffix not in (".svg", ".png", ".jpg", ".jpeg", ".webp"):
                            raise ValueError(f"El recurso «{slot}» tiene un formato no admitido.")
                        if member != f"assets/{slot}{suffix}":
                            raise ValueError(f"La ruta del recurso «{slot}» no es válida.")
                        info = archive.getinfo(member)
                        if info.file_size > 20 * 1024 * 1024:
                            raise ValueError(f"El recurso «{slot}» excede el límite de 20 MB.")
                        destination = staging / f"{slot}{suffix}"
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        destination.write_bytes(archive.read(member))
                        imported_assets[slot] = str(destination)
                    data["assets"] = imported_assets
            elif path.lower().endswith(".qss"):
                data = deepcopy(DEFAULT_THEME)
                data["name"] = Path(path).stem
                data["qss"] = Path(path).read_text(encoding="utf-8")
            else:
                with open(path, encoding="utf-8") as source:
                    data = json.load(source)
                if not isinstance(data, dict):
                    raise ValueError("El archivo JSON debe contener un objeto de tema.")
            data = self.manager.save(data)
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError,
                KeyError, zipfile.BadZipFile) as exc:
            QMessageBox.warning(self, "No se pudo importar el tema", str(exc))
            return
        finally:
            if staging.exists():
                shutil.rmtree(staging)
        self._selected = data["name"]
        self.refresh()

    def _export(self):
        data = next(
            (theme for theme in self.manager.all() if theme["name"] == self._selected), None)
        if data is None:
            QMessageBox.information(self, "Selecciona un tema", "Selecciona un tema para exportarlo.")
            return
        if not data["name"]:
            QMessageBox.warning(self, "Tema sin nombre", "Escribe un nombre antes de exportar.")
            return
        path, selected_filter = QFileDialog.getSaveFileName(
            self, "Exportar tema", f"{data['name']}.zip",
            "Tema completo con recursos (*.zip);;Tema JSON (*.json);;Qt Style Sheet (*.qss)")
        if not path:
            return
        try:
            if path.lower().endswith(".zip") or "completo" in selected_filter.lower():
                path = str(Path(path).with_suffix(".zip"))
                package = dict(data)
                package["assets"] = {}
                with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
                    for slot, source in data.get("assets", {}).items():
                        source_path = Path(source)
                        member = f"assets/{slot}{source_path.suffix.lower()}"
                        archive.write(source_path, member)
                        package["assets"][slot] = member
                    archive.writestr("theme.json", json.dumps(package, ensure_ascii=False, indent=2))
            elif path.lower().endswith(".qss") or "Style Sheet" in selected_filter:
                path = str(Path(path).with_suffix(".qss"))
                with open(path, "w", encoding="utf-8") as target:
                    target.write(build_stylesheet(data))
            else:
                path = str(Path(path).with_suffix(".json"))
                with open(path, "w", encoding="utf-8") as target:
                    json.dump(data, target, ensure_ascii=False, indent=2)
        except OSError as exc:
            QMessageBox.warning(self, "No se pudo exportar el tema", str(exc))
