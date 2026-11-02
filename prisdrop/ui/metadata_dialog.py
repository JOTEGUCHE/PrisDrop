"""Editor de metadatos, letras y carátula de audio o video."""
import re
from datetime import date
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIntValidator, QPixmap
from PySide6.QtWidgets import (QDialog, QFileDialog, QFormLayout, QHBoxLayout, QLabel,
                               QLineEdit, QMessageBox, QPushButton, QTextEdit, QVBoxLayout)
from mutagen import MutagenError

from ..metadata import FIELDS, read_audio_cover, read_audio_metadata, write_audio_metadata
from .icons import svg_icon


class MetadataDialog(QDialog):
    def __init__(self, media, parent=None):
        super().__init__(parent)
        self.media = media
        self.cover_path = media.thumb if media.thumb and Path(media.thumb).exists() else None
        self.cover_data = None
        self.setWindowTitle("Editar metadatos")
        self.resize(620, 680)
        root = QVBoxLayout(self)
        form = QFormLayout()
        try:
            if media.kind == "audio":
                tags = read_audio_metadata(media.path)
                self.cover_data = read_audio_cover(media.path)
            else:
                tags = {}
        except (MutagenError, OSError, ValueError) as exc:
            QMessageBox.warning(self, "No se pudieron leer las etiquetas", str(exc))
            tags = {}
        self._date_original = str(tags.get("date", getattr(media, "date", "") or ""))
        self.fields = {}
        labels = {
            "title": "Nombre", "artist": "Autor / artista", "album": "Álbum",
            "genre": "Género", "composer": "Compositor",
            "track": "Número de pista", "comment": "Comentario",
        }
        for field in FIELDS:
            value = tags.get(field, getattr(media, field, "") or "")
            if field == "lyrics":
                self.lyrics = QTextEdit()
                self.lyrics.setPlainText(str(value))
                self.lyrics.setMinimumHeight(140)
                form.addRow("Letras", self.lyrics)
            elif field == "date":
                self.date_year = QLineEdit()
                self.date_month = QLineEdit()
                self.date_day = QLineEdit()
                self.date_year.setPlaceholderText("AAAA")
                self.date_month.setPlaceholderText("MM")
                self.date_day.setPlaceholderText("DD")
                self.date_year.setAccessibleName("Año")
                self.date_month.setAccessibleName("Mes")
                self.date_day.setAccessibleName("Día")
                self.date_year.setObjectName("datePart")
                self.date_month.setObjectName("datePart")
                self.date_day.setObjectName("datePart")
                self.date_year.setFixedSize(92, 40)
                self.date_month.setFixedSize(68, 40)
                self.date_day.setFixedSize(68, 40)
                self.date_year.setMaxLength(4)
                self.date_month.setMaxLength(2)
                self.date_day.setMaxLength(2)
                self.date_year.setValidator(QIntValidator(1, 9999, self))
                self.date_month.setValidator(QIntValidator(1, 12, self))
                self.date_day.setValidator(QIntValidator(1, 31, self))
                self._set_date_parts(value)
                self._date_initial = (
                    self.date_year.text(), self.date_month.text(), self.date_day.text())
                date_row = QHBoxLayout()
                for label, edit in (("Año", self.date_year), ("Mes", self.date_month),
                                    ("Día", self.date_day)):
                    part = QVBoxLayout()
                    part.addWidget(QLabel(label))
                    edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    part.addWidget(edit)
                    date_row.addLayout(part)
                date_row.addStretch(1)
                form.addRow("Fecha", date_row)
            else:
                edit = QLineEdit(str(value))
                self.fields[field] = edit
                form.addRow(labels[field], edit)
        root.addLayout(form)

        cover_row = QHBoxLayout()
        self.cover_preview = QLabel()
        self.cover_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cover_preview.setFixedSize(120, 120)
        self._show_cover()
        cover_row.addWidget(self.cover_preview)
        cover_buttons = QVBoxLayout()
        self.btn_cover = QPushButton("Cambiar carátula…")
        self.btn_remove_cover = QPushButton("Quitar carátula")
        self.btn_cover.clicked.connect(self._pick_cover)
        self.btn_remove_cover.clicked.connect(self._remove_cover)
        cover_buttons.addWidget(self.btn_cover)
        cover_buttons.addWidget(self.btn_remove_cover)
        cover_buttons.addStretch(1)
        cover_row.addLayout(cover_buttons)
        cover_row.addStretch(1)
        root.addLayout(cover_row)

        lyric_row = QHBoxLayout()
        self.btn_import_lyrics = QPushButton("Importar letras…")
        self.btn_export_lyrics = QPushButton("Exportar letras…")
        self.btn_import_lyrics.clicked.connect(self._import_lyrics)
        self.btn_export_lyrics.clicked.connect(self._export_lyrics)
        lyric_row.addWidget(self.btn_import_lyrics)
        lyric_row.addWidget(self.btn_export_lyrics)
        lyric_row.addStretch(1)
        root.addLayout(lyric_row)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = QPushButton("Cancelar")
        save = QPushButton("Guardar")
        save.setObjectName("primary")
        cancel.clicked.connect(self.reject)
        save.clicked.connect(self._save)
        buttons.addWidget(cancel)
        buttons.addWidget(save)
        root.addLayout(buttons)

    def values(self):
        return {key: edit.text().strip() for key, edit in self.fields.items()} | {
            "date": self._date_value(),
            "lyrics": self.lyrics.toPlainText()
        }

    def _set_date_parts(self, value):
        raw = str(value or "").strip()
        match = re.match(r"^(\d{4})(?:[-/.]?(\d{2}))?(?:[-/.]?(\d{2}))?", raw)
        if match:
            year, month, day = match.groups()
            self.date_year.setText(year or "")
            self.date_month.setText(month or "")
            self.date_day.setText(day or "")

    def _date_value(self):
        year = self.date_year.text().strip()
        month = self.date_month.text().strip()
        day = self.date_day.text().strip()
        if (year, month, day) == self._date_initial:
            return self._date_original
        if not year and not month and not day:
            return ""
        if not year or (day and not month):
            raise ValueError("Indica el año y completa mes y día en orden.")
        if not 1 <= int(year) <= 9999:
            raise ValueError("El año debe estar entre 1 y 9999.")
        if month and not 1 <= int(month) <= 12:
            raise ValueError("El mes debe estar entre 1 y 12.")
        if day:
            try:
                date(int(year), int(month), int(day))
            except ValueError as exc:
                raise ValueError("La fecha no es válida.") from exc
            return f"{int(year):04d}{int(month):02d}{int(day):02d}"
        if month:
            return f"{int(year):04d}{int(month):02d}"
        return f"{int(year):04d}"

    def _show_cover(self):
        pixmap = QPixmap(self.cover_path) if self.cover_path else QPixmap()
        if pixmap.isNull() and self.cover_data:
            pixmap.loadFromData(self.cover_data)
        if pixmap.isNull():
            self.cover_preview.setPixmap(svg_icon("music", "#aaaaaa", 48).pixmap(48))
        else:
            self.cover_preview.setText("")
            self.cover_preview.setPixmap(
                pixmap.scaled(112, 112, Qt.AspectRatioMode.KeepAspectRatio,
                              Qt.TransformationMode.SmoothTransformation))

    def _pick_cover(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Elige la carátula", "", "Imágenes (*.png *.jpg *.jpeg)")
        if path:
            self.cover_path = path
            self.cover_data = None
            self._show_cover()

    def _remove_cover(self):
        self.cover_path = ""
        self.cover_data = None
        self._show_cover()

    def _import_lyrics(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Importar letras", "", "Letras (*.lrc *.txt *.srt);;Todos los archivos (*.*)")
        if not path:
            return
        try:
            self.lyrics.setPlainText(Path(path).read_text("utf-8-sig"))
        except (OSError, UnicodeError) as exc:
            QMessageBox.warning(self, "No se pudieron importar las letras", str(exc))

    def _export_lyrics(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Exportar letras", f"{Path(self.media.path).stem}.lrc",
            "Letras con tiempo (*.lrc);;Texto plano (*.txt);;Subtítulos (*.srt)")
        if not path:
            return
        try:
            Path(path).write_text(self.lyrics.toPlainText(), encoding="utf-8")
        except OSError as exc:
            QMessageBox.warning(self, "No se pudieron exportar las letras", str(exc))

    def _save(self):
        try:
            values = self.values()
            if self.media.kind == "audio":
                write_audio_metadata(self.media.path, values, self.cover_path)
        except (MutagenError, OSError, ValueError, TypeError) as exc:
            QMessageBox.warning(self, "No se pudieron guardar los metadatos", str(exc))
            return
        self.accept()
