"""Optional text translation using the existing local language model."""

import re
import threading

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from qma_face.ui.widgets import ProcessingOrbit


class TranslationWorker(QThread):
    piece = Signal(str)
    completed = Signal(dict)
    failed = Signal()

    def __init__(self, backend, text, target, parent):
        super().__init__(parent)
        self.backend, self.text, self.target = backend, text, target
        self.cancel = threading.Event()

    def run(self):
        try:
            self.completed.emit(
                self.backend.translate(
                    self.text, self.target, self.cancel, self.piece.emit, lambda state: None
                )
            )
        except Exception:
            self.failed.emit()


class TranslatorDialog(QDialog):
    def __init__(self, backend, text, language, parent=None):
        super().__init__(parent)
        self.backend = backend
        self.worker = None
        self.translated_text = ""
        self.closing = False
        self.french = language == "fr"
        self.setWindowTitle(
            "Traduction locale · فارسی" if self.french else "Local translator · فارسی"
        )
        self.resize(760, 640)
        self.setStyleSheet(
            "QDialog { background: #F7F7FE; }"
            "QWidget { font-family: 'Plus Jakarta Sans', 'Vazirmatn', 'Segoe UI'; }"
            "QPlainTextEdit { background: white; border: 1px solid #E2DCF3; "
            "border-radius: 18px; padding: 14px; font-size: 15px; }"
            "QPushButton, QComboBox { border: 1px solid #DED6F3; border-radius: 12px; "
            "background: #EFEBFA; padding: 9px 14px; color: #65518F; }"
        )
        layout = QVBoxLayout(self)
        title = QLabel("ترجمهٔ فارسی · English · Français")
        title.setStyleSheet("font-size: 22px; color: #7867C7; padding: 12px;")
        layout.addWidget(title)
        self.input = QPlainTextEdit()
        self.input.setPlaceholderText("متن را اینجا وارد کنید…")
        self.input.setPlainText(text)
        layout.addWidget(self.input, 1)
        row = QHBoxLayout()
        self.target = QComboBox()
        for title, value in [("فارسی", "Persian"), ("English", "English"), ("Français", "French")]:
            self.target.addItem(title, value)
        row.addWidget(self.target)
        self.start = QPushButton("ترجمه / Translate")
        self.start.clicked.connect(self.translate)
        row.addWidget(self.start)
        layout.addLayout(row)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.hide()
        self.orbit = ProcessingOrbit()
        layout.addWidget(self.orbit, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self.progress)
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        layout.addWidget(self.output, 1)
        self.note = QLabel("ترجمهٔ ماشینی است؛ متن اصلی را هم بررسی کنید.")
        self.note.setWordWrap(True)
        layout.addWidget(self.note)
        row = QHBoxLayout()
        self.copy = QPushButton("کپی / Copy")
        self.copy.clicked.connect(self.copy_output)
        row.addWidget(self.copy)
        self.use = QPushButton("استفاده در چت / Use in chat")
        self.use.setEnabled(False)
        self.use.clicked.connect(self.accept)
        row.addWidget(self.use)
        close = QPushButton("بستن / Close")
        close.clicked.connect(self.reject)
        row.addWidget(close)
        layout.addLayout(row)

    def copy_output(self):
        from PySide6.QtWidgets import QApplication

        QApplication.clipboard().setText(self.translated_text)

    def translate(self):
        if self.worker or not self.input.toPlainText().strip():
            return
        if len(self.input.toPlainText()) > 10000:
            self.note.setText("متن را به بخش‌های کوتاه‌تر از ۱۰ هزار نویسه تقسیم کنید.")
            return
        self.output.clear()
        self.translated_text = ""
        self.output.setLayoutDirection(
            Qt.LayoutDirection.RightToLeft
            if self.target.currentData() == "Persian"
            else Qt.LayoutDirection.LeftToRight
        )
        self.start.setEnabled(False)
        self.use.setEnabled(False)
        self.progress.show()
        self.orbit.set_running(True)
        self.worker = TranslationWorker(
            self.backend, self.input.toPlainText(), self.target.currentData(), self
        )
        self.worker.piece.connect(self.append_piece)
        self.worker.completed.connect(self.complete)
        self.worker.failed.connect(self.failed)
        self.worker.finished.connect(self.finished_work)
        self.worker.start()

    def append_piece(self, piece):
        from PySide6.QtGui import QTextCursor

        self.translated_text += piece
        cursor = self.output.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(piece)
        self.output.setTextCursor(cursor)

    def complete(self, result):
        self.translated_text = result["text"]
        display = self.translated_text
        if self.target.currentData() == "Persian":
            display = re.sub(
                r"https?://\S+|\[S\d+\]|\d+(?:[.,]\d+)*(?:\s*[/±:+−-]\s*\d+(?:[.,]\d+)*)*",
                lambda match: "\u2066" + match.group(0) + "\u2069",
                display,
            )
        self.output.setPlainText(display)
        self.use.setEnabled(not result.get("truncated", False))
        self.note.setText(
            "ترجمه ناتمام است؛ متن را کوتاه‌تر کنید."
            if result.get("truncated")
            else "ترجمهٔ ماشینی است؛ متن اصلی را هم بررسی کنید."
        )

    def failed(self):
        self.output.clear()
        self.translated_text = ""
        self.note.setText("ترجمه کامل نشد. دوباره تلاش کنید.")

    def finished_work(self):
        worker, self.worker = self.worker, None
        worker.deleteLater()
        self.start.setEnabled(True)
        self.progress.hide()
        self.orbit.set_running(False)
        if self.closing:
            super().reject()

    def reject(self):
        if self.worker:
            self.closing = True
            self.worker.cancel.set()
            self.backend.cancel_generation()
            return
        super().reject()

    def closeEvent(self, event):
        if self.worker:
            self.reject()
            event.ignore()
        else:
            super().closeEvent(event)
