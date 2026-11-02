"""Tema oscuro inspirado en YouTube."""

STYLE = """
* { font-family: "Segoe UI", "Roboto", "Arial"; font-size: 13px; color: #f1f1f1; }
QMainWindow, QWidget#root, QStackedWidget, QScrollArea, QScrollArea > QWidget > QWidget { background: #0f0f0f; }
QScrollArea { border: none; }

QFrame#topbar { background: #0f0f0f; border-bottom: 1px solid #272727; }
QFrame#sidebar { background: #0f0f0f; }
QFrame#card { background: #1a1a1a; border-radius: 14px; }
QFrame#queue { background: #141414; border-radius: 14px; }

QLabel#muted { color: #aaaaaa; }
QLabel#title { font-size: 20px; font-weight: 600; }
QLabel#heading { font-size: 16px; font-weight: 600; }

QPushButton { background: #272727; border: none; padding: 8px 16px; border-radius: 18px; }
QPushButton:hover { background: #3f3f3f; }
QPushButton:disabled { background: #1a1a1a; color: #717171; }

QPushButton#nav { text-align: left; padding: 10px 14px; border-radius: 10px;
                  background: transparent; font-size: 14px; }
QPushButton#nav:hover { background: #272727; }
QPushButton#nav:checked { background: #272727; font-weight: 600; }

QPushButton#primary { background: #f1f1f1; color: #0f0f0f; font-weight: 600; padding: 10px 22px; }
QPushButton#primary:hover { background: #d9d9d9; }
QPushButton#primary:disabled { background: #3f3f3f; color: #717171; }

QPushButton#chip { padding: 7px 14px; border-radius: 8px; }
QPushButton#chip:checked { background: #f1f1f1; color: #0f0f0f; font-weight: 600; }

QPushButton#ctl { padding: 0; min-width: 40px; max-width: 40px; min-height: 40px;
                  max-height: 40px; border-radius: 20px; font-size: 16px; }
QPushButton#ctl:checked { background: #f1f1f1; color: #0f0f0f; }
QPushButton#play { padding: 0; min-width: 48px; max-width: 48px; min-height: 48px;
                   max-height: 48px; border-radius: 24px; font-size: 20px;
                   background: #f1f1f1; color: #0f0f0f; }
QPushButton#play:hover { background: #d9d9d9; }

QPushButton#update { background: #272727; padding: 8px 16px; }
QPushButton#update[state="available"] { background: #cc0000; font-weight: 600; }
QPushButton#update[state="available"]:hover { background: #e60000; }
QPushButton#update[state="uptodate"] { background: #14281b; color: #6fd48c; }
QPushButton#update:disabled { color: #aaaaaa; }
QPushButton#update[state="uptodate"]:disabled { color: #6fd48c; }

QLineEdit { background: #121212; border: 1px solid #303030; padding: 8px 14px;
            border-radius: 18px; selection-background-color: #3ea6ff; }
QLineEdit:focus { border: 1px solid #3ea6ff; }
QPlainTextEdit, QTextEdit, QSpinBox, QDoubleSpinBox, QDateEdit, QTimeEdit {
    background: #121212; color: #f1f1f1; border: 1px solid #303030;
    border-radius: 8px; padding: 6px; selection-background-color: #3f3f3f;
}
QPlainTextEdit:disabled, QTextEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled,
QDateEdit:disabled, QTimeEdit:disabled { color: #717171; }
QLineEdit#urlbar { border-top-right-radius: 0; border-bottom-right-radius: 0; }
QPushButton#urlgo { background: #222222; border: 1px solid #303030; border-left: none;
                    border-top-left-radius: 0; border-bottom-left-radius: 0;
                    border-top-right-radius: 18px; border-bottom-right-radius: 18px;
                    padding: 8px 18px; }
QPushButton#urlgo:hover { background: #3f3f3f; }

QComboBox { background: #272727; border: none; border-radius: 8px; padding: 7px 12px; min-width: 150px; }
QComboBox:hover { background: #3f3f3f; }
QComboBox QAbstractItemView { background: #212121; selection-background-color: #3f3f3f; border: none; outline: none; }

QProgressBar { background: #3f3f3f; border: none; border-radius: 3px; max-height: 6px; min-height: 6px; }
QProgressBar::chunk { background: #ff0000; border-radius: 3px; }

QSlider::groove:horizontal { height: 4px; background: #3f3f3f; border-radius: 2px; }
QSlider::sub-page:horizontal { background: #ff0000; border-radius: 2px; }
QSlider::handle:horizontal { background: #ff0000; width: 12px; height: 12px; margin: -4px 0; border-radius: 6px; }

QListWidget { background: transparent; border: none; outline: none; }
QListWidget#grid::item { border-radius: 10px; padding: 6px; color: #f1f1f1; }
QListWidget#grid::item:hover { background: #1f1f1f; }
QListWidget#grid::item:selected { background: #272727; }
QListWidget#plain::item { padding: 6px 8px; border-radius: 8px; }
QListWidget#plain::item:hover { background: #1f1f1f; }
QListWidget#plain::item:selected { background: #303030; }

QScrollBar:vertical { background: transparent; width: 12px; margin: 0; }
QScrollBar::handle:vertical { background: #3f3f3f; border-radius: 5px; min-height: 30px; margin: 2px; }
QScrollBar::handle:vertical:hover { background: #5a5a5a; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal { background: transparent; height: 12px; margin: 0; }
QScrollBar::handle:horizontal { background: #3f3f3f; border-radius: 5px; min-width: 30px; margin: 2px; }
QScrollBar::handle:horizontal:hover { background: #5a5a5a; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }

QCheckBox { spacing: 8px; }
QToolTip { background: #272727; color: #f1f1f1; border: 1px solid #3f3f3f; padding: 4px; }
QStatusBar { background: #0f0f0f; color: #aaaaaa; }
QMenu { background: #212121; border: 1px solid #3f3f3f; padding: 6px; }
QMenu::item { padding: 7px 22px; border-radius: 6px; }
QMenu::item:selected { background: #3f3f3f; }
QMessageBox, QProgressDialog, QDialog { background: #1a1a1a; }

QWidget#busy { background: rgba(0, 0, 0, 190); }
QLabel#busytext { background: transparent; font-size: 20px; font-weight: 600; }

QFrame#fsbar { background: #121212; border-top: 1px solid #303030; }
QFrame#fsbar QLabel { background: transparent; }
QFrame#web { background: #0f0f0f; }
"""
