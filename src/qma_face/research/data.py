import hashlib
import json
import struct
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from torch.utils.data import Dataset
from torchvision.transforms import functional as transforms


def read_scut_points(path: Path) -> np.ndarray:
    content = path.read_bytes()
    if len(content) < 4:
        raise ValueError("Truncated landmark header")
    count = struct.unpack("<I", content[:4])[0]
    if count == 0 and len(content) == 4:
        return np.empty((0, 2), dtype=np.float32)
    if count != 86 or len(content) != 4 + count * 8:
        raise ValueError("Unexpected SCUT binary landmark format")
    points = np.frombuffer(content[4:], dtype="<f4").copy().reshape(count, 2)
    if not np.isfinite(points).all():
        raise ValueError("Non-finite landmark coordinates")
    return points


def split_by_group(records: list[dict], seed: str = "qma-phase5-v1") -> list[dict]:
    """Known identity and exact duplicates cannot cross splits; unknown identities stay flagged."""
    parent = list(range(len(records)))

    def find(index):
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    seen = {}
    for index, item in enumerate(records):
        keys = [("hash", item["sha256"])]
        if item.get("subject_id"):
            keys.append(("subject", item["subject_id"]))
        for key in keys:
            if key in seen:
                parent[find(index)] = find(seen[key])
            else:
                seen[key] = index
    groups = {}
    for index, item in enumerate(records):
        groups.setdefault(find(index), []).append(item)
    for items in groups.values():
        group = min(item["sha256"] for item in items)
        bucket = int(hashlib.sha256((seed + group).encode()).hexdigest()[:8], 16) % 100
        split = "train" if bucket < 80 else "validation" if bucket < 90 else "test"
        for item in items:
            item.update(split=split, group_id=group)
    return records


def audit_scut(root: Path, identity_map: dict | None = None) -> dict:
    root = root.resolve()
    identities = identity_map or {}
    labels = root / "train_test_files/All_labels.txt"
    records = []
    for line in labels.read_text().splitlines():
        name, raw = line.split()
        name = Path(name).name
        image_path = root / "Images" / name
        points_path = root / "facial landmark" / (Path(name).stem + ".pts")
        if not image_path.resolve().is_relative_to(root):
            raise ValueError("Image path outside dataset")
        score = float(raw)
        if not np.isfinite(score) or not 1 <= score <= 5:
            raise ValueError("Invalid overall rating")
        with Image.open(image_path) as image:
            width, height = image.size
            image.verify()
        points = read_scut_points(points_path)
        normalized = points / np.array([width, height])
        in_bounds = ((normalized >= 0) & (normalized <= 1)).all(axis=1)
        records.append(
            {
                "image": str(image_path),
                "points": str(points_path),
                "width": width,
                "height": height,
                "overall": score,
                "sha256": hashlib.sha256(image_path.read_bytes()).hexdigest(),
                "subject_id": identities.get(name),
                "group": Path(name).stem[:2],
                "out_of_bounds_points": int((~in_bounds).sum()),
                "landmark_labels_present": len(points) == 86,
            }
        )
    split_by_group(records)
    counts = {
        name: sum(r["split"] == name for r in records) for name in ("train", "validation", "test")
    }
    hashes = [r["sha256"] for r in records]
    return {
        "schema_version": 1,
        "dataset": "SCUT-FBP5500_v2.1",
        "license": "non-commercial_research_only",
        "records": records,
        "counts": counts,
        "images": len(records),
        "exact_duplicate_images": len(hashes) - len(set(hashes)),
        "images_missing_landmark_annotations": sum(
            not r["landmark_labels_present"] for r in records
        ),
        "identity_split_verified": all(r.get("subject_id") for r in records),
        "genuine_labels": ["overall", "landmarks"],
        "missing_labels": [
            "face_detection_region",
            "no_face_examples",
            "visibility",
            *["component_" + c for c in ("eyes", "eyebrows", "nose", "lips", "jaw", "harmony")],
        ],
        "limitations": [
            "Hash grouping prevents exact duplicate leakage; different images of one person "
            "still need reviewed identities.",
            "Identity map has not been reviewed unless identity_split_verified is true.",
            "Frontal, unoccluded faces; source README includes ages 15-60.",
            "Internet collection does not establish consent or unrestricted redistribution.",
            "Overall labels cannot train component scores or visibility confidence.",
        ],
    }


class FaceDataset(Dataset):
    def __init__(self, manifest: dict, split: str, augment: bool = False, cache_images=False):
        self.records = [r for r in manifest["records"] if r["split"] == split]
        self.augment = augment and split == "train"
        self.photos = []
        if cache_images:
            for record in self.records:
                with Image.open(record["image"]) as photo:
                    self.photos.append(photo.convert("RGB").resize((224, 224)))

    def __len__(self):
        return len(self.records)

    def __getitem__(self, index):
        record = self.records[index]
        if self.photos:
            photo = self.photos[index].copy()
        else:
            with Image.open(record["image"]) as image:
                photo = image.convert("RGB").resize((224, 224))
        points = read_scut_points(Path(record["points"]))
        if len(points):
            points /= np.array([record["width"], record["height"]], dtype=np.float32)
            mask = ((points >= 0) & (points <= 1)).all(axis=1)
        else:
            # Zero is a batching placeholder, never an annotation or an observed point.
            points = np.zeros((86, 2), dtype=np.float32)
            mask = np.zeros(86, dtype=bool)
        if self.augment:
            photo, points, included = augment_photo_points(photo, points)
            mask &= included
        tensor = transforms.to_tensor(photo)
        tensor = transforms.normalize(tensor, [0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
        targets = {
            "overall": (torch.tensor(record["overall"], dtype=torch.float32), torch.tensor(True)),
            "landmarks": (
                torch.from_numpy(points),
                torch.from_numpy(np.repeat(mask[:, None], 2, axis=1)),
            ),
        }
        for name, length in (("components", 6), ("visibility", 86), ("region", 4)):
            values = record.get(name)
            # Every batch has identical shapes, but only genuinely reviewed entries have a mask.
            if values is None:
                values = [None] * length
            mask = torch.tensor([v is not None for v in values], dtype=torch.bool)
            targets[name] = (
                torch.tensor([float(v) if v is not None else 0.0 for v in values]),
                mask,
            )
        return tensor, targets


def augment_photo_points(photo, points, matrix=None):
    """One explicit forward affine for both image and labels; no invented 3D pose."""
    import math
    import random

    from PIL import ImageEnhance

    if matrix is None:
        angle = math.radians(random.uniform(-12, 12))
        scale = random.uniform(0.92, 1.08)
        linear = scale * np.array(
            [[math.cos(angle), -math.sin(angle)], [math.sin(angle), math.cos(angle)]]
        )
        offset = np.array([0.5, 0.5]) - linear @ [0.5, 0.5]
        offset += np.array([random.uniform(-0.035, 0.035), random.uniform(-0.035, 0.035)])
        matrix = np.eye(3)
        matrix[:2, :2], matrix[:2, 2] = linear, offset
    matrix = np.asarray(matrix, dtype=np.float64)
    if matrix.shape != (3, 3) or not np.isfinite(matrix).all():
        raise ValueError("Expected a finite 3x3 affine")
    forward_pixels = np.diag([photo.width, photo.height, 1]) @ matrix
    forward_pixels = forward_pixels @ np.diag([1 / photo.width, 1 / photo.height, 1])
    a, b, tx = forward_pixels[0]
    c, d, ty = forward_pixels[1]
    determinant = a * d - b * c
    if abs(determinant) < 1e-10:
        raise ValueError("Singular affine")
    inverse = np.array([[d, -b, b * ty - d * tx], [-c, a, c * tx - a * ty]]) / determinant
    transformed = photo.transform(
        photo.size,
        Image.Transform.AFFINE,
        tuple(inverse[:2].ravel()),
        Image.Resampling.BILINEAR,
        fillcolor=(127, 127, 127),
    )
    transformed = ImageEnhance.Brightness(transformed).enhance(random.uniform(0.85, 1.15))
    transformed = ImageEnhance.Contrast(transformed).enhance(random.uniform(0.9, 1.1))
    labels = (points @ matrix[:2, :2].T + matrix[:2, 2]).astype(np.float32)
    included = ((labels >= 0) & (labels <= 1)).all(axis=1)
    return transformed, labels, included


def save_manifest(manifest: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
