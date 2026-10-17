"""Refine the existing landmark head; frozen backbone/rating, validation-only selection."""

import argparse
import hashlib
import json
import math
import random
import time
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import DataLoader

from qma_face.research.data import FaceDataset
from qma_face.research.engine import FaceEngine


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--initialize", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    torch.manual_seed(146)
    np.random.seed(146)
    random.seed(146)
    torch.set_num_threads(4)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    manifest = json.loads(args.manifest.read_text())
    checkpoint = torch.load(args.initialize, map_location="cpu", weights_only=True)
    model = FaceEngine().to(device)
    missing = model.load_state_dict(checkpoint["state_dict"], strict=False)
    assert not missing.unexpected_keys
    assert all(
        k.split(".")[0] in {"region", "visibility", "components"} for k in missing.missing_keys
    )
    model.eval()
    for parameter in model.parameters():
        parameter.requires_grad_(False)
    model.landmarks.requires_grad_(True)
    started = time.monotonic()

    def features(split, views):
        dataset = FaceDataset(manifest, split, augment=split == "train", cache_images=True)
        result = [[], [], []]
        with torch.no_grad():
            for _ in range(views):
                for image, target in DataLoader(dataset, batch_size=64, num_workers=0):
                    values, mask = target["landmarks"]
                    result[0].append(model.backbone(image.to(device)).detach())
                    result[1].append(values.to(device))
                    result[2].append(mask.to(device))
        return tuple(torch.cat(items) for items in result)

    train = features("train", 6)
    validation = features("validation", 1)
    print(json.dumps({"feature_views": len(train[0]), "backbone_frozen": True}), flush=True)

    def evaluate(data):
        inputs, expected, mask = data
        with torch.no_grad():
            predicted = model.landmarks(inputs).sigmoid().reshape(-1, 86, 2)
            distance = (predicted - expected).square().sum(-1).sqrt() / math.sqrt(2)
            included = mask.all(-1)
            rows = (distance * included).sum(-1) / included.sum(-1).clamp_min(1)
            eyes = included[:, 42:60]
            eye_rows = (distance[:, 42:60] * eyes).sum(-1) / eyes.sum(-1).clamp_min(1)
            return {
                "landmark_mean_normalized_diagonal_error": float(rows[included.any(-1)].mean()),
                "eye_mean_normalized_diagonal_error": float(eye_rows[eyes.any(-1)].mean()),
            }

    baseline = evaluate(validation)
    best = (
        baseline["landmark_mean_normalized_diagonal_error"]
        + baseline["eye_mean_normalized_diagonal_error"]
    )
    best_state = {k: v.detach().cpu().clone() for k, v in model.landmarks.state_dict().items()}
    best_epoch = 0
    optimizer = torch.optim.AdamW(model.landmarks.parameters(), lr=0.0001, weight_decay=0.0001)
    history = []
    x, y, mask = train
    for epoch in range(1, 81):
        permutation = torch.randperm(len(x), device=device)
        for indices in permutation.split(256):
            output = model.landmarks(x[indices]).sigmoid().reshape(-1, 86, 2)
            squared = (output - y[indices]).square()
            included = mask[indices]
            weights = torch.ones_like(squared)
            weights[:, 42:60] = 2
            loss = (squared * weights)[included].mean()
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            optimizer.step()
        metric = evaluate(validation)
        combined = sum(metric.values())
        # Both the overall landmark mean and eye-region error must improve.
        if (
            combined < best
            and metric["landmark_mean_normalized_diagonal_error"]
            < baseline["landmark_mean_normalized_diagonal_error"]
            and metric["eye_mean_normalized_diagonal_error"]
            < baseline["eye_mean_normalized_diagonal_error"]
        ):
            best, best_epoch = combined, epoch
            best_state = {
                k: v.detach().cpu().clone() for k, v in model.landmarks.state_dict().items()
            }
        history.append({"epoch": epoch, "validation": metric})
        if epoch % 10 == 0:
            print(json.dumps(history[-1]), flush=True)
        if epoch - best_epoch >= 20:
            break
    model.landmarks.load_state_dict(best_state)
    candidate = dict(checkpoint)
    candidate["state_dict"] = dict(checkpoint["state_dict"])
    for key, value in best_state.items():
        candidate["state_dict"]["landmarks." + key] = value
    args.output.mkdir(parents=True, exist_ok=True)
    path = args.output / "candidate-research-only.pt"
    torch.save(candidate, path)
    unchanged = all(
        torch.equal(value, candidate["state_dict"][key])
        for key, value in checkpoint["state_dict"].items()
        if not key.startswith("landmarks.")
    )
    assert unchanged
    report = {
        "baseline_validation": baseline,
        "candidate_validation": evaluate(validation),
        "selected_epoch": best_epoch,
        "completed_epochs": len(history),
        "history": history,
        "validation_gate_passed": best_epoch > 0,
        "backbone_and_rating_bitwise_unchanged": unchanged,
        "test_used_for_selection": False,
        "new_real_images": 0,
        "training_views": len(x),
        "unique_train_images": sum(r["split"] == "train" for r in manifest["records"]),
        "views_are_2d_augmentation": True,
        "seconds": time.monotonic() - started,
        "checkpoint_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "blind_external_validation": False,
        "production_validated": False,
    }
    (args.output / "refinement-report.json").write_text(json.dumps(report, indent=2))
    print(json.dumps({k: v for k, v in report.items() if k != "history"}), flush=True)


if __name__ == "__main__":
    main()
