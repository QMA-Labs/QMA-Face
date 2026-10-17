"""Build-time conversion of the existing trained checkpoint, with parity verification."""

import argparse
import hashlib
import json
import statistics
import time
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from torch import nn

from qma_face.core.config import PROJECT_ROOT
from qma_face.research.inference import ResearchCandidate
from qma_face.services.analysis import AnalysisService
from qma_face.services.onnx_engine import CompactCandidate


class ExportFace(nn.Module):
    def __init__(self, model):
        super().__init__()
        self.model = model

    def forward(self, image):
        backbone = self.model.backbone
        x = backbone.maxpool(backbone.relu(backbone.bn1(backbone.conv1(image))))
        x = backbone.layer4(backbone.layer3(backbone.layer2(backbone.layer1(x))))
        features = backbone.avgpool(x).flatten(1)
        overall = 1 + 4 * torch.sigmoid(self.model.overall(features)).squeeze(-1)
        points = torch.sigmoid(self.model.landmarks(features)).reshape(-1, 86, 2)
        cam = (x * self.model.overall.weight.reshape(1, 512, 1, 1)).sum(1).relu()
        return overall, points, cam


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--manifest", type=Path, required=True, help="Local evaluated dataset manifest"
    )
    args = parser.parse_args()
    torch.set_num_threads(4)
    root = PROJECT_ROOT
    weight = root / "models/weights/qma-face-engine-research-v1.pt"
    candidate = ResearchCandidate(weight, root / "models/engine-evaluation.json", "cpu")
    target = weight.with_suffix(".onnx")
    torch.onnx.export(
        ExportFace(candidate.model).eval(),
        torch.zeros(1, 3, 224, 224),
        target,
        input_names=["image"],
        output_names=["overall", "landmarks", "cam"],
        opset_version=18,
        dynamo=False,
        external_data=False,
    )
    export = {
        "schema_version": 1,
        "onnx_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
        "source_checkpoint_sha256": candidate.report["checkpoint_sha256"],
        "architecture": "qma-resnet18-multitask-v1",
        "trained_heads": ["overall", "landmarks"],
        "cam": "analytic_equivalent_of_normalized_positive_GradCAM_for_GAP_linear_sigmoid",
        "runtime": "onnxruntime-cpu",
        "production_validated": False,
        "redistribution": "not_cleared",
        "model_count": 1,
    }
    export_path = root / "models/engine-export.json"
    export_path.write_text(json.dumps(export, indent=2), encoding="utf-8")
    compact = CompactCandidate(target, root / "models/engine-evaluation.json", export_path)
    manifest = json.loads(args.manifest.read_text())
    records = [r for r in manifest["records"] if r["split"] == "test"]
    old_ms, new_ms, scores, points, cams = [], [], [], [], []
    service = AnalysisService()
    service.candidate = candidate
    for index, row in enumerate(records):
        with Image.open(row["image"]) as image:
            photo = image.convert("RGB")
        start = time.perf_counter()
        old = candidate.predict(photo, cropped_face_confirmed=True)
        old_ms.append((time.perf_counter() - start) * 1000)
        start = time.perf_counter()
        new = compact.predict(photo, cropped_face_confirmed=True)
        new_ms.append((time.perf_counter() - start) * 1000)
        scores.append(abs(old["raw_overall_1_to_5"] - new["raw_overall_1_to_5"]))
        points.append(float(np.abs(np.array(old["landmarks"]) - new["landmarks"]).max()))
        if index < 12:
            old_cam, new_cam = service._gradcam(photo), compact.gradcam(photo)
            if old_cam["values"] is not None:
                cams.append(float(np.abs(np.array(old_cam["values"]) - new_cam["values"]).max()))
    assert records, "The parity manifest needs test records"
    assert max(scores) < 1e-4 and max(points) < 1e-5 and max(cams) < 1e-4
    export["parity"] = {
        "heldout_images": len(records),
        "raw_score_max_abs_error": max(scores),
        "normalized_point_max_abs_error": max(points),
        "gradcam_images": len(cams),
        "gradcam_max_abs_error": max(cams),
        "torch_median_ms": statistics.median(old_ms[2:]),
        "onnx_median_ms": statistics.median(new_ms[2:]),
        "note": "FP32 conversion parity, not new scientific accuracy validation",
    }
    export_path.write_text(json.dumps(export, indent=2), encoding="utf-8")
    print(json.dumps(export, indent=2))


if __name__ == "__main__":
    main()
