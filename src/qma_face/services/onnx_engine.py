"""Same trained face engine in a compact CPU runtime; no extra model or detector."""

import hashlib
import json
import time
from pathlib import Path

import numpy as np


class CompactCandidate:
    def __init__(self, model_path: Path, evaluation_path: Path, export_path: Path):
        import onnxruntime as ort

        self.report = json.loads(evaluation_path.read_text(encoding="utf-8"))
        self.export = json.loads(export_path.read_text(encoding="utf-8"))
        if self.export["source_checkpoint_sha256"] != self.report["checkpoint_sha256"]:
            raise ValueError("Export provenance does not match the evaluated engine")
        if hashlib.sha256(model_path.read_bytes()).hexdigest() != self.export["onnx_sha256"]:
            raise ValueError("Face-engine checksum mismatch")
        options = ort.SessionOptions()
        options.intra_op_num_threads = 4
        options.inter_op_num_threads = 1
        options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        self.session = ort.InferenceSession(
            str(model_path), sess_options=options, providers=["CPUExecutionProvider"]
        )
        self.device = "cpu"

    def outputs(self, image):
        array = np.asarray(image.convert("RGB").resize((224, 224)), dtype=np.float32) / 255
        array = (array - np.array([0.485, 0.456, 0.406], dtype=np.float32)) / np.array(
            [0.229, 0.224, 0.225], dtype=np.float32
        )
        tensor = np.ascontiguousarray(array.transpose(2, 0, 1)[None])
        return self.session.run(None, {"image": tensor})

    def predict(self, image, *, cropped_face_confirmed=False):
        if not cropped_face_confirmed:
            raise ValueError("A selected face must be confirmed")
        started = time.perf_counter()
        score, points, _ = self.outputs(image)
        if not np.isfinite(score).all() or not np.isfinite(points).all():
            raise ValueError("Non-finite model output")
        return {
            "status": "research_candidate_not_production_validated",
            "model": "qma-resnet18-multitask-v1",
            "device": "cpu",
            "selected_face_crop_only": True,
            "coordinates": "normalized_in_selected_crop",
            "raw_overall_1_to_5": float(score[0]),
            "landmarks": points[0].tolist(),
            "component_scores": None,
            "visibility": None,
            "face_detection": None,
            "confidence": None,
            "production_ready": False,
            "forward_ms": round((time.perf_counter() - started) * 1000, 3),
            "license": "non-commercial_research_only_redistribution_not_cleared",
        }

    def gradcam(self, image):
        # For global-average-pool → linear → sigmoid, the positive scalar derivative
        # cancels under max normalization. The exported CAM is analytically equivalent.
        cam = self.outputs(image)[2][0]
        peak = float(cam.max())
        if not np.isfinite(cam).all() or peak < 1e-10:
            return {"status": "no_positive_signal", "values": None}
        return {
            "status": "available",
            "values": (cam / peak).round(5).tolist(),
            "layer": "shared_backbone.layer4",
            "scope": "positive_model_sensitivity",
        }
