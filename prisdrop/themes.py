"""Temas configurables y almacenamiento local."""
import json
import re
import shutil
from copy import deepcopy
from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QImageReader

from .paths import data_dir
from .theme import STYLE

DEFAULT_THEME = {
    "name": "Oscuro",
    "background": "#0f0f0f",
    "surface": "#1a1a1a",
    "text": "#f1f1f1",
    "muted": "#aaaaaa",
    "accent": "#ff0000",
    "control_background": "#272727",
    "control_hover": "#3f3f3f",
    "border_color": "#303030",
    "disabled_text": "#717171",
    "selection_background": "#1f1f1f",
    "audio_blur_radius": 24,
    "audio_overlay_color": "#000000",
    "audio_overlay_opacity": 58,
    "media_text_color": "#f1f1f1",
    "media_shadow_enabled": False,
    "media_shadow_color": "#000000",
    "media_shadow_opacity": 75,
    "media_shadow_blur": 8,
    "media_shadow_size": 2.0,
    "media_shadow_offset_x": 0.0,
    "media_shadow_offset_y": 0.0,
    "media_outline_enabled": True,
    "media_outline_color": "#5b3b73",
    "media_outline_size": 1.0,
    "media_outline_offset_x": 0.0,
    "media_outline_offset_y": 0.0,
    "audio_artwork_frame": True,
    "audio_artwork_circle": True,
    "audio_artwork_rotate": True,
    "empty_assets": [],
    "general_outline_enabled": True,
    "general_outline_color": "#5b3b73",
    "general_outline_size": 1.0,
    "general_outline_offset_x": 0.0,
    "general_outline_offset_y": 0.0,
    "general_text_bold": False,
    "font_family": "Segoe UI",
    "font_size": 13,
    "animation_duration": 180,
    "qss": "",
    "assets": {},
}
DARK_THEME = DEFAULT_THEME
DEFAULT_THEME = {
    **DARK_THEME,
    "name": "Predeterminado",
    "background": "#f3edff",
    "surface": "#ffffff",
    "text": "#321957",
    "muted": "#765d98",
    "accent": "#6c2fd3",
    "control_background": "#efe4ff",
    "control_hover": "#dfccff",
    "border_color": "#d7c4f1",
    "disabled_text": "#aa99be",
    "selection_background": "#eadcff",
    "audio_overlay_opacity": 24,
    "qss": """
QMainWindow, QWidget#root, QStackedWidget, QScrollArea, QScrollArea > QWidget > QWidget {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                stop:0 @background@, stop:1 @surface@);
    color: @text@;
}
QFrame#topbar {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                stop:0 @accent@, stop:1 @control_background@);
    border-bottom: 3px solid @border_color@;
}
QFrame#sidebar { background: @background@; border-right: 1px solid @border_color@; }
QFrame#card, QFrame#queue {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                stop:0 @surface@, stop:1 @background@);
    border: 1px solid @border_color@;
    border-radius: 18px;
}
QFrame#queue { padding: 8px; }
QLabel#title, QLabel#heading { color: @text@; }
QLabel#muted { color: @muted@; }
QPushButton {
    color: @text@;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                stop:0 @surface@, stop:1 @control_background@);
    border: 1px solid @border_color@;
    padding: 9px 16px;
    border-radius: 16px;
}
QPushButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                stop:0 @control_hover@, stop:1 @surface@);
    border-color: @accent@;
}
QPushButton:pressed { background: @selection_background@; }
QPushButton:disabled { background: @control_background@; color: @disabled_text@; }
QPushButton#nav { background: transparent; border: none; text-align: left; }
QPushButton#nav:hover { background: @selection_background@; }
QPushButton#nav:checked {
    color: @text@;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                stop:0 @selection_background@, stop:1 @control_hover@);
    font-weight: 700;
}
QPushButton#primary, QPushButton#play {
    color: #ffffff;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                stop:0 @accent@, stop:1 @control_hover@);
    border: 2px solid @surface@;
    font-weight: 700;
}
QPushButton#primary:hover, QPushButton#play:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                stop:0 @control_hover@, stop:1 @accent@);
}
QPushButton#play { border-radius: 26px; }
QPushButton#chip:checked {
    color: #ffffff;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                stop:0 @accent@, stop:1 @control_hover@);
}
QLineEdit, QPlainTextEdit, QTextEdit, QSpinBox, QDoubleSpinBox, QDateEdit, QTimeEdit {
    color: @text@; background: @surface@; border: 1px solid @border_color@;
}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus { border: 2px solid @accent@; }
QLineEdit#datePart { border-radius: 10px; padding: 6px; }
QComboBox { color: @text@; background: @control_background@; border-radius: 10px; }
QComboBox QAbstractItemView { color: @text@; background: @surface@; selection-background-color: @selection_background@; }
QProgressBar { background: @control_background@; border-radius: 4px; }
QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                stop:0 @accent@, stop:1 @control_hover@);
}
QSlider::groove:horizontal { background: @control_background@; border-radius: 3px; }
QSlider::sub-page:horizontal {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                stop:0 @accent@, stop:1 @control_hover@);
}
QSlider::handle:horizontal { background: @accent@; border: 2px solid @surface@; }
QListWidget#grid::item:hover, QListWidget#plain::item:hover { background: @background@; }
QListWidget#grid::item:selected, QListWidget#plain::item:selected {
    background: @selection_background@; color: @text@; border-radius: 12px;
}
QWidget#cover {
    background: @control_background@;
    border: 5px solid @surface@;
    border-radius: 155px;
}
QMenu, QMessageBox, QProgressDialog, QDialog {
    color: @text@; background: @surface@; border: 1px solid @border_color@;
}
QMenu::item:selected { background: @selection_background@; }
QStatusBar { color: @muted@; background: @background@; }
"""
}
CLASSIC_THEME = {
    **DEFAULT_THEME,
    "name": "2015",
    "background": "#f9f9f9",
    "surface": "#ffffff",
    "text": "#333333",
    "muted": "#666666",
    "accent": "#cc181e",
    "control_background": "#eeeeee",
    "control_hover": "#e2e2e2",
    "border_color": "#cccccc",
    "disabled_text": "#888888",
    "selection_background": "#f5d6d7",
    "audio_overlay_opacity": 58,
    "font_family": "Arial",
    "font_size": 13,
    "animation_duration": 140,
    "qss": """
QMainWindow, QWidget#root, QStackedWidget, QScrollArea, QScrollArea > QWidget > QWidget {
    background: #f9f9f9; color: #333333;
}
QFrame#topbar { background: #ffffff; border-bottom: 1px solid #cccccc; }
QFrame#sidebar { background: #f5f5f5; }
QFrame#card, QFrame#queue { background: #ffffff; border: 1px solid #dddddd; border-radius: 4px; }
QPushButton { background: #eeeeee; color: #333333; border: 1px solid #cccccc;
              border-radius: 3px; padding: 7px 12px; }
QPushButton:hover { background: #e2e2e2; }
QPushButton#nav { background: transparent; border: none; border-radius: 2px; color: #333333; }
QPushButton#nav:hover { background: #e5e5e5; }
QPushButton#nav:checked { background: #cc181e; color: rgb(255, 255, 255); font-weight: 600; }
QPushButton#primary, QPushButton#update[state="available"] {
    background: #cc181e; color: #ffffff; border: none; font-weight: 600;
}
QPushButton#primary:hover, QPushButton#update[state="available"]:hover { background: #b31217; }
QPushButton#chip:checked { background: #cc181e; color: #ffffff; border-color: #cc181e; }
QPushButton#play { background: #cc181e; color: #ffffff; }
QPushButton#play:hover { background: #b31217; }
QLineEdit { background: #ffffff; color: #333333; border: 1px solid #bbbbbb; border-radius: 3px; }
QPushButton#urlgo { background: #eeeeee; color: #333333; border: 1px solid #bbbbbb; }
QListWidget#grid, QListWidget#plain { background: #ffffff; color: #333333; }
QListWidget#grid::item:hover, QListWidget#plain::item:hover { background: #eeeeee; }
QListWidget#grid::item:selected, QListWidget#plain::item:selected { background: #f5d6d7; color: #333333; }
QSlider::sub-page:horizontal, QProgressBar::chunk { background: #cc181e; }
QScrollBar::handle:vertical, QScrollBar::handle:horizontal { background: #bbbbbb; }
QMenu, QMessageBox, QProgressDialog, QDialog { background: #ffffff; color: #333333; }
QMenu::item:selected { background: #f5d6d7; }
QStatusBar { background: #eeeeee; color: #555555; }
"""
}
WINDOWS95_THEME = {
    **DEFAULT_THEME,
    "name": "W95",
    "background": "#008080",
    "surface": "#c0c0c0",
    "text": "#000000",
    "muted": "#404040",
    "accent": "#000080",
    "control_background": "#c0c0c0",
    "control_hover": "#d4d0c8",
    "border_color": "#808080",
    "disabled_text": "#808080",
    "selection_background": "#000080",
    "audio_blur_radius": 30,
    "audio_overlay_color": "#000000",
    "audio_overlay_opacity": 48,
    "font_family": "MS Sans Serif",
    "font_size": 12,
    "animation_duration": 80,
    "qss": """
QMainWindow, QWidget#root, QStackedWidget, QScrollArea, QScrollArea > QWidget > QWidget {
    background: #008080; color: #000000;
}
QWidget#playerPage { background: transparent; }
QStackedWidget#mediaView { background: transparent; }
QFrame#topbar { background: #c0c0c0; border-bottom: 2px outset rgb(255, 255, 255); }
QFrame#sidebar, QFrame#card, QFrame#queue {
    background: #c0c0c0; border: 2px outset rgb(255, 255, 255); border-radius: 0;
}
QPushButton {
    background: #c0c0c0; color: #000000; border: 2px outset rgb(255, 255, 255);
    border-right-color: #404040; border-bottom-color: #404040;
    border-radius: 0; padding: 5px 10px;
}
QPushButton:hover { background: #d4d0c8; }
QPushButton:pressed, QPushButton#nav:checked {
    background: #000080; color: rgb(255, 255, 255); border: 2px inset #808080;
}
QPushButton#nav { background: #c0c0c0; color: #000000; border-radius: 0; text-align: left; }
QPushButton#primary, QPushButton#play { background: #c0c0c0; color: #000000; font-weight: 600; }
QPushButton#primary:hover, QPushButton#play:hover { background: #d4d0c8; }
QLineEdit, QPlainTextEdit, QTextEdit, QSpinBox, QComboBox {
    background: #ffffff; color: #000000; border: 2px inset #808080; border-radius: 0;
}
QListWidget, QListWidget#grid, QListWidget#plain {
    background: #ffffff; color: #000000; border: 2px inset #808080;
}
QListWidget::item:selected, QComboBox QAbstractItemView::item:selected {
    background: #000080; color: rgb(255, 255, 255);
}
QProgressBar { background: #ffffff; border: 2px inset #808080; }
QProgressBar::chunk, QSlider::sub-page:horizontal { background: #000080; }
QSlider::groove:horizontal { background: #808080; }
QSlider::handle:horizontal { background: #000080; border: 1px outset #ffffff; }
QScrollBar::handle:vertical, QScrollBar::handle:horizontal {
    background: #c0c0c0; border: 2px outset rgb(255, 255, 255); border-radius: 0;
}
QMenu, QMessageBox, QProgressDialog, QDialog {
    background: #c0c0c0; color: #000000; border: 2px outset #ffffff;
}
QMenu::item:selected { background: #000080; color: rgb(255, 255, 255); }
QStatusBar { background: #c0c0c0; color: #000000; border-top: 2px inset #808080; }
QWidget#playerBackdropOverlay { background-color: rgba(0, 0, 0, 122); }
"""
}

BUILTIN_THEMES = (DEFAULT_THEME, DARK_THEME, CLASSIC_THEME, WINDOWS95_THEME)

_LEGACY_THEME_NAMES = {
    "Oscuro clásico": DARK_THEME["name"],
    "YouTube clásico": CLASSIC_THEME["name"],
    "Windows 95": WINDOWS95_THEME["name"],
}


def _canonical_theme_name(name: str) -> str:
    return _LEGACY_THEME_NAMES.get(name, name)


def _base_theme(name: str) -> dict:
    name = _canonical_theme_name(name)
    return next((theme for theme in BUILTIN_THEMES if theme["name"] == name), DEFAULT_THEME)

_BASE_COLOR_REPLACEMENTS = {
    "#0f0f0f": "background",
    "#1a1a1a": "surface",
    "#141414": "surface",
    "#121212": "background",
    "#f1f1f1": "text",
    "#3ea6ff": "accent",
    "#aaaaaa": "muted",
    "#ff0000": "accent",
    "#e60000": "accent",
    "#cc0000": "accent",
    "#272727": "control_background",
    "#222222": "control_background",
    "#212121": "surface",
    "#3f3f3f": "control_hover",
    "#5a5a5a": "control_hover",
    "#303030": "border_color",
    "#717171": "disabled_text",
    "#1f1f1f": "selection_background",
    "#d9d9d9": "control_hover",
}

_CLASSIC_COLOR_REPLACEMENTS = {
    "#ffffff": "surface",
    "#f9f9f9": "background",
    "#eeeeee": "control_background",
    "#e2e2e2": "control_hover",
    "#cccccc": "border_color",
    "#bbbbbb": "border_color",
    "#888888": "disabled_text",
    "#f5d6d7": "selection_background",
    "#f5f5f5": "background",
    "#dddddd": "border_color",
    "#555555": "muted",
    "#666666": "muted",
    "#333333": "text",
    "#cc181e": "accent",
    "#b31217": "accent",
}
_WINDOWS95_COLOR_REPLACEMENTS = {
    "#008080": "background",
    "#c0c0c0": "surface",
    "#000000": "text",
    "#404040": "muted",
    "#000080": "accent",
    "#d4d0c8": "control_hover",
    "#808080": "border_color",
}


def _replace_theme_colors(stylesheet: str, replacements: dict[str, str], theme: dict) -> str:
    pattern = re.compile("|".join(re.escape(color) for color in replacements), re.IGNORECASE)
    return pattern.sub(lambda match: str(theme[replacements[match.group().lower()]]), stylesheet)


def build_stylesheet(theme: dict) -> str:
    data = {**DEFAULT_THEME, **theme}
    stylesheet = _replace_theme_colors(STYLE, _BASE_COLOR_REPLACEMENTS, data)
    stylesheet = stylesheet.replace('"Segoe UI", "Roboto", "Arial"', f'"{data["font_family"]}", "Segoe UI", "Arial"')
    stylesheet = stylesheet.replace("font-size: 13px", f'font-size: {int(data["font_size"])}px')
    qss = data.get("qss", "")
    for key, value in data.items():
        qss = qss.replace(f"@{key}@", str(value))
    if data["name"] == CLASSIC_THEME["name"]:
        qss = _replace_theme_colors(qss, _CLASSIC_COLOR_REPLACEMENTS, data)
    elif data["name"] == WINDOWS95_THEME["name"]:
        qss = _replace_theme_colors(qss, _WINDOWS95_COLOR_REPLACEMENTS, data)
        overlay = QColor(data["audio_overlay_color"])
        alpha = round(255 * int(data["audio_overlay_opacity"]) / 100)
        qss = qss.replace(
            "rgba(0, 0, 0, 122)",
            f"rgba({overlay.red()}, {overlay.green()}, {overlay.blue()}, {alpha})")
    if qss.strip():
        stylesheet += "\n\n/* Estilos avanzados del tema */\n" + qss
    return stylesheet


class ThemeManager:
    def __init__(self, settings):
        self.settings = settings
        self.directory = data_dir() / "themes"
        self.directory.mkdir(parents=True, exist_ok=True)

    def all(self) -> list[dict]:
        themes = {
            DEFAULT_THEME["name"]: deepcopy(DEFAULT_THEME),
            DARK_THEME["name"]: deepcopy(DARK_THEME),
            CLASSIC_THEME["name"]: deepcopy(CLASSIC_THEME),
            WINDOWS95_THEME["name"]: deepcopy(WINDOWS95_THEME),
        }
        saved_themes = []
        for path in self.directory.glob("*.json"):
            data = json.loads(path.read_text("utf-8"))
            if (path.stem.casefold() == "predeterminado"
                    and data.get("name") == "Predeterminado"
                    and data.get("background") == "#0f0f0f"
                    and data.get("accent") == "#ff0000"):
                data["name"] = DARK_THEME["name"]
                target = self.directory / "oscuro.json"
                suffix = 0
                while target.exists():
                    suffix += 1
                    target = self.directory / f"oscuro-anterior-{suffix}.json"
                path.replace(target)
                target.write_text(json.dumps(data, ensure_ascii=False, indent=2), "utf-8")
                if self.settings.get("active_theme") == "Predeterminado":
                    self.settings.set("active_theme", DARK_THEME["name"])
                path = target
            saved_themes.append((data, path))
        saved_themes.sort(key=lambda entry: (
            entry[0].get("name") not in _LEGACY_THEME_NAMES,
            entry[1].name,
        ))
        for entry in saved_themes:
            data = entry[0]
            data["name"] = _canonical_theme_name(data.get("name", ""))
            base = _base_theme(data.get("name", ""))
            theme = {**base, **data}
            themes[theme["name"]] = theme
        return list(themes.values())

    def current(self) -> dict:
        themes = self.all()
        selected = self.settings.get("active_theme") or DEFAULT_THEME["name"]
        canonical_name = _canonical_theme_name(selected)
        if canonical_name != selected:
            self.settings.set("active_theme", canonical_name)
            selected = canonical_name
        return next((t for t in themes if t["name"] == selected), deepcopy(DEFAULT_THEME))

    def save(self, theme: dict) -> dict:
        base = _base_theme(theme.get("name", ""))
        data = {**base, **theme}
        name = str(data["name"]).strip()
        if not name:
            raise ValueError("El tema necesita un nombre.")
        name = _canonical_theme_name(name)
        data["name"] = name
        color_keys = (
            "background", "surface", "text", "muted", "accent", "control_background",
            "control_hover", "border_color", "disabled_text", "selection_background",
            "audio_overlay_color", "media_text_color", "media_shadow_color",
            "media_outline_color", "general_outline_color",
        )
        for key in color_keys:
            if not re.fullmatch(r"#[0-9a-fA-F]{6}", str(data[key])):
                raise ValueError(f"El color «{key}» debe estar en formato #RRGGBB.")
        try:
            font_size = int(data["font_size"])
            animation_duration = int(data["animation_duration"])
            audio_blur_radius = int(data["audio_blur_radius"])
            audio_overlay_opacity = int(data["audio_overlay_opacity"])
            media_shadow_opacity = int(data["media_shadow_opacity"])
            media_shadow_blur = int(data["media_shadow_blur"])
            media_shadow_size = float(data["media_shadow_size"])
            media_outline_size = float(data["media_outline_size"])
            general_outline_size = float(data["general_outline_size"])
            media_shadow_offset_x = float(data["media_shadow_offset_x"])
            media_shadow_offset_y = float(data["media_shadow_offset_y"])
            media_outline_offset_x = float(data["media_outline_offset_x"])
            media_outline_offset_y = float(data["media_outline_offset_y"])
            general_outline_offset_x = float(data["general_outline_offset_x"])
            general_outline_offset_y = float(data["general_outline_offset_y"])
        except (TypeError, ValueError) as exc:
            raise ValueError("Los tamaños, duraciones y opacidad deben ser valores numéricos.") from exc
        if (not 9 <= font_size <= 28 or not 0 <= animation_duration <= 1200
                or not 0 <= audio_blur_radius <= 80 or not 0 <= audio_overlay_opacity <= 100
                or not 0 <= media_shadow_opacity <= 100 or not 0 <= media_shadow_blur <= 50
                or not 0 <= media_shadow_size <= 30
                or not 0 <= media_outline_size <= 10 or not 0 <= general_outline_size <= 10
                or any(not -30 <= offset <= 30 for offset in (
                    media_shadow_offset_x, media_shadow_offset_y,
                    media_outline_offset_x, media_outline_offset_y,
                    general_outline_offset_x, general_outline_offset_y,
                ))):
            raise ValueError("Un tamaño, duración, difuminado u opacidad está fuera de rango.")
        for key in (
            "media_shadow_enabled", "media_outline_enabled",
            "general_outline_enabled", "general_text_bold",
            "audio_artwork_frame", "audio_artwork_circle", "audio_artwork_rotate",
        ):
            if not isinstance(data[key], bool):
                raise ValueError(f"La opción «{key}» debe ser booleana.")
        data["name"] = name
        data["font_size"] = font_size
        data["animation_duration"] = animation_duration
        data["audio_blur_radius"] = audio_blur_radius
        data["audio_overlay_opacity"] = audio_overlay_opacity
        data["media_shadow_opacity"] = media_shadow_opacity
        data["media_shadow_blur"] = media_shadow_blur
        data["media_shadow_size"] = round(media_shadow_size, 2)
        data["media_outline_size"] = round(media_outline_size, 2)
        data["general_outline_size"] = round(general_outline_size, 2)
        data["media_shadow_offset_x"] = round(media_shadow_offset_x, 2)
        data["media_shadow_offset_y"] = round(media_shadow_offset_y, 2)
        data["media_outline_offset_x"] = round(media_outline_offset_x, 2)
        data["media_outline_offset_y"] = round(media_outline_offset_y, 2)
        data["general_outline_offset_x"] = round(general_outline_offset_x, 2)
        data["general_outline_offset_y"] = round(general_outline_offset_y, 2)
        if not isinstance(data["qss"], str):
            raise ValueError("Las reglas QSS deben ser texto.")
        slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", name).strip("-").lower() or "tema"
        assets = data.get("assets", {})
        if not isinstance(assets, dict):
            raise ValueError("Los recursos del tema deben ser una lista de rutas.")
        empty_assets = data.get("empty_assets", [])
        if (not isinstance(empty_assets, list)
                or any(not isinstance(slot, str) or not re.fullmatch(r"[a-zA-Z0-9_-]+", slot)
                       for slot in empty_assets)):
            raise ValueError("Los recursos vacíos del tema deben ser una lista de identificadores.")
        empty_assets = sorted(set(empty_assets))
        if set(assets).intersection(empty_assets):
            raise ValueError("Un recurso no puede estar personalizado y vacío al mismo tiempo.")
        asset_dir = self.directory / f"{slug}_assets"
        for slot, raw_path in list(assets.items()):
            if not re.fullmatch(r"[a-zA-Z0-9_-]+", str(slot)):
                raise ValueError(f"El identificador del recurso no es válido: {slot}")
            if not raw_path:
                assets.pop(slot)
                continue
            if not isinstance(raw_path, str):
                raise ValueError(f"La ruta del recurso «{slot}» debe ser texto.")
            source = Path(raw_path)
            if source.suffix.lower() not in (".svg", ".png", ".jpg", ".jpeg", ".webp"):
                raise ValueError(f"El recurso «{slot}» debe ser PNG, JPEG, WebP o SVG.")
            if not source.is_file():
                raise ValueError(f"No se encuentra el recurso del tema: {source}")
            asset_dir.mkdir(parents=True, exist_ok=True)
            suffix = source.suffix.lower()
            target = asset_dir / f"{slot}{suffix}"
            if suffix != ".svg":
                reader = QImageReader(str(source))
                reader.setAutoTransform(True)
                source_size = reader.size()
                if source_size.isValid() and max(source_size.width(), source_size.height()) > 512:
                    scaled_size = source_size.scaled(
                        QSize(512, 512), Qt.AspectRatioMode.KeepAspectRatio)
                    reader.setScaledSize(scaled_size)
                    image = reader.read()
                    if image.isNull():
                        raise ValueError(
                            f"No se pudo ajustar la imagen del recurso «{slot}»: "
                            f"{reader.errorString()}")
                    target = asset_dir / f"{slot}.png"
                    if not image.save(str(target), "PNG"):
                        raise OSError(f"No se pudo guardar la imagen ajustada del recurso «{slot}».")
                elif source.resolve() != target.resolve():
                    shutil.copy2(source, target)
            assets[slot] = str(target)
        data["assets"] = assets
        data["empty_assets"] = empty_assets
        path = self.directory / f"{slug}.json"
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), "utf-8")
        return data

    def remove(self, name: str) -> None:
        if name in {theme["name"] for theme in BUILTIN_THEMES}:
            raise ValueError("Los temas integrados no se pueden eliminar.")
        slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", name).strip("-").lower() or "tema"
        path = self.directory / f"{slug}.json"
        if path.exists():
            path.unlink()
        if self.settings.get("active_theme") == name:
            self.settings.set("active_theme", DEFAULT_THEME["name"])
