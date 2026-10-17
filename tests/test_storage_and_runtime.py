import sqlite3
import threading

import pytest

from qma_face.core.storage import ChatStore
from qma_face.services.local_ai import (
    GenerationCancelled,
    LocalAI,
    ModelUnavailable,
    bounded_messages,
    system_prompt,
)


def test_chat_deletion_cascades_messages_but_leaves_other_chat(tmp_path):
    store = ChatStore(tmp_path)
    first = store.create_chat("en", "First")
    second = store.create_chat("fr", "Second")
    store.add_message(first, "user", "Quoted '; DELETE FROM chats; --")
    store.add_message(second, "user", "Bonjour")
    store.attachment_path(first).write_bytes(b"test attachment")
    store.delete_chat(first)
    assert store.messages(first) == []
    assert store.get_chat(second)["title"] == "Bonjour"
    assert store.messages(second)[0]["content"] == "Bonjour"
    assert not store.attachment_path(first).exists()


def test_unsupported_language_and_photo_path_traversal_are_rejected(tmp_path):
    store = ChatStore(tmp_path)
    with pytest.raises(ValueError):
        store.create_chat("fa", "Invalid")
    with pytest.raises(ValueError):
        store.attachment_path("../outside")


def test_schema_version_is_not_silently_downgraded(tmp_path):
    store = ChatStore(tmp_path)
    with store.connection() as connection:
        connection.execute("PRAGMA user_version=2")
    with pytest.raises(ValueError, match="newer"):
        ChatStore(tmp_path)
    with sqlite3.connect(store.database) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 2


def test_missing_models_and_pre_cancelled_request_never_start_process(tmp_path):
    backend = LocalAI(root=tmp_path, log_root=tmp_path)
    with pytest.raises(ModelUnavailable):
        backend.ensure_started(threading.Event())
    cancel = threading.Event()
    cancel.set()
    with pytest.raises(GenerationCancelled):
        backend.ensure_started(cancel)
    assert backend.process is None


def test_request_budget_keeps_latest_user_and_attaches_only_current_image():
    messages = [{"role": "user", "content": f"old {i} " + ("x" * 1000)} for i in range(20)]
    messages += [{"role": "user", "content": "latest question"}]
    result = bounded_messages(messages, "fr", b"image-bytes")
    assert len(result) <= 9
    assert result[0]["role"] == "system"
    assert "only in French" in result[0]["content"]
    assert result[-1]["content"][0]["text"] == "latest question"
    assert result[-1]["content"][1]["image_url"]["url"].startswith("data:image/jpeg;base64,")
    assert sum(isinstance(x["content"], list) for x in result) == 1


def test_cancelled_and_error_replies_are_excluded_from_model_context():
    messages = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Partial", "metadata": {"status": "cancelled"}},
        {"role": "assistant", "content": "Unavailable", "metadata": {"status": "error"}},
        {"role": "user", "content": "Try again"},
    ]
    context = bounded_messages(messages, "en", None)
    assert [x["content"] for x in context[1:]] == ["Hello", "Try again"]


def test_prompt_does_not_claim_measurements_or_pdf_evidence():
    prompt = system_prompt("en", False)
    assert "No validated beauty-engine" in prompt
    assert "No photo is attached" in prompt
    assert "Never infer personality" in prompt


def test_temporary_auth_key_is_cleaned_on_stop(tmp_path):
    backend = LocalAI(root=tmp_path, log_root=tmp_path)
    key = tmp_path / "test.key"
    key.write_text("temporary-test-key")
    backend._key_path = key
    backend.stop()
    assert not key.exists()
