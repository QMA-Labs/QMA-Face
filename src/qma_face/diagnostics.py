"""Explicit offline acceptance probe for frozen installer validation."""

import hashlib
import io
import json
import os
import sys
import threading
import time
from pathlib import Path

from PIL import Image

from qma_face import __version__
from qma_face.core.config import PROJECT_ROOT, data_directory
from qma_face.services.analysis import AnalysisService
from qma_face.services.geometry import GROUPS
from qma_face.services.library import SourceLibrary
from qma_face.services.local_ai import LocalAI


def run_diagnostics(output: Path, photo_path: Path | None, run_chat: bool, language: str):
    started = time.perf_counter()
    result = {
        "version": __version__,
        "frozen": bool(getattr(sys, "frozen", False)),
        "root": str(PROJECT_ROOT),
        "data_root": str(data_directory()),
        "torch_imported": False,
        "checks": {},
    }
    backend = None
    try:
        manifest = json.loads((PROJECT_ROOT / "models/manifest.json").read_text(encoding="utf-8"))
        assert len(manifest["models"]) == 2
        for model in manifest["models"]:
            for artifact in model["artifacts"]:
                path = PROJECT_ROOT / "models/weights" / artifact["name"]
                with path.open("rb") as stream:
                    digest = hashlib.file_digest(stream, "sha256").hexdigest()
                assert digest == artifact["sha256"], artifact["name"]
        result["checks"]["model_checksums"] = True
        if photo_path:
            with Image.open(photo_path) as image:
                photo = image.convert("RGB")
        else:
            import numpy as np

            y, x = np.indices((256, 256))
            array = (50 + ((x // 8 + y // 8) % 2) * 140).astype("uint8")
            photo = Image.fromarray(np.repeat(array[..., None], 3, axis=2))
        service = AnalysisService()
        located = service.locate(photo, confirmed=True)
        report = service.explain(photo, located["landmarks"], dict.fromkeys(GROUPS, True))
        result["checks"]["face_engine"] = {
            "backend": type(service.candidate).__name__,
            "score": report["score_0_to_100"],
            "landmarks": len(located["landmarks"]),
            "regions": len(report["regions"]),
            "gradcam": report["gradcam"]["status"],
            "exposure_stability": report["exposure_stability"],
        }
        library = SourceLibrary(PROJECT_ROOT, data_directory() / "diagnostic-library.sqlite")
        library.synchronize()
        result["checks"]["sources"] = {
            "article": bool(library.search("SCUT-FBP5500", source_id="scut-fbp5500")),
            "personal_body_pdf": bool(
                library.search("context rules", source_id="personal-body-language")
            ),
            "personal_face_pdf": bool(
                library.search("large nose", source_id="personal-physiognomy")
            ),
        }
        assert all(result["checks"]["sources"].values())
        # Exercise the actual Qt DLLs, platform plugin and native home/chat screens.
        result["ui_checkpoint"] = "before_qt_import"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2), encoding="utf-8")
        from PySide6.QtWidgets import QApplication

        from qma_face.core.storage import ChatStore
        from qma_face.ui.fonts import configure_fonts
        from qma_face.ui.window import FaceWindow

        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        application = QApplication.instance() or QApplication([])
        configure_fonts(application)
        ui = FaceWindow(store=ChatStore(data_directory(), memory=True), resume=False)
        ui.show()
        application.processEvents()
        ui.grab().save(str(output.with_suffix(".png")))
        ui.begin_new_chat()
        ui.start_conversation()
        application.processEvents()
        ui.close()
        result["checks"]["native_home_chat"] = True
        result["ui_checkpoint"] = "complete"
        if run_chat:
            backend = LocalAI(log_root=data_directory())
            image_bytes = io.BytesIO()
            photo.save(image_bytes, format="JPEG")
            messages = [
                {
                    "role": "user",
                    "content": "Describe the visible photo in one short sentence. "
                    "Do not guess identity or personality.",
                }
            ]
            answer = backend.generate(
                messages, language, image_bytes.getvalue(), threading.Event(), lambda piece: None
            )
            result["checks"]["chat"] = {
                "device": answer["device"],
                "text": answer["text"],
                "seconds": answer["duration_s"],
            }
            backend.stop()
            result["checks"]["owned_server_stopped"] = backend.process is None
        result["torch_imported"] = "torch" in sys.modules
        result["checks"]["no_training_runtime_loaded"] = "torch" not in sys.modules
        result["device_preference"] = os.environ.get("QMA_FACE_DEVICE", "auto")
        result["passed"] = True
        status = 0
    except Exception as error:
        result["passed"] = False
        result["error"] = f"{type(error).__name__}: {error}"
        status = 1
    finally:
        if backend:
            backend.stop()
        result["elapsed_seconds"] = round(time.perf_counter() - started, 3)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return status
