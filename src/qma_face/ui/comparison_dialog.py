from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from qma_face.core.i18n import tr
from qma_face.services.comparison import compare_reports, comparison_text
from qma_face.ui.analysis_dialog import AnalysisDialog
from qma_face.ui.widgets import readable_image


class ComparisonDialog(QDialog):
    def __init__(self, language, parent=None):
        super().__init__(parent)
        self.language = language
        self.items = []
        self.comparison_report = None
        self.setWindowTitle(self.t("comparison_title"))
        self.resize(900, 760)
        layout = QVBoxLayout(self)
        title = QLabel(self.t("compare"))
        title.setStyleSheet("font-size: 24px; color: #7867C7; padding: 8px 0;")
        layout.addWidget(title)
        note = QLabel(self.t("collection_note"))
        note.setWordWrap(True)
        layout.addWidget(note)
        form = QFormLayout()
        self.photo_label = QLineEdit()
        self.photo_label.setMaxLength(80)
        self.photo_date = QLineEdit()
        self.photo_date.setPlaceholderText("YYYY-MM-DD")
        self.angle = self.picker(("unknown", "front", "left", "right"))
        self.expression = self.picker(("unknown", "neutral", "smile"))
        for key, widget in (
            ("photo_label", self.photo_label),
            ("photo_date", self.photo_date),
            ("angle_label", self.angle),
            ("expression_label", self.expression),
        ):
            form.addRow(self.t(key), widget)
            widget.setAccessibleName(self.t(key))
        layout.addLayout(form)
        actions = QHBoxLayout()
        actions.addWidget(self.button("add_comparison_photo", self.add_photo))
        actions.addWidget(self.button("remove_item", self.remove_item))
        layout.addLayout(actions)
        self.list = QListWidget()
        self.list.setMaximumHeight(135)
        layout.addWidget(self.list)
        self.same_person = QCheckBox(self.t("same_person"))
        self.same_person.toggled.connect(self.invalidate)
        layout.addWidget(self.same_person)
        layout.addWidget(self.button("compare_now", self.compute))
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        layout.addWidget(self.output, 1)
        self.save = self.button("save_comparison", self.accept)
        self.save.setEnabled(False)
        layout.addWidget(self.save, alignment=Qt.AlignmentFlag.AlignRight)

    def t(self, key):
        return tr(key, self.language)

    def picker(self, keys):
        widget = QComboBox()
        for key in keys:
            widget.addItem(self.t(key), key)
        return widget

    def button(self, key, callback):
        button = QPushButton(self.t(key))
        button.setObjectName("secondary")
        button.clicked.connect(callback)
        return button

    def invalidate(self):
        self.comparison_report = None
        self.save.setEnabled(False)
        self.output.clear()

    def add_photo(self):
        if len(self.items) >= 8:
            return
        path, _ = QFileDialog.getOpenFileName(self, self.t("add_photo"), "", self.t("photo_dialog"))
        if not path:
            return
        try:
            reader = readable_image(Path(path))
            if max(reader.size().width(), reader.size().height()) > 1024:
                reader.setScaledSize(
                    reader.size().scaled(1024, 1024, Qt.AspectRatioMode.KeepAspectRatio)
                )
            image = reader.read()
            if image.isNull():
                raise ValueError("image_decode")
        except (OSError, ValueError):
            self.output.setPlainText(self.t("image_decode"))
            return
        if max(image.width(), image.height()) > 1024:
            image = image.scaled(
                1024,
                1024,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        dialog = AnalysisDialog(image, self.language, self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.analysis_report:
            self.items.append(
                {
                    "label": self.photo_label.text().strip() or f"Photo {len(self.items) + 1}",
                    "date": self.photo_date.text().strip(),
                    "angle": self.angle.currentData(),
                    "expression": self.expression.currentData(),
                    "report": dialog.analysis_report,
                }
            )
            self.list.addItem(self.items[-1]["label"])
            self.photo_label.clear()
            self.invalidate()
        dialog.deleteLater()

    def remove_item(self):
        index = self.list.currentRow()
        if index >= 0:
            self.items.pop(index)
            self.list.takeItem(index)
            self.invalidate()

    def compute(self):
        try:
            self.comparison_report = compare_reports(
                self.items, same_person_confirmed=self.same_person.isChecked()
            )
        except (KeyError, TypeError, ValueError):
            self.output.setPlainText(self.t("comparison_invalid"))
            self.save.setEnabled(False)
            return
        self.output.setPlainText(comparison_text(self.comparison_report, self.language))
        self.save.setEnabled(True)
