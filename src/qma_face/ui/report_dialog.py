from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from qma_face.core.i18n import tr
from qma_face.services.report_export import export_report


class ReportDialog(QDialog):
    def __init__(self, text, language, parent=None, *, engine_hash=None, sources=None):
        super().__init__(parent)
        self.setWindowTitle(tr("export_report", language))
        self.resize(800, 700)
        self.language = language
        self.text = text
        self.engine_hash = engine_hash
        self.sources = sources or []
        layout = QVBoxLayout(self)
        content = QPlainTextEdit()
        content.setReadOnly(True)
        content.setPlainText(text)
        layout.addWidget(content, 1)
        self.excerpts = QCheckBox(tr("source_excerpts", language))
        self.excerpts.setVisible(bool(self.sources))
        layout.addWidget(self.excerpts)
        self.status = QLabel(tr("report_private", language))
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        controls = QHBoxLayout()
        for extension, title in (("pdf", "PDF"), ("html", "HTML"), ("png", "PNG")):
            button = QPushButton(title)
            button.setObjectName("secondary")
            button.clicked.connect(lambda checked=False, ext=extension: self.save(ext))
            controls.addWidget(button)
        close = QPushButton(tr("close", language))
        close.clicked.connect(self.accept)
        controls.addWidget(close)
        layout.addLayout(controls)

    def save(self, extension):
        path, _ = QFileDialog.getSaveFileName(
            self,
            tr("export_report", self.language),
            f"QMA-Face-report.{extension}",
            f"{extension.upper()} (*.{extension})",
        )
        if not path:
            return
        output = Path(path)
        if output.suffix.lower() != "." + extension:
            output = Path(str(output) + "." + extension)
        try:
            export_report(
                output,
                self.text,
                language=self.language,
                engine_hash=self.engine_hash,
                sources=self.sources,
                include_excerpts=self.excerpts.isChecked(),
            )
        except (OSError, ValueError):
            self.status.setText(tr("export_error", self.language))
