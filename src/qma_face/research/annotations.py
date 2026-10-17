"""Import reviewed human labels. Missing scores stay missing; no automatic pseudo-labels."""

import json
import math
from pathlib import Path

from qma_face.research.engine import COMPONENTS


def read_annotations(path: Path) -> dict[str, dict]:
    result = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        if item.get("schema_version") != 1 or item.get("human_reviewed") is not True:
            raise ValueError("Human-reviewed schema version 1 is required")
        if not item.get("subject_id") or not item.get("consent_reference"):
            raise ValueError(
                "Reviewed subject grouping and documented training consent are required"
            )
        digest = item.get("image_sha256", "")
        if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise ValueError("Image SHA256 must match the reviewed photo")
        if digest in result:
            raise ValueError("Duplicate photo annotation")
        scores, variation = [], []
        for component in COMPONENTS:
            ratings = item.get("component_ratings", {}).get(component, [])
            if not ratings:
                scores.append(None)
                variation.append(None)
                continue
            raters = [rating["rater_id"] for rating in ratings]
            if len(set(raters)) < 3 or len(set(raters)) != len(raters):
                raise ValueError(
                    "Each labeled component needs at least three distinct human raters"
                )
            if any(isinstance(rating["score_1_to_5"], bool) for rating in ratings):
                raise ValueError("Boolean flags are not human appearance ratings")
            values = [float(rating["score_1_to_5"]) for rating in ratings]
            if not all(math.isfinite(v) and 1 <= v <= 5 for v in values):
                raise ValueError("Human ratings must be finite and on the declared 1-5 scale")
            mean = sum(values) / len(values)
            scores.append(mean)
            variation.append(
                {
                    "raters": len(values),
                    "sample_sd": (sum((v - mean) ** 2 for v in values) / (len(values) - 1)) ** 0.5,
                }
            )
        unknown = set(item.get("component_ratings", {})) - set(COMPONENTS)
        if unknown:
            raise ValueError("Unknown or character-related component labels are not accepted")
        visibility = item.get("landmark_visibility")
        if visibility is not None and (
            len(visibility) != 86 or any(v is not None and type(v) is not bool for v in visibility)
        ):
            raise ValueError("Visibility must contain 86 reviewed boolean or unknown labels")
        region = item.get("face_region_xyxy_normalized")
        if region is not None:
            if (
                len(region) != 4
                or not all(
                    type(v) in (float, int) and math.isfinite(v) and 0 <= v <= 1 for v in region
                )
                or not (region[0] < region[2] and region[1] < region[3])
            ):
                raise ValueError("Invalid reviewed normalized face rectangle")
        result[digest] = {
            "subject_id": item["subject_id"],
            "consent_reference": item["consent_reference"],
            "components": scores,
            "component_rater_variation": variation,
            "visibility": visibility,
            "region": region,
        }
    return result


def attach_annotations(manifest: dict, annotations: dict) -> dict:
    from qma_face.research.data import split_by_group

    records = manifest["records"]
    known = {record["sha256"] for record in records}
    if set(annotations) - known:
        raise ValueError("Annotation photo hashes are not present in the dataset")
    for record in records:
        if record["sha256"] in annotations:
            record.update(annotations[record["sha256"]])
    split_by_group(records)
    manifest["identity_split_verified"] = all(r.get("subject_id") for r in records)
    manifest["counts"] = {
        name: sum(r["split"] == name for r in records) for name in ("train", "validation", "test")
    }
    manifest["reviewed_annotation_photos"] = len(annotations)
    return manifest
