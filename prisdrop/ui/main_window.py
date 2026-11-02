"""Ventana principal de PrisDrop."""
from PySide6.QtCore import QPropertyAnimation, Qt, QTimer
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtWidgets import (QButtonGroup, QFrame, QGraphicsOpacityEffect, QHBoxLayout, QLineEdit,
                               QApplication, QMainWindow, QMessageBox, QProgressDialog, QPushButton,
                               QStackedWidget, QVBoxLayout, QWidget)

from .. import tools
from ..library import Library
from ..settings import Settings
from ..themes import ThemeManager, build_stylesheet
from ..workers import SetupWorker, UpdateWorker, VersionWorker
from .download_page import DownloadPage
from .legal_info_dialog import LegalInfoDialog
from .library_page import LibraryPage
from .pages_page import PagesPage
from .player_page import PlayerPage
from .settings_page import SettingsPage
from .themes_page import ThemesPage
from .icons import apply_theme_assets, bind_icon
from .text_effects import apply_general_text_outline
from .widgets import BusyOverlay, Logo, app_icon_path

PAGE_DOWNLOAD, PAGE_LIBRARY, PAGE_PLAYER, PAGE_PAGES, PAGE_THEMES, PAGE_SETTINGS = range(6)

PLACEHOLDER_MEDIA = "Pega aquí el enlace de YouTube (video, canción o playlist)"
PLACEHOLDER_PAGES = "Pega aquí el enlace de una página web (por ejemplo https://…)"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PrisDrop")
        self.resize(1280, 820)
        self.setMinimumSize(1020, 660)

        self.settings = Settings()
        self.theme_manager = ThemeManager(self.settings)
        current_theme = self.theme_manager.current()
        self._animation_duration = int(current_theme["animation_duration"])
        app = QApplication.instance()
        if app:
            app.setStyleSheet(build_stylesheet(current_theme))
            self._set_theme_properties(app, current_theme)
        self.setWindowIcon(QIcon(str(app_icon_path())))
        self.library = Library()
        self._update_state = "checking"
        self._pages_mode = False
        self._prev_index = 0
        self._setup_worker = None
        self._version_worker = None
        self._update_worker = None
        self._page_animation = None
        self._page_animation_page = None
        self._page_animation_effect = None

        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        v = QVBoxLayout(root)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        v.addWidget(self._build_topbar())

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        body.addWidget(self._build_sidebar())
        self.stack = QStackedWidget()
        body.addWidget(self.stack, 1)
        v.addLayout(body, 1)

        self.download_page = DownloadPage(self.settings, self.library)
        self.library_page = LibraryPage(self.settings, self.library)
        self.player_page = PlayerPage(self.settings)
        self.pages_page = PagesPage(self.settings)
        self.themes_page = ThemesPage(self.settings, self.theme_manager)
        self.settings_page = SettingsPage(self.settings)
        for page in (self.download_page, self.library_page, self.player_page,
                     self.pages_page, self.themes_page, self.settings_page):
            self.stack.addWidget(page)

        # capa «Cargando…» (solo aparece si una acción tarda más de ~1 s)
        self.busy = BusyOverlay(root, delay_ms=1000)

        self.download_page.library_changed.connect(self.library_page.refresh)
        self.download_page.status_message.connect(self._status)
        self.download_page.busy_changed.connect(self._set_busy)
        self.library_page.busy_changed.connect(self._set_busy)
        self.library_page.refreshed.connect(self.player_page.set_library)
        self.library_page.play_requested.connect(self._play)
        self.library_page.enqueue_requested.connect(self._enqueue)
        self.settings_page.folders_changed.connect(self._folders_changed)
        self.settings_page.repair_requested.connect(lambda: self.ensure_tools(force=True))
        self.themes_page.theme_applied.connect(self._apply_theme)
        self.stack.currentChanged.connect(self._page_changed)
        self._apply_theme(build_stylesheet(current_theme), self._animation_duration, current_theme)
        self._legal_info_button = QPushButton("❕")
        self._legal_info_button.setToolTip("Licencias, términos y condiciones")
        self._legal_info_button.setAccessibleName("Información legal y licencias")
        self._legal_info_button.setFixedSize(34, 28)
        self._legal_info_button.clicked.connect(self._show_legal_information)
        self.statusBar().addPermanentWidget(self._legal_info_button)
        self.statusBar().showMessage("Listo")

        self.library_page.refresh()
        QTimer.singleShot(250, self.ensure_tools)

    # ------------------------------------------------------------ construcción
    def _build_topbar(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("topbar")
        bar.setFixedHeight(62)
        h = QHBoxLayout(bar)
        h.setContentsMargins(18, 0, 18, 0)
        self.logo = Logo()
        h.addWidget(self.logo)
        h.addStretch(1)

        self.url = QLineEdit()
        self.url.setObjectName("urlbar")
        self.url.setPlaceholderText(PLACEHOLDER_MEDIA)
        self.url.setMinimumWidth(420)
        self.url.setMaximumWidth(680)
        self.url.returnPressed.connect(self._submit)
        self.btn_go = QPushButton("Analizar")
        self.btn_go.setObjectName("urlgo")
        self.btn_go.clicked.connect(self._submit)
        self.btn_add = QPushButton("＋  Agregar a páginas")
        self.btn_add.clicked.connect(self._add_page)
        self.btn_add.hide()
        btn_paste = QPushButton("Pegar")
        btn_paste.clicked.connect(self._paste)
        h.addWidget(self.url, 3)
        h.addWidget(self.btn_go)
        h.addSpacing(8)
        h.addWidget(btn_paste)
        h.addWidget(self.btn_add)
        h.addStretch(1)

        self.btn_update = QPushButton("Comprobando yt-dlp…")
        self.btn_update.setObjectName("update")
        self.btn_update.clicked.connect(self.on_update_clicked)
        h.addWidget(self.btn_update)
        return bar

    def _build_sidebar(self) -> QFrame:
        side = QFrame()
        side.setObjectName("sidebar")
        side.setFixedWidth(200)
        v = QVBoxLayout(side)
        v.setContentsMargins(12, 14, 12, 14)
        v.setSpacing(4)
        self.nav = []
        grp = QButtonGroup(self)
        grp.setExclusive(True)
        labels = ("Descargar", "Biblioteca", "Reproductor", "Páginas", "Temas", "Ajustes")
        icon_keys = ("download", "library", "player", "pages", "themes", "settings")
        icon_slots = ("nav_download", "nav_library", "nav_player", "nav_pages",
                      "nav_themes", "nav_settings")
        for i, text in enumerate(labels):
            b = QPushButton(text)
            b.setObjectName("nav")
            bind_icon(b, icon_slots[i], icon_keys[i], 18)
            b.setCheckable(True)
            b.clicked.connect(lambda _=False, idx=i: self.nav_to(idx))
            grp.addButton(b)
            v.addWidget(b)
            self.nav.append(b)
        self.nav[0].setChecked(True)
        v.addStretch(1)
        return side

    # -------------------------------------------------------------- navegación
    def nav_to(self, index: int):
        self.stack.setCurrentIndex(index)
        self.nav[index].setChecked(True)

    def _page_changed(self, index: int):
        if self._prev_index == PAGE_PLAYER and index != PAGE_PLAYER:
            self.player_page.pause_if_video()
        self._prev_index = index
        pages_mode = index == PAGE_PAGES
        if pages_mode != self._pages_mode:
            self._pages_mode = pages_mode
            self.url.clear()
            self.url.setPlaceholderText(PLACEHOLDER_PAGES if pages_mode else PLACEHOLDER_MEDIA)
            self.btn_go.setText("Abrir" if pages_mode else "Analizar")
            self.btn_add.setVisible(pages_mode)
        if index == PAGE_LIBRARY:
            self.library_page.refresh()
        elif index == PAGE_THEMES:
            self.themes_page.refresh()
        elif index == PAGE_SETTINGS:
            self.settings_page.refresh_tools()
        self._apply_text_effects()
        self._finish_page_animation()
        if index != PAGE_PLAYER and self._animation_duration > 0:
            page = self.stack.widget(index)
            effect = QGraphicsOpacityEffect(page)
            page.setGraphicsEffect(effect)
            animation = QPropertyAnimation(effect, b"opacity", self)
            animation.setDuration(self._animation_duration)
            animation.setStartValue(0.0)
            animation.setEndValue(1.0)
            self._page_animation = animation
            self._page_animation_page = page
            self._page_animation_effect = effect
            animation.finished.connect(self._finish_page_animation)
            animation.start()

    def _finish_page_animation(self):
        animation = self._page_animation
        page = self._page_animation_page
        effect = self._page_animation_effect
        self._page_animation = None
        self._page_animation_page = None
        self._page_animation_effect = None
        if animation is not None and animation.state() == QPropertyAnimation.State.Running:
            animation.stop()
        if page is not None and page.graphicsEffect() is effect:
            page.setGraphicsEffect(None)
        if animation is not None:
            animation.deleteLater()

    def _apply_theme(self, stylesheet: str, duration: int, theme: dict):
        app = QApplication.instance()
        if app:
            app.setStyleSheet(stylesheet)
            self._set_theme_properties(app, theme)
            app.setProperty("theme_assets", theme.get("assets", {}))
            app.setProperty("theme_empty_assets", theme.get("empty_assets", []))
            apply_theme_assets(theme)
        self.logo.apply_theme(theme)
        app_icon = ("" if "app_icon" in theme.get("empty_assets", [])
                    else theme.get("assets", {}).get("app_icon", str(app_icon_path())))
        self.setWindowIcon(QIcon(app_icon))
        if hasattr(self, "player_page"):
            self.player_page._update_player_backdrop()
            self._apply_text_effects()
        self._animation_duration = duration

    def _apply_text_effects(self):
        apply_general_text_outline(QApplication.instance())
        if hasattr(self, "player_page"):
            self.player_page.apply_media_text_theme()

    @staticmethod
    def _set_theme_properties(app, theme: dict):
        app.setProperty("theme_name", theme["name"])
        for key in ("background", "surface", "text", "muted", "accent",
                    "audio_blur_radius", "audio_overlay_color", "audio_overlay_opacity",
                    "media_text_color", "media_shadow_enabled", "media_shadow_color",
                    "media_shadow_opacity", "media_shadow_blur", "media_shadow_size",
                    "media_shadow_offset_x", "media_shadow_offset_y",
                    "media_outline_enabled", "media_outline_color", "media_outline_size",
                    "media_outline_offset_x", "media_outline_offset_y",
                    "audio_artwork_frame", "audio_artwork_circle", "audio_artwork_rotate",
                    "general_outline_enabled", "general_outline_color", "general_outline_size",
                    "general_outline_offset_x", "general_outline_offset_y",
                    "general_text_bold"):
            app.setProperty(f"theme_{key}", theme[key])

    def _folders_changed(self):
        self.download_page.refresh_destination()
        self.library_page.refresh()

    def _status(self, msg: str):
        first = msg.strip().splitlines()[0] if msg.strip() else ""
        self.statusBar().showMessage(first, 6000)

    def _show_legal_information(self):
        LegalInfoDialog(self).exec()

    def _set_busy(self, on: bool):
        self.busy.start() if on else self.busy.stop()

    def _paste(self):
        text = QGuiApplication.clipboard().text().strip()
        if not text:
            return
        self.url.setText(text)
        if not self._pages_mode:
            self._submit()

    def _submit(self):
        text = self.url.text().strip()
        if not text:
            return
        if self._pages_mode:
            self.pages_page.open_url(text)
        else:
            self.nav_to(PAGE_DOWNLOAD)
            self.download_page.analyze(text)

    def _add_page(self):
        self._status(self.pages_page.add_page(self.url.text()))

    def _play(self, items, index):
        self.player_page.set_queue(items, index)
        self.nav_to(PAGE_PLAYER)

    def _enqueue(self, items):
        self.player_page.enqueue(items)
        self.statusBar().showMessage("Añadido a la cola de reproducción.", 4000)

    # --------------------------------------------------- herramientas (1.er inicio)
    def ensure_tools(self, force: bool = False):
        if not force and tools.ytdlp_path() and tools.ffmpeg_dir() and tools.deno_path():
            self.check_updates()
            return
        dlg = QProgressDialog("Preparando PrisDrop…", None, 0, 100, self)
        dlg.setWindowTitle("PrisDrop")
        dlg.setWindowModality(Qt.WindowModality.ApplicationModal)
        dlg.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, False)
        dlg.setMinimumDuration(0)
        dlg.setAutoClose(False)
        dlg.setAutoReset(False)
        dlg.setMinimumWidth(420)
        dlg.show()

        w = SetupWorker(force=force)

        def on_progress(msg: str, pct: int):
            dlg.setLabelText(msg)
            if pct < 0:
                dlg.setRange(0, 0)
            else:
                dlg.setRange(0, 100)
                dlg.setValue(pct)

        def on_done():
            dlg.close()
            self.settings_page.refresh_tools()
            self.check_updates()

        def on_failed(msg: str):
            dlg.close()
            self.settings_page.refresh_tools()
            self.check_updates()
            QMessageBox.warning(
                self, "PrisDrop",
                f"No se pudieron preparar las herramientas:\n\n{msg}\n\n"
                "Revisa tu conexión a internet. Se reintentará al abrir la app o desde Ajustes.")

        w.progress.connect(on_progress)
        w.done.connect(on_done)
        w.failed.connect(on_failed)
        self._setup_worker = w
        w.start()

    # ---------------------------------------------------------- botón actualizar
    def _set_update_btn(self, text: str, enabled: bool, state: str, tip: str = ""):
        self._update_state = state
        self.btn_update.setText(text)
        self.btn_update.setEnabled(enabled)
        self.btn_update.setToolTip(tip)
        self.btn_update.setProperty("state", state)
        self.btn_update.style().unpolish(self.btn_update)
        self.btn_update.style().polish(self.btn_update)

    def check_updates(self):
        if self._version_worker is not None and self._version_worker.isRunning():
            return
        self._set_update_btn("Comprobando yt-dlp…", False, "checking")
        w = VersionWorker()
        w.result.connect(self._on_version)
        self._version_worker = w
        w.start()

    def _on_version(self, local, latest, err):
        self.settings_page.set_version(local)
        if local is None:
            self._set_update_btn("Instalar yt-dlp", True, "install", "yt-dlp no está instalado todavía.")
        elif latest is None:
            self._set_update_btn(f"yt-dlp {local} · reintentar", True, "retry",
                                 f"No se pudo comprobar la última versión: {err}")
        elif tools.is_up_to_date(local, latest):
            self._set_update_btn(f"✓ yt-dlp actualizado ({local})", False, "uptodate",
                                 "Ya tienes la última versión de yt-dlp.")
        else:
            self._set_update_btn(f"Actualizar yt-dlp  ({local} → {latest})", True, "available",
                                 "Hay una versión nueva de yt-dlp disponible.")

    def on_update_clicked(self):
        if self._update_state == "retry":
            self.check_updates()
            return
        if self._update_state == "install":
            self.ensure_tools()
            return
        if self.download_page.active_count():
            QMessageBox.information(self, "PrisDrop",
                                    "Espera a que terminen las descargas para actualizar yt-dlp.")
            return
        self._set_update_btn("Actualizando… 0%", False, "busy")
        w = UpdateWorker()
        w.progress.connect(lambda p: self.btn_update.setText(f"Actualizando… {p}%"))
        w.done.connect(lambda _v: self.check_updates())
        w.failed.connect(self._on_update_failed)
        self._update_worker = w
        w.start()

    def _on_update_failed(self, msg: str):
        self.check_updates()
        QMessageBox.warning(self, "PrisDrop", f"No se pudo actualizar yt-dlp:\n\n{msg}")

    # ------------------------------------------------------------------ cierre
    def closeEvent(self, event):
        if self.download_page.active_count():
            ans = QMessageBox.question(self, "PrisDrop",
                                       "Hay descargas en curso. ¿Cancelarlas y salir?")
            if ans != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
        self.download_page.shutdown()
        self.player_page.shutdown()
        self.pages_page.shutdown()
        for w in (self._setup_worker, self._version_worker, self._update_worker):
            if w is not None and w.isRunning():
                w.wait(3000)
        event.accept()
