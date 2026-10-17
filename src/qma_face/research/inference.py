import hashlib
import json
import time
from pathlib import Path

from qma_face.research.engine import FaceEngine


class ResearchCandidate:
    """Explicit selected-face research use; never promotes a checkpoint to production."""

    def __init__(self, checkpoint: Path, report: Path, device: str | None = None):
        import torch

        self.report = json.loads(report.read_text(encoding="utf-8"))
        if hashlib.sha256(checkpoint.read_bytes()).hexdigest() != self.report["checkpoint_sha256"]:
            raise ValueError("Candidate checksum does not match its evaluation report")
        data = torch.load(checkpoint, map_location="cpu", weights_only=True)
        if data.get("architecture") != "qma-resnet18-multitask-v1":
            raise ValueError("Unsupported research architecture")
        self.trained_heads = set(data["trained_heads"])
        if not self.trained_heads <= {"overall", "landmarks", "region", "visibility", "components"}:
            raise ValueError("Unsupported head names")
        self.model = FaceEngine(data["landmark_count"])
        missing = self.model.load_state_dict(data["state_dict"], strict=False)
        expected = {
            f"{head}.{parameter}"
            for head in ("overall", "landmarks", "region", "visibility", "components")
            if head not in self.trained_heads
            for parameter in ("weight", "bias")
        }
        if set(missing.missing_keys) != expected or missing.unexpected_keys:
            raise ValueError("Checkpoint contains missing or unexpected trained parameters")
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        if self.device not in {"cuda", "cpu"}:
            raise ValueError("Unsupported research device")
        self.model.eval().to(self.device)

    def predict(self, image, *, cropped_face_confirmed: bool = False) -> dict:
        import torch
        from torchvision.transforms import functional as transforms

        if not cropped_face_confirmed:
            raise ValueError("This candidate has no validated full-photo face detector")
        tensor = transforms.to_tensor(image.convert("RGB").resize((224, 224)))
        tensor = transforms.normalize(tensor, [0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
        if self.device == "cuda":
            torch.cuda.synchronize()
        started = time.perf_counter()
        with torch.inference_mode():
            output = self.model(tensor.unsqueeze(0).to(self.device))
        if self.device == "cuda":
            torch.cuda.synchronize()
        return {
            "status": "research_candidate_not_production_validated",
            "model": "qma-resnet18-multitask-v1",
            "device": self.device,
            "selected_face_crop_only": True,
            "coordinates": "normalized_in_selected_crop",
            "raw_overall_1_to_5": float(output["overall"][0])
            if "overall" in self.trained_heads
            else None,
            "landmarks": output["landmarks"][0].cpu().tolist()
            if "landmarks" in self.trained_heads
            else None,
            "component_scores": None,
            "visibility": None,
            "face_detection": None,
            "confidence": None,
            "production_ready": False,
            "forward_ms": round((time.perf_counter() - started) * 1000, 3),
            "license": "non-commercial_research_only_redistribution_not_cleared",
        }
