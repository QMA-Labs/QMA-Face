import json
import sys
from pathlib import Path

import pytest

from qma_face.core.config import data_directory
from qma_face.services.analysis_answers import analysis_answer
from qma_face.services.library import evidence_context
from qma_face.services.onnx_engine import CompactCandidate


def test_frozen_data_is_separate_from_installation(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.delenv("QMA_FACE_DATA_DIR", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "user-profile"))
    assert data_directory() == tmp_path / "user-profile/QMA/Face/Data"
    monkeypatch.setenv("QMA_FACE_DATA_DIR", str(tmp_path / "explicit"))
    assert data_directory() == tmp_path / "explicit"


def test_compact_runtime_rejects_corruption_and_wrong_provenance(tmp_path):
    evaluation = tmp_path / "evaluation.json"
    exported = tmp_path / "export.json"
    model = tmp_path / "model.onnx"
    model.write_bytes(b"corrupted-model")
    evaluation.write_text(json.dumps({"checkpoint_sha256": "original"}))
    exported.write_text(
        json.dumps({"source_checkpoint_sha256": "original", "onnx_sha256": "wrong"})
    )
    with pytest.raises(ValueError, match="checksum"):
        CompactCandidate(model, evaluation, exported)
    exported.write_text(json.dumps({"source_checkpoint_sha256": "other"}))
    with pytest.raises(ValueError, match="provenance"):
        CompactCandidate(model, evaluation, exported)


def test_simple_score_reply_keeps_exposure_warning():
    messages = [
        {
            "role": "user",
            "content": "Why not 100?",
            "metadata": {
                "_photo_sha256": "photo",
                "_answer_style": "casual",
                "_active_analysis": {
                    "status": "research_preview",
                    "photo_sha256": "photo",
                    "score_0_to_100": 60,
                    "blur_sensitivity": [],
                    "metrics": [],
                    "exposure_stability": {
                        "trials": [{"delta_100": 8}],
                        "largest_abs_change": 8,
                        "unstable_heuristic": True,
                    },
                },
            },
        }
    ]
    answer = analysis_answer(messages, "en", True)
    assert "8.00" in answer["text"] and "stable personal trait" in answer["text"]
    assert "not confidence" in answer["text"]


def test_source_context_includes_limitations_and_fulltext_status():
    result = evidence_context(
        [
            {
                "citation_id": "S1",
                "text": "Curated summary",
                "limitations": "Frontal only",
                "method_and_sample": "5,500 faces",
                "full_text_indexed": False,
            }
        ]
    )
    data = json.loads(result.split("\n", 1)[1])[0]
    assert data["limitations"] == "Frontal only" and data["full_text_indexed"] is False


def test_installer_keeps_data_and_has_no_network_download_actions():
    script = (Path(__file__).parents[1] / "tools/windows-installer.iss").read_text(encoding="utf-8")
    assert "PrivilegesRequired=lowest" in script and "[UninstallDelete]" not in script
    assert "DownloadTemporaryFile" not in script and "sources" not in script.lower()
