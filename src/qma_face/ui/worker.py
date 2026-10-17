import copy
import re
import threading

from PySide6.QtCore import QThread, Signal

from qma_face.services.local_ai import GenerationCancelled, ModelUnavailable


class ReplyWorker(QThread):
    piece = Signal(str)
    state = Signal(str)
    complete = Signal(dict)
    failed = Signal(str)

    def __init__(self, backend, messages, language, image, parent=None):
        super().__init__(parent)
        self.backend = backend
        self.messages = messages
        self.language = language
        self.image = image
        self.cancel_event = threading.Event()

    def run(self):
        try:
            messages = copy.deepcopy(self.messages)
            previous_user = None
            for message in messages:
                if message["role"] == "user":
                    previous_user = message
                elif previous_user is not None:
                    cached = message.get("metadata", {}).get("input_translation", {})
                    if cached.get("target_language") == "English" and cached.get("text"):
                        previous_user["content"] = cached["text"]
            translated_input = None
            latest = next((m for m in reversed(messages) if m["role"] == "user"), None)
            if (
                latest
                and latest.get("metadata", {}).get("_translate_persian_input")
                and re.search(r"[\u0600-\u06ff]", latest["content"])
            ):
                self.state.emit("translating_input")
                translated = self.backend.translate(
                    latest["content"],
                    "English",
                    self.cancel_event,
                    lambda piece: None,
                    lambda state: None,
                )
                if translated.get("truncated") or not translated.get("text", "").strip():
                    raise RuntimeError("Input translation is incomplete; nothing sent")
                if self.cancel_event.is_set():
                    raise GenerationCancelled()
                translated_input = translated["text"]
                latest_copy = next(m for m in reversed(messages) if m["role"] == "user")
                latest_copy["content"] = translated_input
            result = self.backend.generate(
                messages,
                self.language,
                self.image,
                self.cancel_event,
                self.piece.emit,
                self.state.emit,
            )
            if translated_input:
                result["input_translation"] = {
                    "source_language": "Persian",
                    "target_language": "English",
                    "text": translated_input,
                    "machine_translation": True,
                }
            self.complete.emit(result)
        except GenerationCancelled:
            self.failed.emit("cancelled")
        except ModelUnavailable:
            self.failed.emit("unavailable")
        except Exception:
            self.failed.emit("cancelled" if self.cancel_event.is_set() else "request_failed")

    def cancel(self):
        self.cancel_event.set()
        self.backend.cancel_generation()
