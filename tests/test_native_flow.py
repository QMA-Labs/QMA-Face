import os
import threading
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

from qma_face.core.i18n import TRANSLATIONS, tr
from qma_face.core.storage import ChatStore
from qma_face.services.local_ai import GenerationCancelled
from qma_face.ui.fonts import configure_fonts
from qma_face.ui.window import FaceWindow


class FakeBackend:
    def __init__(self):
        self.cancelled = threading.Event()
        self.calls = []

    def generate(self, messages, language, image, cancel, on_piece, status):
        self.calls.append((messages, language, image))
        status("thinking")
        text = "A local test reply." if language == "en" else "Une réponse de test locale."
        on_piece(text)
        return {"text": text, "device": "test", "duration_s": 0.01}

    def cancel_generation(self):
        self.cancelled.set()

    def stop(self):
        pass


@pytest.fixture(scope="module")
def application():
    app = QApplication.instance() or QApplication([])
    app.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
    configure_fonts(app)
    return app


@pytest.fixture
def window(application, tmp_path):
    result = FaceWindow(store=ChatStore(tmp_path / "data"), backend=FakeBackend())
    result.show()
    application.processEvents()
    yield result
    result.close()
    application.processEvents()


def test_suggestions_fill_composer_without_sending(window):
    from PySide6.QtWidgets import QPushButton

    window.begin_new_chat()
    window.start_conversation()
    window.add_analysis_suggestions()
    buttons = window.transcript.findChildren(QPushButton)
    reflection = next(button for button in buttons if button.text() == "Self-reflection")
    before = len(window.store.messages(window.chat_id))
    reflection.click()
    assert "based on my answers" in window.question.toPlainText()
    assert "without inferring personality" in window.question.toPlainText()
    assert len(window.store.messages(window.chat_id)) == before
    assert not window.backend.calls


def photo_file(tmp_path):
    image = QImage(160, 200, QImage.Format.Format_RGB32)
    image.fill(Qt.GlobalColor.white)
    path = tmp_path / "photo.png"
    image.save(str(path))
    return path


def wait_reply(window, application):
    deadline = time.monotonic() + 3
    while window.worker is not None and time.monotonic() < deadline:
        application.processEvents()
        time.sleep(0.01)
    assert window.worker is None


def test_home_actions_open_their_actual_screens(window):
    window.new_chat.click()
    assert window.current_screen == "upload"
    window.back.click()
    window.my_chats.click()
    assert window.current_screen == "chats"
    window.empty_new_chat.click()
    assert window.current_screen == "upload"


def test_only_english_and_french_are_available_and_persist(window):
    assert [window.language_picker.itemData(i) for i in range(window.language_picker.count())] == [
        "en",
        "fr",
    ]
    window.language_picker.setCurrentIndex(1)
    assert window.home_title.text() == tr("home_title", "fr")
    assert window.store.setting("language") == "fr"
    assert set(TRANSLATIONS["en"]) == set(TRANSLATIONS["fr"])
    with pytest.raises(ValueError):
        tr("home_title", "fa")


def test_language_switch_preserves_unsent_message(window):
    window.begin_new_chat()
    window.start_conversation()
    window.question.setPlainText("Keep this draft")
    window.language_picker.setCurrentIndex(1)
    assert window.question.toPlainText() == "Keep this draft"
    assert window.store.get_chat(window.chat_id)["language"] == "fr"


def test_long_message_is_rejected_without_silent_truncation(window):
    window.begin_new_chat()
    window.start_conversation()
    window.question.setPlainText("x" * 3001)
    window.send_message()
    assert window.store.messages(window.chat_id) == []
    assert window.question.toPlainText() == "x" * 3001
    assert window.request_status.text() == tr("message_too_long", "en")


def test_invalid_upload_preserves_the_previous_photo(window, tmp_path):
    window.begin_new_chat()
    path = photo_file(tmp_path)
    original_bytes = path.read_bytes()
    window.select_photo(str(path))
    assert window.selected_image == path
    assert window.photo_preview.isVisible()
    assert window.keep_photo.isChecked() is False
    broken = tmp_path / "broken.png"
    broken.write_bytes(b"not an image")
    window.select_photo(str(broken))
    assert window.selected_image == path
    assert window.photo_error.isVisible()
    assert path.read_bytes() == original_bytes


def test_an_oversized_image_header_is_rejected_before_decode(window, tmp_path):
    import struct
    import zlib

    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data))

    header = struct.pack(">IIBBBBB", 20000, 20000, 8, 2, 0, 0, 0)
    path = tmp_path / "huge.png"
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IEND", b""))
    window.begin_new_chat()
    window.select_photo(str(path))
    assert window.selected_image is None
    assert window.photo_error.isVisible()


def test_real_history_flow_and_restart_resume(window, application):
    window.begin_new_chat()
    window.without_photo.click()
    identity = window.chat_id
    window.question.setPlainText("Explain this ratio.")
    window.send.click()
    wait_reply(window, application)
    messages = window.store.messages(identity)
    assert [m["role"] for m in messages] == ["user", "assistant"]
    assert messages[1]["content"] == "A local test reply."
    assert window.store.get_chat(identity)["title"] == "Explain this ratio."
    window.close()
    resumed = FaceWindow(store=window.store, backend=FakeBackend())
    assert resumed.current_screen == "chat"
    assert resumed.chat_id == identity
    assert resumed.store.messages(identity) == messages
    resumed.close()


def test_photo_is_not_saved_without_opt_in(window, application, tmp_path):
    path = photo_file(tmp_path)
    window.begin_new_chat()
    window.select_photo(str(path))
    window.start_conversation()
    identity = window.chat_id
    assert not window.store.attachment_path(identity).exists()
    window.close()
    resumed = FaceWindow(store=window.store, backend=FakeBackend())
    assert identity not in resumed.active_images
    assert resumed.chat_photo_note.text() == tr("photo_missing", "en")
    resumed.close()
    assert path.exists()


def test_opt_in_photo_is_restored_and_deleted_with_chat(window, application, tmp_path):
    path = photo_file(tmp_path)
    original = path.read_bytes()
    window.begin_new_chat()
    window.select_photo(str(path))
    window.keep_photo.setChecked(True)
    window.start_conversation()
    identity = window.chat_id
    saved = window.store.attachment_path(identity)
    assert saved.exists()
    window.close()
    resumed = FaceWindow(store=window.store, backend=FakeBackend())
    assert identity in resumed.active_images
    resumed.delete_chat(identity)
    assert not saved.exists()
    assert resumed.store.get_chat(identity) is None
    assert path.read_bytes() == original
    resumed.close()


def test_reply_uses_selected_language_and_local_image(window, application, tmp_path):
    window.language_picker.setCurrentIndex(1)
    window.begin_new_chat()
    window.select_photo(str(photo_file(tmp_path)))
    window.start_conversation()
    window.question.setPlainText("Décris cette photo.")
    window.send_message()
    wait_reply(window, application)
    call = window.backend.calls[-1]
    assert call[1] == "fr"
    assert call[2].startswith(b"\xff\xd8")
    assert window.store.messages(window.chat_id)[-1]["content"] == "Une réponse de test locale."


def test_removing_photo_does_not_reuse_it_in_next_request(window, application, tmp_path):
    window.begin_new_chat()
    window.select_photo(str(photo_file(tmp_path)))
    window.start_conversation()
    window.remove_chat_photo()
    window.question.setPlainText("Hello")
    window.send_message()
    wait_reply(window, application)
    assert window.backend.calls[-1][2] is None


def test_cancelled_reply_is_not_misrepresented_as_completed(window, application):
    class SlowBackend(FakeBackend):
        def generate(self, messages, language, image, cancel, on_piece, status):
            on_piece("Partial reply")
            while not cancel.wait(0.01):
                pass
            raise GenerationCancelled()

    window.backend = SlowBackend()
    window.begin_new_chat()
    window.start_conversation()
    window.question.setPlainText("Hello")
    window.send_message()
    deadline = time.monotonic() + 2
    while not window.reply_text and time.monotonic() < deadline:
        application.processEvents()
        time.sleep(0.01)
    window.cancel_reply()
    wait_reply(window, application)
    message = window.store.messages(window.chat_id)[-1]
    assert message["metadata"]["status"] == "cancelled"
    assert window.stop_reply.isEnabled()
