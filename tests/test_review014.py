import copy

from PIL import Image
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QApplication

from qma_face.services.geometry import GROUPS, measurements, photo_palette
from qma_face.services.photo_quality import photo_digest
from qma_face.ui.analysis_dialog import AnalysisDialog
from qma_face.ui.face_canvas import FaceCanvas, qt_image


def saved_report(photo):
    points = [[0.2 + (i % 11) * 0.06, 0.2 + (i // 11) * 0.07] for i in range(86)]
    return {
        "score_0_to_100": 56.13,
        "raw_score_1_to_5": 3.2452,
        "score_status": "experimental_model_estimate",
        "scale_mapping": "(raw_1_to_5 - 1) * 25",
        "component_scores": None,
        "confidence": None,
        "geometry": measurements(points, photo.size, {key: True for key in GROUPS}),
        "palette": photo_palette(photo),
        "regions": [],
        "gradcam": None,
        "checkpoint_sha256": "fixture",
        "limitations": [],
        "landmarks": points,
        "source_photo_sha256": photo_digest(photo),
        "working_photo_sha256": photo_digest(photo),
        "crop_box": [0, 0, *photo.size],
        "preparation": {},
    }


def test_saved_graphical_report_never_reanalyses_or_changes_evidence():
    app = QApplication.instance() or QApplication([])
    photo = Image.new("RGB", (80, 100), "gray")
    report = saved_report(photo)
    before = copy.deepcopy(report)
    dialog = AnalysisDialog.saved_result(report, "en", source_image=qt_image(photo))
    dialog.show()
    app.processEvents()
    assert dialog.pages.currentIndex() == 2
    assert dialog.worker is None and dialog.service.candidate is None
    assert "56.1 / 100" in dialog.overview.text()
    assert dialog.result_canvas.isVisible()
    assert not dialog.back.isVisible()
    assert dialog.result_canvas.points == report["landmarks"]
    assert report == before
    dialog.reject()


def test_saved_report_never_attaches_an_unrelated_photo():
    app = QApplication.instance() or QApplication([])
    photo = Image.new("RGB", (80, 100), "gray")
    report = saved_report(photo)
    dialog = AnalysisDialog.saved_result(
        report, "fr", source_image=qt_image(Image.new("RGB", (80, 100), "red"))
    )
    dialog.show()
    app.processEvents()
    assert dialog.working is None and not dialog.result_canvas.isVisible()
    assert dialog.photo_unavailable.isVisible()
    assert dialog.analysis_report == report
    dialog.reject()


def test_zoom_preserves_photo_coordinates_at_cursor():
    app = QApplication.instance() or QApplication([])
    canvas = FaceCanvas("points")
    canvas.set_image(Image.new("RGB", (80, 100)))
    canvas.resize(600, 600)
    canvas.show()
    app.processEvents()
    anchor = QPointF(240, 250)
    before = canvas.normalized(anchor)
    event = QWheelEvent(
        anchor,
        anchor,
        QPointF().toPoint(),
        QPointF(0, 120).toPoint(),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )
    canvas.wheelEvent(event)
    after = canvas.normalized(anchor)
    assert canvas.zoom > 1
    assert abs(before.x() - after.x()) < 1e-8
    assert abs(before.y() - after.y()) < 1e-8
    canvas.reset_view()
    assert canvas.zoom == 1 and canvas.pan == QPointF()
    canvas.close()
