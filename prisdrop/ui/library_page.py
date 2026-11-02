"""Biblioteca local de videos y música descargados."""
import os
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QIcon, QPixmap
from PySide6.QtWidgets import (QButtonGroup, QHBoxLayout, QLabel, QLineEdit, QListWidget,
                               QListWidgetItem, QMenu, QMessageBox, QPushButton, QFileDialog,
                               QVBoxLayout, QWidget)

from ..library import Library, pretty_date
from ..paths import legacy_media_dirs
from ..settings import Settings
from ..workers import LibraryScanWorker
from .icons import bind_icon
from .widgets import fmt_duration, rounded_pixmap

BATCH = 24      # elementos que se agregan por vuelta para no congelar la ventana


class LibraryPage(QWidget):
    play_requested = Signal(list, int)      # elementos visibles, índice a reproducir
    enqueue_requested = Signal(list)
    refreshed = Signal(list)                # toda la biblioteca (para las recomendaciones)
    busy_changed = Signal(bool)

    def __init__(self, settings: Settings, library: Library):
        super().__init__()
        self.settings = settings
        self.library = library
        self._all = []
        self._shown = []
        self._icons = {}
        self._scanner = None
        self._rescan = False
        self._busy = False
        self._gen = 0
        self._pos = 0

        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 22, 28, 12)
        lay.setSpacing(14)

        top = QHBoxLayout()
        self._kind = None
        grp = QButtonGroup(self)
        grp.setExclusive(True)
        for text, kind in (("Todo", None), ("Videos", "video"), ("Música", "audio")):
            b = QPushButton(text)
            b.setObjectName("chip")
            b.setCheckable(True)
            b.setChecked(kind is None)
            b.clicked.connect(lambda _=False, k=kind: self._set_kind(k))
            grp.addButton(b)
            top.addWidget(b)
        top.addSpacing(12)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Buscar en tu biblioteca")
        self.search.setMaximumWidth(340)
        self.search.textChanged.connect(self._apply_filter)
        top.addWidget(self.search)
        top.addStretch(1)
        self.lbl_count = QLabel()
        self.lbl_count.setObjectName("muted")
        top.addWidget(self.lbl_count)
        self.btn_metadata = QPushButton("Editar metadatos")
        self.btn_metadata.setEnabled(False)
        self.btn_metadata.clicked.connect(self._edit_current_metadata)
        top.addWidget(self.btn_metadata)
        btn_all = QPushButton("Reproducir todo")
        bind_icon(btn_all, "action_play", "play")
        btn_all.clicked.connect(self._play_all)
        top.addWidget(btn_all)
        lay.addLayout(top)

        self.list = QListWidget()
        self.list.setObjectName("grid")
        self.list.setViewMode(QListWidget.ViewMode.IconMode)
        self.list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.list.setMovement(QListWidget.Movement.Static)
        self.list.setIconSize(QSize(240, 135))
        self.list.setGridSize(QSize(266, 222))
        self.list.setSpacing(6)
        self.list.setWordWrap(True)
        self.list.setUniformItemSizes(True)
        self.list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self._menu)
        self.list.currentItemChanged.connect(self._selection_changed)
        self.list.itemDoubleClicked.connect(lambda it: self._play(self.list.row(it)))
        lay.addWidget(self.list, 1)

        self.empty = QLabel("Aún no hay nada aquí.\nDescarga un video o una canción y aparecerá en tu biblioteca.")
        self.empty.setObjectName("muted")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self.empty)

    # ------------------------------------------------------------- estado «ocupado»
    def _begin_busy(self):
        if not self._busy:
            self._busy = True
            self.busy_changed.emit(True)

    def _end_busy(self):
        if self._busy:
            self._busy = False
            self.busy_changed.emit(False)

    # ------------------------------------------------------------------ carga
    def refresh(self):
        """Escanea las carpetas en un hilo y luego rellena la lista por tandas."""
        if self._scanner is not None and self._scanner.isRunning():
            self._rescan = True
            return
        self._begin_busy()
        folders = [self.settings.get("video_dir"), self.settings.get("audio_dir")]
        folders.extend(str(folder) for folder in legacy_media_dirs() if folder.is_dir())
        w = LibraryScanWorker(self.library, folders)
        w.done.connect(self._on_scanned)
        w.finished.connect(self._scan_thread_finished)
        self._scanner = w
        w.start()

    def _scan_thread_finished(self):
        self._scanner = None
        if self._rescan:
            self._rescan = False
            self.refresh()

    def _on_scanned(self, items):
        self._all = items
        self.refreshed.emit(items)
        self._apply_filter()

    def _set_kind(self, kind):
        self._kind = kind
        self._apply_filter()

    def _apply_filter(self, *_):
        q = self.search.text().strip().lower()
        self._shown = [i for i in self._all
                       if (self._kind is None or i.kind == self._kind)
                       and (not q or q in f"{i.title} {i.artist}".lower())]
        self._gen += 1
        self._pos = 0
        self.list.clear()
        self.lbl_count.setText(f"{len(self._shown)} elemento(s)")
        self.empty.setVisible(not self._shown)
        self.list.setVisible(bool(self._shown))
        if self._shown:
            self._fill_batch(self._gen)
        else:
            self._end_busy()

    def _fill_batch(self, gen: int):
        if gen != self._gen:
            return
        end = min(self._pos + BATCH, len(self._shown))
        for idx in range(self._pos, end):
            self.list.addItem(self._make_item(self._shown[idx]))
        self._pos = end
        if end < len(self._shown):
            QTimer.singleShot(0, lambda g=gen: self._fill_batch(g))
        else:
            self._end_busy()

    def _icon_for(self, it) -> QIcon:
        key = (it.thumb, it.kind)
        icon = self._icons.get(key)
        if icon is None:
            pix = QPixmap(it.thumb) if it.thumb else QPixmap()
            icon = QIcon(rounded_pixmap(pix, 240, 135, 12, "▶" if it.kind == "video" else "♪"))
            self._icons[key] = icon
        return icon

    def _make_item(self, it) -> QListWidgetItem:
        meta = "  ·  ".join(x for x in (it.artist, pretty_date(it.date)) if x)
        dur = f"  [{fmt_duration(it.duration)}]" if it.duration else ""
        li = QListWidgetItem(self._icon_for(it), f"{it.title}{dur}\n{meta}")
        li.setToolTip(it.path)
        li.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        return li

    # ----------------------------------------------------------- acciones
    def _play(self, row: int):
        if 0 <= row < len(self._shown):
            self.play_requested.emit(list(self._shown), row)

    def _play_all(self):
        if self._shown:
            self.play_requested.emit(list(self._shown), 0)

    def _selection_changed(self, current, _previous):
        row = self.list.row(current) if current else -1
        self.btn_metadata.setEnabled(0 <= row < len(self._shown))

    def _edit_current_metadata(self):
        row = self.list.currentRow()
        if 0 <= row < len(self._shown):
            self._edit_metadata(self._shown[row])

    def _edit_metadata(self, media):
        from .metadata_dialog import MetadataDialog

        dialog = MetadataDialog(media, self)
        if dialog.exec() != MetadataDialog.DialogCode.Accepted:
            return
        values = dialog.values()
        cover = Path(media.path).with_suffix(".jpg")
        if dialog.cover_path:
            pixmap = QPixmap(dialog.cover_path)
            if pixmap.isNull():
                QMessageBox.warning(self, "Carátula no válida", "No se pudo leer la imagen seleccionada.")
                return
            pixmap = pixmap.scaled(640, 640, Qt.AspectRatioMode.KeepAspectRatio,
                                   Qt.TransformationMode.SmoothTransformation)
            if not pixmap.save(str(cover), "JPG", 90):
                QMessageBox.warning(self, "No se pudo guardar la carátula", str(cover))
                return
            thumb = str(cover)
        else:
            try:
                cover.unlink(missing_ok=True)
            except OSError as exc:
                QMessageBox.warning(self, "No se pudo quitar la carátula", str(exc))
                return
            thumb = ""
        try:
            self.library.update_metadata(media.path, values, thumb)
        except OSError as exc:
            QMessageBox.warning(self, "No se pudieron guardar los metadatos", str(exc))
            return
        media.title = values["title"] or Path(media.path).stem
        media.artist = values["artist"]
        media.album = values["album"]
        media.date = values["date"]
        media.genre = values["genre"]
        media.lyrics = values["lyrics"]
        media.composer = values["composer"]
        media.comment = values["comment"]
        media.thumb = thumb
        self._icons.clear()
        self._apply_filter()
        self.refreshed.emit(self._all)

    def _edit_cover(self, media, remove=False):
        target = Path(media.path).with_name(f"{Path(media.path).stem}.cover.jpg")
        if remove:
            try:
                target.unlink(missing_ok=True)
                self.library.update_metadata(media.path, {
                    "title": media.title, "artist": media.artist, "album": media.album,
                    "date": media.date, "genre": media.genre, "lyrics": media.lyrics,
                })
            except OSError as exc:
                QMessageBox.warning(self, "No se pudo quitar la carátula", str(exc))
                return
            media.thumb = ""
        else:
            path, _ = QFileDialog.getOpenFileName(
                self, "Elige la carátula", "", "Imágenes (*.png *.jpg *.jpeg)")
            if not path:
                return
            pixmap = QPixmap(path)
            if pixmap.isNull():
                QMessageBox.warning(self, "Carátula no válida", "No se pudo leer la imagen seleccionada.")
                return
            pixmap = pixmap.scaled(640, 640, Qt.AspectRatioMode.KeepAspectRatio,
                                   Qt.TransformationMode.SmoothTransformation)
            if not pixmap.save(str(target), "JPG", 90):
                QMessageBox.warning(self, "No se pudo guardar la carátula", str(target))
                return
            try:
                self.library.update_metadata(media.path, {
                    "title": media.title, "artist": media.artist, "album": media.album,
                    "date": media.date, "genre": media.genre, "lyrics": media.lyrics,
                }, str(target))
            except OSError as exc:
                QMessageBox.warning(self, "No se pudo guardar la carátula", str(exc))
                return
            media.thumb = str(target)
        self._icons.clear()
        self._apply_filter()
        self.refreshed.emit(self._all)

    def _menu(self, pos):
        item = self.list.itemAt(pos)
        if not item:
            return
        row = self.list.row(item)
        media = self._shown[row]
        m = QMenu(self)
        a_play = m.addAction("Reproducir")
        a_queue = m.addAction("Añadir a la cola")
        a_metadata = m.addAction("Editar metadatos…")
        a_cover = m.addAction("Cambiar carátula…") if media.kind == "video" else None
        a_remove_cover = m.addAction("Quitar carátula") if media.kind == "video" else None
        a_open = m.addAction("Mostrar en la carpeta")
        m.addSeparator()
        a_del = m.addAction("Eliminar del disco…")
        chosen = m.exec(self.list.viewport().mapToGlobal(pos))
        if chosen == a_play:
            self._play(row)
        elif chosen == a_queue:
            self.enqueue_requested.emit([media])
        elif chosen is a_metadata:
            self._edit_metadata(media)
        elif chosen is a_cover:
            self._edit_cover(media)
        elif chosen is a_remove_cover:
            self._edit_cover(media, remove=True)
        elif chosen == a_open:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(media.path).parent)))
        elif chosen == a_del:
            ok = QMessageBox.question(self, "Eliminar", f"¿Eliminar este archivo del disco?\n\n{media.path}")
            if ok == QMessageBox.StandardButton.Yes:
                for p in (media.path, media.thumb):
                    try:
                        if p:
                            os.remove(p)
                    except OSError:
                        pass
                self.refresh()
