"""PrisDrop: descargador y reproductor multimedia basado en yt-dlp."""
import sys

from PySide6.QtWidgets import QApplication

from prisdrop.theme import STYLE
from prisdrop.ui.main_window import MainWindow


def _hide_standalone_windows_console() -> None:
    if sys.platform != "win32":
        return

    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GetConsoleWindow.restype = wintypes.HWND
    console_window = kernel32.GetConsoleWindow()
    if not console_window:
        return

    kernel32.GetConsoleProcessList.argtypes = (
        ctypes.POINTER(wintypes.DWORD),
        wintypes.DWORD,
    )
    kernel32.GetConsoleProcessList.restype = wintypes.DWORD
    process_ids = (wintypes.DWORD * 64)()
    process_count = kernel32.GetConsoleProcessList(process_ids, len(process_ids))
    if process_count == 1:
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        user32.ShowWindow.argtypes = (wintypes.HWND, ctypes.c_int)
        user32.ShowWindow(console_window, 0)


def main() -> int:
    _hide_standalone_windows_console()
    app = QApplication(sys.argv)
    app.setApplicationName("PrisDrop")
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
