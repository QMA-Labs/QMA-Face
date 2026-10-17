import copy
import io
import json
import threading

from PIL import Image
from PySide6.QtCore import QBuffer, QByteArray, QIODevice, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from qma_face.core.i18n import tr
from qma_face.services.analysis import AnalysisCancelled, AnalysisService, finish_report
from qma_face.services.geometry import GROUPS, measurements
from qma_face.services.photo_quality import (
    auto_prepare_photo,
    inspect_photo,
    photo_digest,
    prepare_photo,
)
from qma_face.ui.analysis_text import text_report
from qma_face.ui.face_canvas import FaceCanvas, qt_image
from qma_face.ui.widgets import ProcessingOrbit


def pil_image(image):
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    buffer.close()
    with Image.open(io.BytesIO(bytes(data))) as photo:
        rgba = photo.convert("RGBA")
        result = Image.new("RGBA", rgba.size, "white")
        result.alpha_composite(rgba)
        return result.convert("RGB")


class AnalysisWorker(QThread):
    completed = Signal(dict)
    failed = Signal(str)

    def __init__(self, action, parent=None):
        super().__init__(parent)
        self.action = action
        self.cancel_event = threading.Event()

    def run(self):
        try:
            result = self.action(self.cancel_event)
            if not self.cancel_event.is_set():
                self.completed.emit(result)
        except AnalysisCancelled:
            pass
        except Exception:
            self.failed.emit("analysis_failed")


class AnalysisDialog(QDialog):
    def __init__(self, image, language, parent=None, service=None, guided_auto=False):
        super().__init__(parent)
        self.language = language
        self.guided_auto = guided_auto
        self.source = pil_image(image)
        self.source_digest = photo_digest(self.source)
        self.oriented = self.source.copy()
        self.rotation = 0
        self.service = service or AnalysisService()
        self.worker = None
        self.analysis_report = None
        self.working = None
        self.original_crop = None
        self.edited_points = False
        self.points_reviewed = False
        self._pending_auto_result = False
        self._close_requested = False
        self.setWindowTitle(self.t("analysis_title"))
        self.resize(1240, 900)
        self.setMinimumSize(720, 500)
        self.setStyleSheet(
            "QDialog { background: #F8F7FE; } QLabel { color: #3B3457; } "
            "QPushButton { border: none; background: #EEE8FA; color: #65558E; "
            "border-radius: 12px; padding: 10px 16px; min-height: 18px; } "
            "QPushButton#primary { background: #8273D9; color: white; } "
            "QPushButton:disabled, QPushButton#primary:disabled "
            "{ background: #E7E2ED; color: #AAA3B7; } "
            "QCheckBox { color: #655D79; padding: 6px; } "
            "QPlainTextEdit { background: white; border: 1px solid #E7E0F3; "
            "border-radius: 16px; padding: 12px; font-size: 13px; } "
            "QScrollArea { border: none; background: transparent; }"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 18, 24, 18)
        self.steps = self.caption("")
        self.steps.setStyleSheet("color: #8273D9; font-size: 13px; padding: 4px;")
        layout.addWidget(self.steps)
        note = self.caption(self.t("research_note"))
        note.setStyleSheet("color: #8B809D; font-size: 12px; padding: 5px;")
        layout.addWidget(note)
        self.pages = QStackedWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.pages)
        self.pages.setAutoFillBackground(False)
        scroll.viewport().setAutoFillBackground(False)
        layout.addWidget(scroll, 1)
        self._make_photo()
        self._make_points()
        self._make_result()
        self.status = self.caption("")
        activity = QHBoxLayout()
        self.orbit = ProcessingOrbit()
        activity.addWidget(self.orbit)
        activity.addWidget(self.status, 1)
        layout.addLayout(activity)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(8)
        self.progress.hide()
        layout.addWidget(self.progress)
        controls = QHBoxLayout()
        self.back = self.button("back", self.go_back)
        controls.addWidget(self.back)
        controls.addStretch()
        self.cancel = self.button("cancel_analysis", self.reject)
        controls.addWidget(self.cancel)
        self.continue_button = self.button("next_points", self.continue_flow, True)
        self.continue_button.setMinimumWidth(210)
        controls.addWidget(self.continue_button)
        layout.addLayout(controls)
        self.set_step(0)
        self.quality_timer = QTimer(self)
        self.quality_timer.setSingleShot(True)
        self.quality_timer.setInterval(250)
        self.quality_timer.timeout.connect(self.check_photo)
        if self.guided_auto:
            self.points_confirm.toggled.connect(self._auto_explain)
            self.face_confirm.hide()
            self.next_points.hide()
            self.next_result.hide()
            self.accept_button.hide()
            self.next_points.setText(
                "Confirmer et analyser" if language == "fr" else "Confirm & analyse"
            )
            QTimer.singleShot(0, self.check_photo)

    def _auto_locate(self, checked):
        if checked:
            QTimer.singleShot(0, self.locate_points)

    def _auto_explain(self, checked):
        if checked:
            QTimer.singleShot(0, self.compute_result)

    def continue_flow(self):
        if self.pages.currentIndex() == 0:
            self.locate_points()
        elif self.pages.currentIndex() == 1:
            self.compute_result()
        elif self.analysis_report:
            self.accept()

    def t(self, key):
        return tr(key, self.language)

    def caption(self, text):
        widget = QLabel(text)
        widget.setWordWrap(True)
        widget.setTextFormat(Qt.TextFormat.PlainText)
        return widget

    def button(self, key, action, primary=False):
        button = QPushButton(self.t(key))
        if primary:
            button.setObjectName("primary")
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.clicked.connect(action)
        return button

    def _make_photo(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(self.caption(self.t("crop_hint")))
        self.crop_canvas = FaceCanvas("crop")
        self.crop_canvas.set_image(self.oriented)
        self.crop_canvas.cropChanged.connect(self.invalidate_quality)
        layout.addWidget(self.crop_canvas, 1)
        controls = QHBoxLayout()
        controls.addWidget(self.button("rotate", self.rotate))
        controls.addWidget(self.button("reset", self.reset_crop))
        controls.addStretch()
        self.check_button = self.button("check_photo", self.check_photo, True)
        controls.addWidget(self.check_button)
        layout.addLayout(controls)
        self.quality_note = self.caption("")
        self.quality_note.setStyleSheet(
            "background: #EEE8FF; border-radius: 12px; padding: 12px; font-size: 14px;"
        )
        layout.addWidget(self.quality_note)
        self.comparison = QWidget()
        comparison = QHBoxLayout(self.comparison)
        self.before_preview = QLabel()
        self.after_preview = QLabel()
        for image_label, key in (
            (self.before_preview, "original"),
            (self.after_preview, "prepared"),
        ):
            box = QVBoxLayout()
            box.addWidget(self.caption(self.t(key)))
            box.addWidget(image_label)
            comparison.addLayout(box)
        self.comparison.hide()
        layout.addWidget(self.comparison)
        self.adjust_options = QWidget()
        adjust = QHBoxLayout(self.adjust_options)
        adjust.setContentsMargins(0, 0, 0, 0)
        self.improve = self.button("improve", self.improve_photo)
        self.use_original = self.button("use_original", self.use_original_photo)
        self.denoise = QCheckBox(self.t("denoise"))
        self.denoise.toggled.connect(self.update_improve)
        adjust.addWidget(self.improve)
        adjust.addWidget(self.use_original)
        adjust.addWidget(self.denoise)
        layout.addWidget(self.adjust_options)
        self.face_confirm = QCheckBox(self.t("confirm_face"))
        self.face_confirm.toggled.connect(self.update_next)
        layout.addWidget(self.face_confirm)
        self.next_points = self.button("next_points", self.locate_points, True)
        layout.addWidget(self.next_points)
        self.pages.addWidget(page)
        self.invalidate_quality()

    def _make_points(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(self.caption(self.t("points_hint")))
        self.map_canvas = FaceCanvas("points")
        self.map_canvas.pointsEdited.connect(self.points_edited)
        layout.addWidget(self.map_canvas, 1)
        map_tools = QHBoxLayout()
        enlarge = QPushButton(
            "Agrandir la carte ↗" if self.language == "fr" else "Expand face map ↗"
        )
        enlarge.clicked.connect(self.expand_map)
        map_tools.addWidget(enlarge)
        self.number_points = QCheckBox("Numéros" if self.language == "fr" else "Point numbers")
        self.number_points.toggled.connect(self.toggle_numbers)
        map_tools.addWidget(self.number_points)
        map_tools.addStretch()
        layout.addLayout(map_tools)
        groups = QHBoxLayout()
        self.group_checks = {}
        for group in GROUPS:
            check = QCheckBox(self.t(group))
            check.setChecked(True)
            check.toggled.connect(self.visibility_changed)
            groups.addWidget(check)
            self.group_checks[group] = check
        layout.addLayout(groups)
        self.points_confirm = QCheckBox(self.t("confirm_points"))
        self.points_confirm.toggled.connect(self.update_next)
        layout.addWidget(self.points_confirm)
        self.next_result = self.button("next_result", self.compute_result, True)
        self.next_result.setEnabled(False)
        layout.addWidget(self.next_result)
        self.pages.addWidget(page)

    def _make_result(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        self.score = self.caption("")
        self.score.setStyleSheet("font-size: 30px; color: #7867C7; font-weight: 600;")
        layout.addWidget(self.score)
        self.cards_layout = QVBoxLayout()
        layout.addLayout(self.cards_layout)
        body = QHBoxLayout()
        visual = QVBoxLayout()
        self.result_canvas = FaceCanvas("readonly")
        self.result_canvas.setMinimumHeight(420)
        visual.addWidget(self.result_canvas, 1)
        self.expand_result = QPushButton(
            "Agrandir le visage ↗" if self.language == "fr" else "Expand face view ↗"
        )
        self.expand_result.clicked.connect(lambda: self.expand_map(readonly=True))
        visual.addWidget(self.expand_result)
        self.review_result = QPushButton(
            "Vérifier / corriger les points" if self.language == "fr" else "Review / correct points"
        )
        self.review_result.clicked.connect(lambda: self.set_step(1))
        visual.addWidget(self.review_result)
        self.photo_unavailable = self.caption(
            "La photo préparée n’est pas conservée. Les résultats enregistrés restent disponibles."
            if self.language == "fr"
            else "The analysed photo is not retained. Your saved results are still available."
        )
        self.photo_unavailable.hide()
        visual.addWidget(self.photo_unavailable)
        self.attention_toggle = QCheckBox(self.t("attention_layer"))
        self.attention_toggle.toggled.connect(self.toggle_attention)
        visual.addWidget(self.attention_toggle)
        self.swatches = QWidget()
        self.swatch_layout = QHBoxLayout(self.swatches)
        visual.addWidget(self.swatches)
        body.addLayout(visual, 4)
        self.details = QPlainTextEdit()
        self.details.setReadOnly(True)
        self.result_tabs = QTabWidget()
        self.result_tabs.setStyleSheet(
            "QTabWidget::pane { border: none; background: white; border-radius: 18px; }"
            "QTabBar::tab { background: #EEEAF8; color: #74658E; padding: 10px 14px; "
            "border-radius: 10px; margin: 3px; }"
            "QTabBar::tab:selected { background: #FFFFFF; color: #6950B4; }"
        )
        self.overview = self.caption("")
        self.overview.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.overview.setStyleSheet("padding: 18px; font-size: 15px; line-height: 1.5;")
        self.result_tabs.addTab(self.overview, "Résumé" if self.language == "fr" else "Overview")
        self.measurement_table = QTableWidget(0, 2)
        self.measurement_table.setHorizontalHeaderLabels(
            ["Mesure", "Valeur"] if self.language == "fr" else ["Measurement", "Value"]
        )
        self.measurement_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self.measurement_table.verticalHeader().hide()
        self.measurement_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.measurement_table.setAlternatingRowColors(True)
        self.measurement_table.setStyleSheet(
            "QTableWidget { background: white; alternate-background-color: #F6F3FE; "
            "border: none; gridline-color: #EEE9F8; font-size: 12px; }"
        )
        self.result_tabs.addTab(
            self.measurement_table, "Mesures" if self.language == "fr" else "Measurements"
        )
        self.sensitivity_page = QScrollArea()
        self.sensitivity_page.setWidgetResizable(True)
        self.sensitivity_page.viewport().setAutoFillBackground(False)
        self.result_tabs.addTab(
            self.sensitivity_page, "Sensibilité" if self.language == "fr" else "Sensitivity"
        )
        self.result_tabs.addTab(self.details, "Méthode" if self.language == "fr" else "Method")
        body.addWidget(self.result_tabs, 6)
        layout.addLayout(body, 1)
        layout.addWidget(self.caption(self.t("privacy_analysis")))
        controls = QHBoxLayout()
        controls.addWidget(self.button("export_analysis", self.export_result))
        report_button = QPushButton(tr("export_report", self.language))
        report_button.clicked.connect(self.export_document)
        controls.addWidget(report_button)
        controls.addStretch()
        self.accept_button = self.button("save_analysis", self.accept, True)
        controls.addWidget(self.accept_button)
        layout.addLayout(controls)
        self.pages.addWidget(page)

    def toggle_numbers(self, checked):
        self.map_canvas.show_numbers = checked
        self.map_canvas.update()

    def expand_map(self, readonly=False):
        source_canvas = self.result_canvas if readonly else self.map_canvas
        if source_canvas.points is None or self.working is None:
            return
        dialog = QDialog(self)
        dialog.setWindowTitle(self.t("analysis_title"))
        dialog.resize(1120, 900)
        layout = QVBoxLayout(dialog)
        layout.addWidget(
            self.caption(
                "Molette : zoom · Bouton droit : déplacer · Glissez un point pour le corriger."
                if self.language == "fr"
                else "Scroll to zoom · Right-drag to pan · Drag a point to correct its position."
            )
        )
        if readonly:
            layout.itemAt(0).widget().setText(
                "Molette : zoom · Bouton droit : déplacer · Carte enregistrée en lecture seule."
                if self.language == "fr" else
                "Scroll to zoom · Right-drag to pan · Read-only saved map."
            )
        canvas = FaceCanvas("readonly" if readonly else "points")
        canvas.set_image(self.working)
        canvas.points = copy.deepcopy(source_canvas.points)
        canvas.visible_groups = dict(source_canvas.visible_groups)
        canvas.show_numbers = True
        layout.addWidget(canvas, 1)
        controls = QHBoxLayout()
        reset = QPushButton(self.t("reset"))
        reset.clicked.connect(canvas.reset_view)
        controls.addWidget(reset)
        controls.addStretch()
        cancel = QPushButton(self.t("cancel_analysis"))
        cancel.clicked.connect(dialog.reject)
        controls.addWidget(cancel)
        apply = QPushButton("Appliquer" if self.language == "fr" else "Apply corrections")
        if readonly:
            apply.setText(self.t("close"))
        apply.clicked.connect(dialog.accept)
        controls.addWidget(apply)
        layout.addLayout(controls)
        if dialog.exec() == QDialog.DialogCode.Accepted and not readonly:
            if canvas.points != self.map_canvas.points:
                self.map_canvas.points = copy.deepcopy(canvas.points)
                self.map_canvas.update()
                self.points_edited()
        dialog.deleteLater()

    def set_step(self, step):
        self.pages.setCurrentIndex(step)
        key = ("step_photo", "step_points", "step_result")[step]
        self.steps.setText(f"{step + 1} / 3   ·   {self.t(key).split('·', 1)[-1].strip()}")
        if self.guided_auto:
            self.steps.setText("Studio visage" if self.language == "fr" else "Face studio")
        if hasattr(self, "back"):
            self.back.setVisible(step > 0)
        self.update_next()

    def invalidate_quality(self):
        self.working = self.original_crop = None
        self.face_confirm.setChecked(False)
        self.quality_note.setText("")
        self.improve.setEnabled(False)
        self.use_original.setEnabled(False)
        self.comparison.hide()
        self.adjust_options.hide()
        self.denoise.setChecked(False)
        self.next_points.setEnabled(False)
        if self.guided_auto and hasattr(self, "quality_timer"):
            self.quality_timer.start()

    def rotate(self):
        self.rotation = (self.rotation + 90) % 360
        self.oriented = self.source.rotate(-self.rotation, expand=True)
        self.crop_canvas.set_image(self.oriented)
        self.invalidate_quality()

    def reset_crop(self):
        self.rotation = 0
        self.oriented = self.source.copy()
        self.crop_canvas.set_image(self.oriented)
        self.invalidate_quality()

    def check_photo(self):
        box = self.crop_canvas.crop_box()
        if box[2] <= box[0] or box[3] <= box[1]:
            return
        self.original_crop = self.oriented.crop(box)
        if self.guided_auto:
            self.working, self.preparation = auto_prepare_photo(self.original_crop)
            self.preparation["rotation_degrees_clockwise"] = self.rotation
            self.show_quality()
        else:
            self.use_original_photo()

    def use_original_photo(self):
        if self.original_crop is None:
            return
        self.working = self.original_crop.copy()
        self.preparation = {
            "operations": [],
            "rotation_degrees_clockwise": self.rotation,
            "before": inspect_photo(self.original_crop),
            "after": inspect_photo(self.working),
            "geometric_warp": False,
            "generated_detail": False,
        }
        self.show_quality()

    def improve_photo(self):
        if self.original_crop is None:
            return
        self.working, self.preparation = prepare_photo(
            self.original_crop, denoise=self.denoise.isChecked()
        )
        self.preparation["rotation_degrees_clockwise"] = self.rotation
        self.show_quality()

    def show_quality(self):
        quality = self.preparation["after"]
        parts = [self.t("quality_" + quality["status"])]
        parts.extend(self.t(key) for key in quality["blocking"] + quality["warnings"])
        if self.preparation.get("operations"):
            parts.append(
                "Correction locale appliquée ; comparez avec l’original."
                if self.language == "fr"
                else "Local adjustments applied; compare with the original."
            )
        self.quality_note.setText(" ".join(parts))
        self.adjust_options.show()
        self.update_improve()
        self.use_original.setEnabled(True)
        for target, photo in (
            (self.before_preview, self.original_crop),
            (self.after_preview, self.working),
        ):
            target.setPixmap(
                QPixmap.fromImage(qt_image(photo)).scaled(
                    110,
                    78,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        changed = bool(self.preparation["operations"])
        self.comparison.setVisible(changed)
        self.use_original.setVisible(changed)
        self.face_confirm.setChecked(False)
        self.update_next()

    def update_improve(self):
        if self.original_crop is None:
            self.improve.setEnabled(False)
            return
        mean = inspect_photo(self.original_crop)["mean_luma_0_to_255"]
        self.improve.setEnabled(mean < 75 or mean > 195 or self.denoise.isChecked())

    def update_next(self):
        busy = self.worker is not None
        self.next_points.setEnabled(
            not busy
            and self.working is not None
            and (self.guided_auto or self.face_confirm.isChecked())
            and self.preparation["after"]["status"] != "retake"
        )
        if hasattr(self, "next_result"):
            self.next_result.setEnabled(not busy and self.points_confirm.isChecked())
        if hasattr(self, "continue_button"):
            step = self.pages.currentIndex()
            self.continue_button.setVisible(True)
            target = (self.next_points, self.next_result, self.accept_button)[step]
            self.continue_button.setText(target.text())
            self.continue_button.setEnabled(
                not busy and (bool(self.analysis_report) if step == 2 else target.isEnabled())
            )
            self.continue_button.setToolTip(
                self.quality_note.text() if step == 0 else self.t("confirm_points")
            )

    def _run(self, action, completed, state):
        if self.worker is not None:
            return
        self.status.setText(self.t(state))
        self.progress.show()
        self.orbit.set_running(True)
        self.worker = AnalysisWorker(action, self)
        self.worker.completed.connect(completed)
        self.worker.failed.connect(lambda key: self.status.setText(self.t(key)))
        self.worker.finished.connect(self._finished)
        self.back.setEnabled(False)
        self.pages.setEnabled(False)
        self.update_next()
        self.worker.start()

    def _finished(self):
        worker = self.worker
        self.worker = None
        self.progress.hide()
        self.orbit.set_running(False)
        worker.deleteLater()
        self.back.setEnabled(True)
        self.pages.setEnabled(True)
        self.update_next()
        if self._close_requested:
            QTimer.singleShot(0, self.reject)
        elif self._pending_auto_result:
            self._pending_auto_result = False
            QTimer.singleShot(0, lambda: self.compute_result(automatic=True))

    def locate_points(self):
        if not self.next_points.isEnabled():
            return
        self.quality_timer.stop()
        photo = self.working.copy()
        self._run(
            lambda cancel: self.service.locate(photo, confirmed=True, cancel=cancel),
            self._located,
            "finding",
        )

    def _located(self, result):
        self.initial_points = copy.deepcopy(result["landmarks"])
        self.map_canvas.set_image(self.working)
        self.map_canvas.points = copy.deepcopy(self.initial_points)
        self.edited_points = False
        self.points_confirm.setChecked(False)
        self.status.setText("")
        self.set_step(1)
        flags = measurements(
            self.initial_points, self.working.size, {key: True for key in GROUPS}
        ).get("review_flags", [])
        if flags:
            self.status.setText("\n".join(self.t(flag) for flag in flags))
        if self.guided_auto:
            self._pending_auto_result = True

    def points_edited(self):
        self.edited_points = True
        self.points_confirm.setChecked(False)

    def visibility_changed(self):
        self.map_canvas.visible_groups = {
            key: check.isChecked() for key, check in self.group_checks.items()
        }
        self.map_canvas.update()
        self.points_confirm.setChecked(False)

    def compute_result(self, automatic=False):
        if not automatic and not self.next_result.isEnabled():
            return
        self.points_reviewed = not automatic
        points = copy.deepcopy(self.map_canvas.points)
        visible = {key: check.isChecked() for key, check in self.group_checks.items()}
        photo = self.working.copy()
        original = self.original_crop.copy()
        self._run(
            lambda cancel: self.service.explain(
                photo, points, visible, original=original, cancel=cancel
            ),
            self._explained,
            "explaining",
        )

    def _explained(self, result):
        self.analysis_report = finish_report(
            result,
            source=self.working,
            crop_box=self.crop_canvas.crop_box(),
            source_photo_sha256=self.source_digest,
            edited_points=self.edited_points,
            preparation=self.preparation,
            points=self.map_canvas.points,
        )
        if not self.points_reviewed:
            self.analysis_report["landmarks_source"] = "model_points_not_manually_reviewed"
            self.analysis_report["geometry"]["visibility_source"] = (
                "user_confirmed_photo_not_per_point_review"
            )
        self.analysis_report["points_manually_reviewed"] = self.points_reviewed
        self.display_report()

    def display_report(self):
        value = self.analysis_report["score_0_to_100"]
        self.score.setText(
            f"{self.t('research_score')}   {value:.1f} / 100"
            if value is not None
            else self.t("withheld")
        )
        self.details.setPlainText(text_report(self.analysis_report, self.language))
        metrics = self.analysis_report["geometry"]["metrics"]
        self.measurement_table.setRowCount(len(metrics))
        for row, metric in enumerate(metrics):
            self.measurement_table.setItem(row, 0, QTableWidgetItem(self.t(metric["name"])))
            metric_value = metric["value"]
            self.measurement_table.setItem(
                row, 1, QTableWidgetItem("—" if metric_value is None else f"{metric_value:.4f}")
            )
        self.measurement_table.resizeRowsToContents()
        flags = self.analysis_report["geometry"].get("review_flags", [])
        score_value = self.analysis_report["score_0_to_100"]
        value_text = "—" if score_value is None else f"{score_value:.1f} / 100"
        if self.language == "fr":
            summary = [
                f"Pour cette photo, le modèle local estime : {value_text}. Ce nombre reflète "
                "les évaluations apprises ; ce n’est pas un pourcentage de précision.",
                "L’onglet Mesures présente les rapports calculés. Méthode contient les détails "
                "du calcul et ses limites.",
                "Les barres montrent la variation du modèle après floutage de chaque zone. "
                "Elles ne donnent pas une note de beauté à vos yeux, votre nez ou vos lèvres.",
            ]
        else:
            summary = [
                f"For this photo, the local model estimates: {value_text}. This reflects the "
                "overall ratings it learned; it is not an accuracy percentage.",
                "Measurements contains the recorded ratios. Method contains the calculation "
                "details and limitations.",
                "The bars show how the model changes after each region is blurred. They do "
                "not rate the beauty of your eyes, nose or lips.",
            ]
        summary += [self.t(flag) for flag in flags]
        if self.analysis_report.get("points_manually_reviewed") is False:
            summary.insert(
                0,
                "Points automatiques non vérifiés. Utilisez « Vérifier / corriger les points » "
                "avant de vous fier aux mesures."
                if self.language == "fr"
                else "Automatic points have not been reviewed. Use ‘Review / correct points’ "
                "before relying on the measurements.",
            )
        summary += [self.t("component_note"), self.t("confidence_note")]
        self.overview.setText("\n\n".join(summary))
        self.result_tabs.setCurrentIndex(0)
        from qma_face.ui.analysis_cards import analysis_cards

        while self.cards_layout.count():
            self.cards_layout.takeAt(0).widget().deleteLater()
        self.cards_layout.addWidget(
            analysis_cards(self.analysis_report, self.language, compact=True)
        )
        sensitivity_cards = analysis_cards(self.analysis_report, self.language)
        self.sensitivity_page.setWidget(sensitivity_cards)
        sensitivity_cards.setAutoFillBackground(False)
        if self.working is not None:
            self.result_canvas.set_image(self.working)
            stored = self.analysis_report.get("landmarks", [])
            self.result_canvas.points = [point or [0, 0] for point in stored]
            self.result_canvas.visible_groups = dict(self.analysis_report["geometry"]["visibility"])
        attention = self.analysis_report.get("gradcam") or {}
        if self.working is not None:
            self.result_canvas.set_attention(attention.get("values"))
        self.attention_toggle.setChecked(False)
        self.attention_toggle.setEnabled(attention.get("status") == "available")
        while self.swatch_layout.count():
            item = self.swatch_layout.takeAt(0)
            item.widget().deleteLater()
        for color in self.analysis_report["palette"]["colors"]:
            swatch = QLabel()
            swatch.setFixedHeight(28)
            swatch.setStyleSheet(f"background: {color['hex']}; border-radius: 8px;")
            swatch.setToolTip(color["hex"])
            self.swatch_layout.addWidget(swatch)
        self.status.setText("")
        self.set_step(2)

    @classmethod
    def saved_result(cls, report, language, parent=None, source_image=None):
        """Display existing evidence without recomputing it or substituting another photo."""
        photo = None
        if source_image is not None:
            original = pil_image(source_image)
            if photo_digest(original) == report.get("source_photo_sha256"):
                preparation = report.get("preparation", {})
                rotated = original.rotate(
                    -preparation.get("rotation_degrees_clockwise", 0), expand=True
                )
                crop = rotated.crop(tuple(report["crop_box"]))
                if photo_digest(crop) == report.get("working_photo_sha256"):
                    photo = crop
        dialog = cls(qt_image(photo or Image.new("RGB", (32, 32), "white")), language, parent)
        dialog.working = photo
        dialog.analysis_report = copy.deepcopy(report)
        dialog.display_report()
        dialog.back.hide()
        dialog.review_result.hide()
        dialog.accept_button.hide()
        dialog.continue_button.setText(dialog.t("close"))
        if photo is None:
            dialog.result_canvas.hide()
            dialog.attention_toggle.hide()
            dialog.expand_result.hide()
            dialog.photo_unavailable.show()
        dialog.steps.setText("Analyse enregistrée" if language == "fr" else "Saved analysis")
        return dialog

    def toggle_attention(self, checked):
        self.result_canvas.show_attention = checked
        self.result_canvas.update()

    def go_back(self):
        if self.worker is None:
            self.analysis_report = None
            self.set_step(max(0, self.pages.currentIndex() - 1))

    def export_result(self):
        if not self.analysis_report:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, self.t("export_analysis"), "QMA-Face-analysis.json", self.t("export_filter")
        )
        if path:
            try:
                from pathlib import Path

                Path(path).write_text(
                    json.dumps(self.analysis_report, ensure_ascii=False, indent=2, allow_nan=False),
                    encoding="utf-8",
                )
            except OSError:
                self.status.setText(self.t("export_failed"))

    def export_document(self):
        if self.analysis_report:
            from qma_face.ui.report_dialog import ReportDialog

            dialog = ReportDialog(
                text_report(self.analysis_report, self.language),
                self.language,
                self,
                engine_hash=self.analysis_report["checkpoint_sha256"],
            )
            dialog.exec()
            dialog.deleteLater()

    def reject(self):
        if self.worker is not None and self.worker.isRunning():
            self._close_requested = True
            self.worker.cancel_event.set()
            self.status.setText(self.t("cancelled"))
            return
        super().reject()

    def closeEvent(self, event):
        if self.worker is not None and self.worker.isRunning():
            self.reject()
            event.ignore()
        else:
            super().closeEvent(event)
