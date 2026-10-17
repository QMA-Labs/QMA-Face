import copy

import numpy as np
from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from qma_face.core.storage import ChatStore
from qma_face.research.data import augment_photo_points
from qma_face.services.geometry import GROUPS, measurements
from qma_face.ui.analysis_cards import analysis_cards
from qma_face.ui.translator_dialog import TranslatorDialog
from qma_face.ui.window import FaceWindow
from qma_face.ui.worker import ReplyWorker


def test_affine_augmentation_moves_pixels_and_annotations_together():
    pixels = np.zeros((80, 80, 3), dtype=np.uint8)
    pixels[38:43, 38:43, 0] = 255
    image = Image.fromarray(pixels)
    points = np.array([[0.5, 0.5], [0.99, 0.01]], dtype=np.float32)
    matrix = np.array([[1, 0, 0.1], [0, 1, -0.1], [0, 0, 1]])
    photo, moved, included = augment_photo_points(image, points, matrix)
    assert np.allclose(moved[0], [0.6, 0.4])
    assert included.tolist() == [True, False]
    assert np.asarray(photo)[32, 48, 0] > 150
    assert np.asarray(photo)[40, 40, 0] < 80
    assert np.allclose(points[0], [0.5, 0.5])


class TranslationBackend:
    def __init__(self, truncated=False):
        self.truncated = truncated
        self.generated = []

    def translate(self, text, target, cancel, on_piece, status):
        assert text == "این عکس را بررسی کن" and target == "English"
        return {"text": "Review this photo.", "truncated": self.truncated}

    def generate(self, messages, language, image, cancel, on_piece, status):
        self.generated.append(messages)
        return {"text": "A test response."}


def test_persian_input_is_translated_without_modifying_original_history():
    backend = TranslationBackend()
    original = [
        {
            "role": "user",
            "content": "این عکس را بررسی کن",
            "metadata": {"_translate_persian_input": True},
        }
    ]
    before = copy.deepcopy(original)
    worker = ReplyWorker(backend, original, "en", None)
    completed = []
    worker.complete.connect(completed.append)
    worker.run()
    assert backend.generated[0][-1]["content"] == "Review this photo."
    assert original == before
    assert completed[0]["input_translation"]["machine_translation"]


def test_partial_input_translation_is_never_sent_to_chat_model():
    backend = TranslationBackend(truncated=True)
    worker = ReplyWorker(
        backend,
        [
            {
                "role": "user",
                "content": "این عکس را بررسی کن",
                "metadata": {"_translate_persian_input": True},
            }
        ],
        "en",
        None,
    )
    failures = []
    worker.failed.connect(failures.append)
    worker.run()
    assert not backend.generated and failures == ["request_failed"]


def test_previous_persian_messages_reuse_saved_english_without_retranslation():
    backend = TranslationBackend()
    history = [
        {"role": "user", "content": "پرسش قبلی", "metadata": {}},
        {
            "role": "assistant",
            "content": "Earlier answer.",
            "metadata": {
                "input_translation": {"target_language": "English", "text": "Previous question."}
            },
        },
        {"role": "user", "content": "Continue.", "metadata": {"_translate_persian_input": True}},
    ]
    worker = ReplyWorker(backend, history, "en", None)
    worker.run()
    assert backend.generated[0][0]["content"] == "Previous question."
    assert history[0]["content"] == "پرسش قبلی"


def test_missing_exposure_value_does_not_break_withheld_result_cards():
    app = QApplication.instance() or QApplication([])
    panel = analysis_cards(
        {"score_0_to_100": None, "regions": [], "exposure_stability": {"largest_abs_change": None}},
        "en",
    )
    panel.show()
    app.processEvents()
    assert panel.isVisible()
    panel.close()


def test_eye_geometry_warning_is_a_review_request_and_respects_hidden_groups():
    points = np.full((86, 2), 0.5)
    for number, xy in {
        1: (0.5, 0.05),
        12: (0.5, 0.95),
        6: (0.2, 0.5),
        18: (0.8, 0.5),
        43: (0.3, 0.45),
        47: (0.4, 0.45),
        45: (0.35, 0.40),
        49: (0.35, 0.46),
        51: (0.6, 0.45),
        55: (0.7, 0.45),
        53: (0.65, 0.43),
        57: (0.65, 0.46),
        59: (0.35, 0.45),
        60: (0.65, 0.45),
    }.items():
        points[number - 1] = xy
    visible = {group: True for group in GROUPS}
    result = measurements(points, (300, 300), visible)
    assert "review_eye_points" in result["review_flags"]
    assert result["review_flags_are_heuristics_not_diagnoses"]
    visible["eyes"] = False
    assert "review_eye_points" not in measurements(points, (300, 300), visible)["review_flags"]


def test_persian_numeric_display_preserves_raw_translation_for_copy_and_sending():
    app = QApplication.instance() or QApplication([])
    dialog = TranslatorDialog(None, "score", "en")
    raw = "امتیاز: 54.13 / 100 [S1]"
    dialog.complete({"text": raw, "truncated": False})
    assert "\u206654.13 / 100\u2069" in dialog.output.toPlainText()
    assert dialog.translated_text == raw
    dialog.copy_output()
    assert app.clipboard().text() == raw
    dialog.reject()


def test_persian_composer_alignment_changes_without_altering_text(tmp_path):
    app = QApplication.instance() or QApplication([])
    backend = TranslationBackend()
    backend.stop = lambda: None
    window = FaceWindow(store=ChatStore(tmp_path / "data"), backend=backend, resume=False)
    source = "لطفاً این عکس را بررسی کن"
    window.question.setPlainText(source)
    app.processEvents()
    assert window.question.toPlainText() == source
    assert (
        window.question.document().firstBlock().blockFormat().alignment()
        == Qt.AlignmentFlag.AlignRight
    )
    window.question.setPlainText("Explain this photo.")
    assert (
        window.question.document().firstBlock().blockFormat().alignment()
        == Qt.AlignmentFlag.AlignLeft
    )
    window.close()
