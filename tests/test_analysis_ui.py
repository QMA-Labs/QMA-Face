import os
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pytest
from PIL import Image
from PySide6.QtWidgets import QApplication

from qma_face.services.analysis import AnalysisCancelled
from qma_face.services.geometry import GROUPS, measurements, photo_palette
from qma_face.ui.analysis_dialog import AnalysisDialog
from qma_face.ui.face_canvas import qt_image
from qma_face.ui.fonts import configure_fonts


class FakeAnalysis:
    """UI contract fixture. Real model evidence is in the integration report."""

    def locate(self, image, confirmed, cancel=None):
        if cancel and cancel.is_set():
            raise AnalysisCancelled()
        return {"landmarks": [[0.2 + (i % 11) * 0.06, 0.2 + (i // 11) * 0.07] for i in range(86)]}

    def explain(self, image, points, visible, original=None, cancel=None):
        if cancel and cancel.is_set():
            raise AnalysisCancelled()
        score = 50.0 if all(visible.values()) else None
        return {
            "score_0_to_100": score,
            "raw_score_1_to_5": 3 if score is not None else None,
            "score_status": "experimental_model_estimate"
            if score is not None
            else "withheld_occlusion",
            "scale_mapping": "(raw_1_to_5 - 1) * 25",
            "component_scores": None,
            "confidence": None,
            "geometry": measurements(points, image.size, visible),
            "palette": photo_palette(image),
            "regions": [],
            "gradcam": None,
            "explanation_kind": "local_model_sensitivity_not_causal_or_additive_deductions",
            "checkpoint_sha256": "test-only",
            "limitations": ["Test fixture; not model performance."],
        }


def wait(dialog, app):
    deadline = time.monotonic() + 4
    idle = 0
    while idle < 3 and time.monotonic() < deadline:
        app.processEvents()
        idle = idle + 1 if dialog.worker is None and not dialog._pending_auto_result else 0
        time.sleep(0.005)
    app.processEvents()
    assert dialog.worker is None


@pytest.fixture
def dialog():
    app = QApplication.instance() or QApplication([])
    configure_fonts(app)
    y, x = np.indices((256, 256))
    values = (60 + ((x // 9 + y // 9) % 2) * 120).astype("uint8")
    photo = Image.fromarray(values).convert("RGB")
    window = AnalysisDialog(qt_image(photo), "fr", service=FakeAnalysis())
    window.show()
    app.processEvents()
    yield window, app
    window.reject()
    if window.worker:
        wait(window, app)
    app.processEvents()


def test_quality_and_map_review_gate_the_flow(dialog):
    window, app = dialog
    assert not window.next_points.isEnabled()
    window.check_photo()
    assert not window.next_points.isEnabled()
    window.face_confirm.setChecked(True)
    assert window.next_points.isEnabled()
    window.locate_points()
    wait(window, app)
    assert window.pages.currentIndex() == 1
    assert not window.next_result.isEnabled()
    window.points_confirm.setChecked(True)
    assert window.next_result.isEnabled()
    window.points_edited()
    assert not window.next_result.isEnabled()


def test_guided_flow_one_click_then_optional_manual_review(dialog, tmp_path):
    original, app = dialog
    window = AnalysisDialog(
        qt_image(original.source), "en", service=FakeAnalysis(), guided_auto=True
    )
    window.show()
    app.processEvents()
    assert window.working is not None
    assert window.analysis_report is None
    window.next_points.click()
    app.processEvents()
    wait(window, app)
    assert window.pages.currentIndex() == 2
    assert window.analysis_report["points_manually_reviewed"] is False
    assert window.analysis_report["landmarks_source"] == "model_points_not_manually_reviewed"
    window.review_result.click()
    assert window.pages.currentIndex() == 1
    window.points_confirm.setChecked(True)
    app.processEvents()
    wait(window, app)
    assert window.pages.currentIndex() == 2
    assert window.analysis_report["score_0_to_100"] == 50
    assert window.analysis_report["points_manually_reviewed"] is True
    assert "50.0 / 100" in window.overview.text()
    assert window.cards_layout.count() == 1
    assert not window.progress.isVisible()
    assert window.grab().save(str(tmp_path / "guided-result.png"))
    window.reject()


def test_hidden_points_and_overall_score_are_not_exported_as_observations(dialog):
    window, app = dialog
    window.check_photo()
    window.face_confirm.setChecked(True)
    window.locate_points()
    wait(window, app)
    window.group_checks["nose"].setChecked(False)
    window.points_confirm.setChecked(True)
    window.compute_result()
    wait(window, app)
    assert window.pages.currentIndex() == 2
    report = window.analysis_report
    assert report["score_0_to_100"] is None
    assert all(report["landmarks"][number - 1] is None for number in GROUPS["nose"])
    assert report["component_scores"] is None
    assert "Score indisponible" in window.score.text()


def test_selecting_a_new_crop_invalidates_prior_quality_confirmation(dialog):
    window, _ = dialog
    window.check_photo()
    window.face_confirm.setChecked(True)
    assert window.next_points.isEnabled()
    window.rotate()
    assert window.working is None
    assert not window.face_confirm.isChecked()
    assert not window.next_points.isEnabled()


def test_dialog_cancel_waits_for_worker_without_saving_partial_result(dialog):
    window, app = dialog

    def cancellable(cancel):
        cancel.wait(2)
        raise AnalysisCancelled()

    window._run(cancellable, lambda result: pytest.fail("Cancelled result was accepted"), "finding")
    window.reject()
    wait(window, app)
    assert window.analysis_report is None
    assert not window.isVisible()


def test_json_export_saves_results_without_photo_bytes(dialog, tmp_path, monkeypatch):
    import json

    from PySide6.QtWidgets import QFileDialog

    window, app = dialog
    window.check_photo()
    window.face_confirm.setChecked(True)
    window.locate_points()
    wait(window, app)
    window.points_confirm.setChecked(True)
    window.compute_result()
    wait(window, app)
    destination = tmp_path / "analysis.json"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *args: (str(destination), "JSON"))
    window.export_result()
    exported = json.loads(destination.read_text(encoding="utf-8"))
    assert exported["schema_version"] == 1
    assert exported["component_scores"] is None
    assert len(exported["landmarks"]) == 86
    assert "data:image" not in destination.read_text(encoding="utf-8")


def test_dragging_crop_and_points_updates_the_actual_canvas(dialog):
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest

    window, app = dialog
    canvas = window.crop_canvas
    rect = canvas.image_rect()
    first = QPoint(round(rect.x() + rect.width() * 0.1), round(rect.y() + rect.height() * 0.1))
    last = QPoint(round(rect.x() + rect.width() * 0.9), round(rect.y() + rect.height() * 0.9))
    QTest.mousePress(canvas, Qt.MouseButton.LeftButton, pos=first)
    QTest.mouseMove(canvas, last)
    QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=last)
    app.processEvents()
    assert 0.75 < canvas.crop.width() < 0.85
    window.check_photo()
    window.face_confirm.setChecked(True)
    window.locate_points()
    wait(window, app)
    canvas = window.map_canvas
    rect = canvas.image_rect()
    point = canvas.points[0]
    first = QPoint(
        round(rect.x() + point[0] * rect.width()), round(rect.y() + point[1] * rect.height())
    )
    last = first + QPoint(7, 4)
    QTest.mousePress(canvas, Qt.MouseButton.LeftButton, pos=first)
    QTest.mouseMove(canvas, last)
    QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=last)
    app.processEvents()
    assert window.edited_points is True
    assert not window.points_confirm.isChecked()
