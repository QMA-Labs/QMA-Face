"""Reproducible local research run, not automatic production model promotion."""

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

from qma_face.research.annotations import attach_annotations, read_annotations
from qma_face.research.data import FaceDataset, audit_scut, read_scut_points, save_manifest
from qma_face.research.engine import FaceEngine, masked_loss


def evaluate(model, loader, device):
    model.eval()
    predictions, actual, errors = [], [], []
    auxiliary = {name: [] for name in ("components", "region", "visibility")}
    with torch.inference_mode():
        for images, targets in loader:
            output = model(images.to(device))
            predictions.extend(output["overall"].cpu().tolist())
            actual.extend(targets["overall"][0].tolist())
            points, mask = targets["landmarks"]
            distance = (output["landmarks"].cpu() - points).square().sum(dim=-1).sqrt()
            valid = mask.all(dim=-1)
            for row, included in zip(distance, valid, strict=True):
                if included.any():
                    errors.append(float(row[included].mean() / math.sqrt(2)))
            for name in auxiliary:
                if name not in targets:
                    continue
                values, mask = targets[name]
                if mask.any():
                    prediction = (
                        output["visibility_logits"].sigmoid().cpu()
                        if name == "visibility"
                        else output[name].cpu()
                    )
                    if name == "visibility":
                        auxiliary[name].extend(
                            ((prediction[mask] >= 0.5) == values[mask].bool()).float().tolist()
                        )
                    else:
                        auxiliary[name].extend((prediction[mask] - values[mask]).abs().tolist())
    predictions, actual = np.asarray(predictions), np.asarray(actual)
    residuals = np.abs(predictions - actual)
    metrics = {
        "images": len(actual),
        "overall_mae_1_to_5": float(residuals.mean()),
        "overall_rmse_1_to_5": float(np.sqrt(((predictions - actual) ** 2).mean())),
        "overall_pearson": float(np.corrcoef(predictions, actual)[0, 1])
        if predictions.std() > 1e-8 and actual.std() > 1e-8
        else None,
        "landmark_mean_error_normalized_image_diagonal": float(np.mean(errors)),
        "landmark_metric_definition": (
            "Euclidean distance after independent x/width,y/height normalization, "
            "divided by sqrt(2); in-bounds annotated points only. Not interocular NME."
        ),
    }
    metrics["auxiliary_heads"] = {
        name: {
            "labeled_values": len(values),
            "metric": "accuracy" if name == "visibility" else "mae",
            "value": float(np.mean(values)) if values else None,
        }
        for name, values in auxiliary.items()
    }
    return metrics, residuals, predictions, actual


def train(args):
    torch.manual_seed(45)
    np.random.seed(45)
    random.seed(45)
    torch.set_num_threads(8)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    manifest = audit_scut(args.dataset)
    if args.annotations is not None:
        manifest = attach_annotations(manifest, read_annotations(args.annotations))
    save_manifest(manifest, output / "dataset-manifest.local.json")
    datasets = {
        split: FaceDataset(manifest, split, augment=args.augment, cache_images=args.cache_images)
        for split in manifest["counts"]
    }
    if min(len(ds) for ds in datasets.values()) < 2:
        raise ValueError("Train, validation and test splits must all be populated")
    loaders = {
        split: DataLoader(
            ds,
            batch_size=args.batch_size,
            shuffle=split == "train",
            num_workers=args.workers,
            persistent_workers=args.workers > 0,
            pin_memory=device == "cuda",
        )
        for split, ds in datasets.items()
    }
    model = FaceEngine().to(device)
    if args.initialize:
        checkpoint = torch.load(args.initialize, map_location=device, weights_only=True)
        if checkpoint.get("architecture") != "qma-resnet18-multitask-v1":
            raise ValueError("Unsupported initialization")
        incompatible = model.load_state_dict(checkpoint["state_dict"], strict=False)
        if incompatible.unexpected_keys or any(
            k.split(".")[0] not in {"region", "visibility", "components"}
            for k in incompatible.missing_keys
        ):
            raise ValueError("Incomplete trained backbone/heads")
    # No externally trained initialization: unknown original checkpoint split cannot leak here.
    trained_heads = ["overall", "landmarks"]
    for name in ("region", "visibility", "components"):
        has_labels = any(
            r.get(name) and any(v is not None for v in r[name]) for r in datasets["train"].records
        )
        getattr(model, name).requires_grad_(has_labels)
        if has_labels:
            trained_heads.append(name)
    optimizer = torch.optim.AdamW(
        (p for p in model.parameters() if p.requires_grad),
        lr=args.learning_rate,
        weight_decay=0.0001,
    )
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=args.epochs)
    scaler = torch.amp.GradScaler("cuda", enabled=device == "cuda")
    started = time.monotonic()
    history, best, best_epoch = [], float("inf"), 0
    candidate = output / "candidate-research-only.pt"
    for epoch in range(1, args.epochs + 1):
        model.train()
        accumulated, batches = 0, 0
        for images, target in loaders["train"]:
            images = images.to(device)
            target = {k: (v.to(device), m.to(device)) for k, (v, m) in target.items()}
            optimizer.zero_grad(set_to_none=True)
            with torch.autocast(device_type=device, enabled=device == "cuda"):
                loss, _ = masked_loss(model(images), target)
            if not torch.isfinite(loss):
                raise ValueError("Non-finite training loss; run aborted")
            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()
            accumulated += float(loss.detach())
            batches += 1
        validation, _, _, _ = evaluate(model, loaders["validation"], device)
        scheduler.step()
        combined = (
            validation["overall_mae_1_to_5"]
            + 10 * validation["landmark_mean_error_normalized_image_diagonal"]
        )
        history.append(
            {"epoch": epoch, "training_loss": accumulated / batches, "validation": validation}
        )
        if combined < best:
            best, best_epoch = combined, epoch
            state = {
                k: v.cpu()
                for k, v in model.state_dict().items()
                if k.split(".")[0] in {"backbone", *trained_heads}
            }
            torch.save(
                {
                    "state_dict": state,
                    "architecture": "qma-resnet18-multitask-v1",
                    "trained_heads": trained_heads,
                    "landmark_count": 86,
                    "status": "research_only_not_validated",
                    "dataset": manifest["dataset"],
                    "license": manifest["license"],
                    "epoch": epoch,
                },
                candidate,
            )
        print(json.dumps(history[-1]), flush=True)
        if args.patience and epoch - best_epoch >= args.patience:
            break
        if args.max_minutes and time.monotonic() - started >= args.max_minutes * 60:
            break
    checkpoint = torch.load(candidate, map_location=device, weights_only=True)
    incompatible = model.load_state_dict(checkpoint["state_dict"], strict=False)
    expected_missing = {
        f"{name}.{param}"
        for name in ("region", "visibility", "components")
        if name not in trained_heads
        for param in ("weight", "bias")
    }
    if set(incompatible.missing_keys) != expected_missing or incompatible.unexpected_keys:
        raise ValueError("Unexpected checkpoint layout")
    validation, residuals, _, _ = evaluate(model, loaders["validation"], device)
    test, test_residuals, _, actual = evaluate(model, loaders["test"], device)
    n = len(residuals)
    quantile = sorted(residuals)[min(n - 1, math.ceil((n + 1) * 0.9) - 1)]
    training_mean = float(np.mean([r["overall"] for r in datasets["train"].records]))
    mean_score_baseline = float(np.mean(np.abs(actual - training_mean)))
    train_points = np.stack(
        [
            read_scut_points(Path(r["points"])) / [r["width"], r["height"]]
            for r in datasets["train"].records
            if r["landmark_labels_present"]
        ]
    )
    average_shape = train_points.mean(axis=0)
    shape_errors = []
    for _, targets in loaders["test"]:
        points, mask = targets["landmarks"]
        distances = np.linalg.norm(points.numpy() - average_shape, axis=-1) / math.sqrt(2)
        for row, included in zip(distances, mask.all(dim=-1).numpy(), strict=True):
            if included.any():
                shape_errors.append(float(row[included].mean()))
    report = {
        "status": "research_candidate_trained_not_production_validated",
        "device": device,
        "epochs": len(history),
        "maximum_requested_epochs": args.epochs,
        "early_stopping_patience": args.patience,
        "selected_epoch": best_epoch,
        "seconds": round(time.monotonic() - started, 2),
        "parameters": sum(p.numel() for p in model.parameters()),
        "maximum_cuda_allocated_mib": round(torch.cuda.max_memory_allocated() / 2**20, 2)
        if device == "cuda"
        else None,
        "dataset": {k: v for k, v in manifest.items() if k != "records"},
        "initialization": str(args.initialize) if args.initialize else "random_seed_45",
        "augmentation": args.augment,
        "new_real_images": 0,
        "augmentation_is_not_3d_pose_supervision": True,
        "test_used_for_selection": False,
        "history": history,
        "validation": validation,
        "test": test,
        "mean_score_baseline_test_mae": mean_score_baseline,
        "mean_shape_baseline_test_normalized_diagonal_error": float(np.mean(shape_errors)),
        "interval_experiment": {
            "nominal_coverage": 0.9,
            "validation_absolute_residual_radius": float(quantile),
            "test_empirical_coverage": float(np.mean(test_residuals <= quantile)),
            "use": "research_split_conformal_only_exchangeability_and_identity_not_verified",
        },
        "checkpoint_sha256": hashlib.sha256(candidate.read_bytes()).hexdigest(),
        "trained_heads": trained_heads,
        "unsupported_heads_exported": False,
        "production_gate": {
            "identity_separation": manifest["identity_split_verified"],
            "component_labels": False,
            "visibility_labels": False,
            "detection_labels_and_negatives": False,
            "redistribution_cleared": False,
            "robustness_and_population_evaluation": False,
        },
        "deployed": False,
    }
    (output / "training-report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "final": report["test"],
                "seconds": report["seconds"],
                "baseline_mae": mean_score_baseline,
            }
        ),
        flush=True,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--epochs", type=int, default=6)
    parser.add_argument("--annotations", type=Path)
    parser.add_argument("--batch-size", type=int, default=24)
    parser.add_argument("--initialize", type=Path)
    parser.add_argument("--augment", action="store_true")
    parser.add_argument("--learning-rate", type=float, default=0.0003)
    parser.add_argument("--workers", type=int, default=0)
    parser.add_argument("--cache-images", action="store_true")
    parser.add_argument("--patience", type=int, default=0)
    parser.add_argument("--max-minutes", type=float, default=0)
    args = parser.parse_args()
    if not 1 <= args.epochs <= 200 or not 2 <= args.batch_size <= 128:
        raise ValueError("Unsupported training configuration")
    if not 0 <= args.workers <= 4 or not 0 < args.learning_rate <= 0.01:
        raise ValueError("Unsupported worker count or learning rate")
    train(args)


if __name__ == "__main__":
    main()
