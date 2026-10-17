import json
from pathlib import Path

from qma_face.core.config import settings


def load_model_manifest(path: Path | None = None) -> dict:
    path = path or settings.project_root / "models" / "manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    entries = manifest["models"]
    if len(entries) != settings.maximum_models:
        raise ValueError("The product must declare exactly two model roles.")
    if {entry["role"] for entry in entries} != {"vision_chat", "face_engine"}:
        raise ValueError("Unexpected or duplicate model role.")
    return manifest


def validate_release_manifest(manifest: dict) -> None:
    entries = manifest.get("models", [])
    if len(entries) != settings.maximum_models:
        raise ValueError("Release requires exactly two model roles.")
    if {entry.get("role") for entry in entries} != {"vision_chat", "face_engine"}:
        raise ValueError("Release model roles are incomplete.")
    for entry in entries:
        if entry.get("status") != "validated" or not entry.get("evaluation_id"):
            raise ValueError("Release requires tested model artifacts.")
        if entry.get("redistribution") != "cleared":
            raise ValueError("Redistribution has not been cleared.")
        artifacts = entry.get("artifacts", [])
        if not artifacts or any(not artifact.get("sha256") for artifact in artifacts):
            raise ValueError("Every release artifact needs a checksum.")
