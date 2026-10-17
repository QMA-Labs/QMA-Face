import argparse
import os
import sys
import tempfile
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="QMA Face desktop foundation")
    parser.add_argument("--preview-dir", type=Path, help="Render native screens without analysis.")
    parser.add_argument("--language", choices=("en", "fr"))
    parser.add_argument("--diagnostics", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--test-photo", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--test-chat", action="store_true", help=argparse.SUPPRESS)
    arguments = parser.parse_args()
    if arguments.diagnostics:
        from qma_face.diagnostics import run_diagnostics

        return run_diagnostics(
            arguments.diagnostics,
            arguments.test_photo,
            arguments.test_chat,
            arguments.language or "en",
        )
    if arguments.preview_dir:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtWidgets import QApplication

    from qma_face.core.registry import load_model_manifest
    from qma_face.core.storage import ChatStore
    from qma_face.ui.fonts import configure_fonts
    from qma_face.ui.window import FaceWindow

    load_model_manifest()
    application = QApplication.instance() or QApplication(sys.argv[:1])
    application.setApplicationName("QMA Face")
    application.setOrganizationName("QMA")
    application.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
    configure_fonts(application)
    preview_data = None
    store = None
    if arguments.preview_dir:
        arguments.preview_dir.mkdir(parents=True, exist_ok=True)
        preview_data = tempfile.TemporaryDirectory(prefix="qma-preview-", dir=arguments.preview_dir)
        store = ChatStore(Path(preview_data.name))
    window = FaceWindow(store=store, resume=not bool(arguments.preview_dir))
    if arguments.language:
        window.language_picker.setCurrentIndex(0 if arguments.language == "en" else 1)
    window.show()

    if arguments.preview_dir:
        arguments.preview_dir.mkdir(parents=True, exist_ok=True)

        def capture() -> None:
            for language in ("en", "fr"):
                window.language_picker.setCurrentIndex(0 if language == "en" else 1)
                for name in ("home", "upload", "chats"):
                    window.show_screen(name)
                    application.processEvents()
                    target = arguments.preview_dir / f"qma-face-{name}-{language}.png"
                    if not window.grab().save(str(target)):
                        raise RuntimeError(f"Could not save preview: {target}")
                window.start_conversation()
                application.processEvents()
                window.grab().save(str(arguments.preview_dir / f"qma-face-chat-{language}.png"))
            window.resize(800, 620)
            window.show_screen("home")
            application.processEvents()
            window.grab().save(str(arguments.preview_dir / "qma-face-home-compact-fr.png"))
            application.quit()

        QTimer.singleShot(120, capture)
    result = application.exec()
    window.close()
    if preview_data:
        preview_data.cleanup()
    return result
