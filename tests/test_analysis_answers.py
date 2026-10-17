import threading

from qma_face.services.analysis_answers import analysis_answer
from qma_face.services.local_ai import LocalAI


def messages(question, delta=5.124):
    return [
        {
            "role": "user",
            "content": question,
            "metadata": {
                "_photo_sha256": "current",
                "_active_analysis": {
                    "status": "research_preview",
                    "photo_sha256": "current",
                    "score_0_to_100": 62.16,
                    "blur_sensitivity": [{"region": "nose", "delta_score_100_after_blur": delta}],
                    "metrics": [],
                },
            },
        }
    ]


def test_positive_and_negative_blur_changes_have_correct_meaning():
    result = analysis_answer(messages("Does the blur sensitivity prove the cause?"), "en", True)
    assert "+5.124 (higher)" in result["text"]
    assert "do not prove a cause" in result["text"]
    assert "unavailable (not trained)" in result["text"]
    result = analysis_answer(messages("Pourquoi mon score est bas ?", -5.124), "fr", True)
    assert "-5.124 (plus bas)" in result["text"]
    assert result["model"] is None


def test_numeric_answers_work_without_starting_another_model(tmp_path):
    backend = LocalAI(root=tmp_path, log_root=tmp_path)
    chunks = []
    result = backend.generate(
        messages("Why not 100?"), "en", b"current-image", threading.Event(), chunks.append
    )
    assert backend.process is None
    assert result["answer_kind"] == "structured_analysis_explanation"
    assert "37.8" in result["text"]
    assert "".join(chunks) == result["text"]


def test_missing_photo_or_different_photo_never_gets_the_old_answer():
    assert analysis_answer(messages("Why this score?"), "en", False) is None
    changed = messages("Why this score?")
    changed[0]["metadata"]["_photo_sha256"] = "another"
    assert analysis_answer(changed, "en", True) is None
    assert analysis_answer(messages("What does the PDF say about beauty?"), "en", True) is None


def test_beauty_number_is_never_used_as_a_trustworthiness_score():
    result = analysis_answer(messages("Give me a trustworthiness score from this face"), "en", True)
    assert result["answer_kind"] == "appearance_trait_boundary"
    assert "62.2" not in result["text"]
