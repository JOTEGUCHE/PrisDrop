"""Visor de la licencia del proyecto, dependencias y aviso legal."""
import sys
from pathlib import Path

from PySide6.QtWidgets import QDialog, QMessageBox, QPushButton, QTabWidget, QTextEdit, QVBoxLayout


def _resource_path(filename: str) -> Path:
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        return Path(bundle_root) / filename
    return Path(__file__).resolve().parents[2] / filename


class LegalInfoDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Licencias, términos y condiciones")
        self.resize(760, 560)

        tabs = QTabWidget()
        for filename, title in (
            ("LICENSE", "Licencia del proyecto"),
            ("NOTICES.txt", "Licencias de dependencias"),
            ("LEGAL_DISCLAIMER.txt", "Aviso legal"),
        ):
            editor = QTextEdit()
            editor.setReadOnly(True)
            path = _resource_path(filename)
            try:
                editor.setPlainText(path.read_text(encoding="utf-8"))
            except OSError as error:
                editor.setPlainText(f"No se pudo leer el archivo:\n{path}\n\n{error}")
                QMessageBox.warning(
                    self, "No se pudo cargar un documento legal",
                    f"No se pudo leer {filename}:\n{path}\n\n{error}")
            tabs.addTab(editor, title)

        close_button = QPushButton("Cerrar")
        close_button.clicked.connect(self.accept)
        layout = QVBoxLayout(self)
        layout.addWidget(tabs)
        layout.addWidget(close_button)
