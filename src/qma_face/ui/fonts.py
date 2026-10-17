import os
from pathlib import Path

from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication

from qma_face.core.config import PROJECT_ROOT


def configure_fonts(application: QApplication) -> None:
    """Load installed Windows fonts explicitly for offscreen and restricted sessions."""
    font_directory = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
    for name in ("SegUIVar.ttf", "segoeui.ttf", "seguisb.ttf", "segoeuib.ttf", "tahoma.ttf"):
        path = font_directory / name
        if path.is_file():
            QFontDatabase.addApplicationFont(str(path))
    bundled = PROJECT_ROOT / "assets/fonts"
    for name in ("PlusJakartaSans[wght].ttf", "Vazirmatn[wght].ttf"):
        path = bundled / name
        if path.is_file():
            QFontDatabase.addApplicationFont(str(path))
    font = QFont("Plus Jakarta Sans", 11)
    font.setFamilies(["Plus Jakarta Sans", "Vazirmatn", "Segoe UI Variable", "Segoe UI"])
    application.setFont(font)
