import copy
import io
import json
import threading

import pytest
from PySide6.QtWidgets import QApplication, QMessageBox

from qma_face.core.storage import ChatStore
from qma_face.services.comparison import compare_reports, comparison_answer, comparison_text
from qma_face.services.library import checked_source_answer, source_filter
from qma_face.services.local_ai import LocalAI, bounded_messages
from qma_face.services.report_export import export_report, report_html
from qma_face.ui.comparison_dialog import ComparisonDialog
from qma_face.ui.window import FaceWindow


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def sample(index, *, score=50, quality="usable", metric=1.2, date=""):
    """Synthetic calculation fixture; never an evaluation of the real face model."""
    return {
        "label": f"Photo {index}",
        "date": date,
        "angle": "front",
        "expression": "neutral",
        "report": {
            "source_photo_sha256": str(index),
            "checkpoint_sha256": "engine-a",
            "status": "research_preview",
            "score_0_to_100": score,
            "preparation": {"after": {"status": quality}},
            "geometry": {"metrics": [{"name": "face_height_to_width", "value": metric}]},
        },
    }


def test_comparison_uses_quality_not_beauty_and_reports_actual_spread():
    data = compare_reports(
        [sample(1, score=99, quality="adjustable"), sample(2, score=10, metric=1.4)],
        same_person_confirmed=True,
    )
    assert data["quality_pick"] == "Photo 2"
    assert data["score_summary"] == {"n": 2, "min": 10, "max": 99, "range": 89}
    assert data["signature"][0]["median"] == pytest.approx(1.3)
    assert data["apparent_age"] is None and data["rarity"] is None
    assert not data["identity_verified"]
    assert "not an aging model" not in comparison_text(data, "en")  # no dated observations
    assert "aucune" in comparison_text(data, "fr").lower()


@pytest.mark.parametrize("change", ["consent", "duplicate", "engine", "date", "nan"])
def test_invalid_or_uncomparable_collections_are_rejected(change):
    items = [sample(1), sample(2)]
    if change == "duplicate":
        items[1] = copy.deepcopy(items[0])
    if change == "engine":
        items[1]["report"]["checkpoint_sha256"] = "engine-b"
    if change == "date":
        items[1]["date"] = "2025-02-30"
    if change == "nan":
        items[1]["report"]["score_0_to_100"] = float("nan")
    with pytest.raises(ValueError):
        compare_reports(items, same_person_confirmed=change != "consent")


def test_withheld_values_and_insufficient_groups_are_not_filled_in():
    items = [sample(1, score=None, metric=None), sample(2)]
    data = compare_reports(items, same_person_confirmed=True)
    assert data["score_summary"] is None
    assert data["signature"] == [] and data["labeled_groups"] == []


def test_labeled_groups_and_dates_are_only_descriptive():
    items = [sample(i, score=i * 10, date=f"2024-01-0{i}") for i in range(1, 5)]
    for item in items[2:]:
        item["expression"] = "smile"
    data = compare_reports(items, same_person_confirmed=True)
    assert len(data["labeled_groups"]) == 1
    assert data["labeled_groups"][0]["groups"][1]["mean"] == 35
    assert len(data["timeline"]) == 4
    assert "not an aging model" in comparison_text(data, "en")
    assert "causal" in comparison_text(data, "en")


def test_collection_chat_requires_selected_collection_and_never_scores_trust():
    messages = [{"role": "user", "content": "Compare my photos", "metadata": {}}]
    assert comparison_answer(messages, "en") is None
    data = compare_reports([sample(1), sample(2)], same_person_confirmed=True)
    messages[0]["metadata"]["_active_comparison"] = data
    assert comparison_answer(messages, "en")["answer_kind"] == "collection_calculation"
    messages[0]["content"] = "Compare trustworthiness"
    assert comparison_answer(messages, "en") is None


def test_memory_store_writes_no_chat_or_photo_files_and_loses_data_on_close(tmp_path):
    root = tmp_path / "must-not-be-created"
    store = ChatStore(root, memory=True)
    identity = store.create_chat("en", "private")
    store.add_message(identity, "assistant", "sensitive", {"analysis": {"score": 1}})
    with pytest.raises(ValueError):
        store.attachment_path(identity)
    store.delete_chat(identity)
    assert store.list_chats() == []
    assert not root.exists()
    store.close()
    reopened = ChatStore(root, memory=True)
    assert reopened.list_chats() == []
    reopened.close()


def test_erasing_analysis_removes_paraphrases_and_managed_copies_only(tmp_path):
    store = ChatStore(tmp_path / "data")
    original = tmp_path / "original.png"
    original.write_bytes(b"original")
    identity = store.create_chat("fr", "test")
    store.add_message(identity, "user", "My question")
    store.add_message(identity, "assistant", "Numbers", {"analysis": {"score": 1}})
    store.add_message(identity, "assistant", "Paraphrased derived features")
    store.attachment_path(identity).write_bytes(b"managed-copy")
    store.delete_analysis(identity)
    assert [m["content"] for m in store.messages(identity)] == ["My question"]
    store.delete_all_chats()
    assert not list(store.attachments.iterdir()) and store.list_chats() == []
    assert original.read_bytes() == b"original"


def test_modes_body_limit_and_collection_history_bounding():
    messages = [
        {"role": "assistant", "content": "old measurements", "metadata": {"comparison": {}}},
        {"role": "user", "content": "Describe hands", "metadata": {"_answer_style": "casual"}},
    ]
    result = bounded_messages(messages, "fr", None)
    assert "everyday" in result[0]["content"]
    assert "still image cannot" in result[0]["content"]
    assert "numerical apparent age" in result[0]["content"]


def test_age_request_returns_honest_limit_without_model(tmp_path):
    ai = LocalAI(root=tmp_path, log_root=tmp_path)
    for language, question in (("en", "What is my apparent age?"), ("fr", "Quel âge apparent ?")):
        chunks = []
        answer = ai.generate(
            [{"role": "user", "content": question}],
            language,
            None,
            threading.Event(),
            chunks.append,
        )
        assert answer["answer_kind"] == "capability_limit"
        assert ai.process is None and answer["model"] is None
        assert "".join(chunks) == answer["text"]


def test_source_draft_is_buffered_and_photo_results_do_not_become_source_claims(
    tmp_path, monkeypatch
):
    ai = LocalAI(root=tmp_path, log_root=tmp_path)
    passage = {
        "citation_id": "S1",
        "title": "Dataset",
        "text": "Real curated excerpt.",
        "limitations": "Frontal-face collection only.",
        "type": "conference_paper_arxiv_copy",
    }
    monkeypatch.setattr(ai, "ensure_started", lambda *args: None)
    monkeypatch.setattr(ai, "_source_keywords", lambda *args: "dataset")
    monkeypatch.setattr(ai.library, "synchronize", lambda: None)
    monkeypatch.setattr(ai.library, "search", lambda *args, **kwargs: [passage])

    def request(path, payload, timeout):
        context = json.dumps(payload["messages"])
        assert "old invented numerical claim" not in context
        user_context = json.dumps([m for m in payload["messages"] if m["role"] == "user"])
        assert "image_url" not in user_context and "RESEARCH_ANALYSIS_JSON" not in user_context
        event = {"choices": [{"delta": {"content": "UNCITED DRAFT MUST NOT LEAK"}}]}
        return io.BytesIO(("data: " + json.dumps(event) + "\n\ndata: [DONE]\n").encode())

    monkeypatch.setattr(ai, "_request", request)
    chunks = []
    answer = ai.generate(
        [
            {"role": "assistant", "content": "old invented numerical claim"},
            {
                "role": "user",
                "content": "What does the SCUT article say?",
                "metadata": {"_photo_sha256": "x"},
            },
        ],
        "en",
        b"image",
        threading.Event(),
        chunks.append,
    )
    assert "UNCITED DRAFT" not in "".join(chunks) + answer["text"]
    assert "Real curated excerpt" in answer["text"]
    assert answer["analysis_photo_sha256"] is None
    assert answer["citation_validation"] == "uncited_draft_withheld_source_extracts_only"
    assert source_filter("SCUT-FBP5500 research article") == "scut-fbp5500"
    assert source_filter("Compare SCUT versus another paper") is None
    valid, policy = checked_source_answer("A statement [S1].", [passage], "fr")
    assert valid == "A statement [S1]." and "not_claim_entailment" in policy
    invalid, policy = checked_source_answer("A statement [S99].", [passage], "fr")
    assert "A statement" not in invalid and "extraits" in invalid


def test_export_escapes_private_sources_and_defaults_to_no_excerpts(app, tmp_path):
    sources = [
        {
            "citation_id": "S1",
            "title": "A <script>bad</script>",
            "page": 4,
            "text": "متن فارسی آزمایشی",
            "type": "teaching_notes",
        }
    ]
    markup = report_html(
        "<img src='https://example.invalid/track'>", language="fr", sources=sources
    )
    assert "<img" not in markup and "&lt;script&gt;" in markup
    assert "متن فارسی" not in markup
    private = report_html("Results", language="fr", sources=sources, include_excerpts=True)
    assert 'dir="rtl"' in private and "متن فارسی" in private
    for extension in ("pdf", "html", "png"):
        path = tmp_path / f"report.{extension}"
        export_report(
            path,
            "Experimental result: 50 / 100",
            language="en",
            sources=sources,
            include_excerpts=True,
        )
        assert path.stat().st_size > 200
    assert (tmp_path / "report.pdf").read_bytes().startswith(b"%PDF")


def test_collection_ui_gate_and_temporary_session_preserve_saved_chats(app, tmp_path, monkeypatch):
    class Backend:
        def stop(self):
            pass

    monkeypatch.setattr(QMessageBox, "information", lambda *args: None)
    store = ChatStore(tmp_path / "data")
    saved = store.create_chat("en", "saved")
    window = FaceWindow(store=store, backend=Backend(), resume=False)
    window.toggle_private()
    assert window.store.memory and not window.keep_photo.isEnabled()
    window.start_conversation()
    temporary = window.chat_id
    window.store.add_message(temporary, "user", "private-content")
    assert store.get_chat(temporary) is None
    window.toggle_private()
    assert window.store.get_chat(saved) and window.store.get_chat(temporary) is None
    collection = ComparisonDialog("fr", window)
    collection.items = [sample(1), sample(2)]
    collection.compute()
    assert not collection.save.isEnabled()
    collection.same_person.setChecked(True)
    collection.compute()
    assert collection.save.isEnabled()
    collection.list.addItem("Photo 1")
    collection.list.setCurrentRow(0)
    collection.remove_item()
    assert not collection.save.isEnabled() and collection.comparison_report is None
    collection.close()
    window.close()
