"""Selected-crop research analysis and explanations from the same second model."""

import json
import threading
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

from qma_face.core.config import PROJECT_ROOT
from qma_face.services.geometry import GROUPS, measurements, photo_palette, validate_points
from qma_face.services.photo_quality import inspect_photo, photo_digest


class AnalysisCancelled(RuntimeError):
    pass


def check_cancel(cancel):
    if cancel is not None and cancel.is_set():
        raise AnalysisCancelled()


def score_to_100(raw: float) -> float:
    if not np.isfinite(raw) or not 1 <= raw <= 5:
        raise ValueError("The model did not return a finite rating on the declared scale")
    return round((raw - 1) * 25, 2)


def region_mask(image, points, group):
    if group not in GROUPS:
        raise ValueError("Unsupported facial group")
    pixels = validate_points(points) * np.asarray(image.size)
    mask = Image.new("L", image.size)
    draw = ImageDraw.Draw(mask)
    if group == "outline":
        contour = [tuple(pixels[n - 1]) for n in GROUPS[group]]
        draw.line(contour + contour[:1], fill=255, width=max(3, round(min(image.size) * 0.035)))
    else:
        regions = {
            "eyes": [(43, 50), (51, 58)],
            "brows": [(23, 32), (33, 42)],
            "nose": [(61, 73)],
            "mouth": [(74, 86)],
        }[group]
        padding = min(image.size) * 0.025
        for start, end in regions:
            subset = pixels[start - 1 : end]
            low, high = subset.min(axis=0) - padding, subset.max(axis=0) + padding
            draw.rectangle((float(low[0]), float(low[1]), float(high[0]), float(high[1])), fill=255)
    return mask


class AnalysisService:
    def __init__(self, root: Path = PROJECT_ROOT):
        self.root = root
        self.candidate = None
        self._lock = threading.Lock()

    def load(self):
        if self.candidate is None:
            compact = self.root / "models/weights/qma-face-engine-research-v1.onnx"
            if compact.is_file():
                from qma_face.services.onnx_engine import CompactCandidate

                self.candidate = CompactCandidate(
                    compact,
                    self.root / "models/engine-evaluation.json",
                    self.root / "models/engine-export.json",
                )
                return
            # CPU keeps the small second engine independent of Qwen's GPU memory allocation.
            import torch

            from qma_face.research.inference import ResearchCandidate

            torch.set_num_threads(4)
            self.candidate = ResearchCandidate(
                self.root / "models/weights/qma-face-engine-research-v1.pt",
                self.root / "models/engine-evaluation.json",
                device="cpu",
            )

    def locate(self, image, *, confirmed: bool, cancel=None) -> dict:
        if not confirmed:
            raise ValueError("A single frontal, visible face must be selected and confirmed")
        quality = inspect_photo(image)
        if quality["status"] == "retake":
            raise ValueError("The selected crop failed the photo checks")
        check_cancel(cancel)
        with self._lock:
            self.load()
            result = self.candidate.predict(image, cropped_face_confirmed=True)
        check_cancel(cancel)
        return result

    def explain(self, image, points, visible, *, original=None, cancel=None) -> dict:
        validate_points(points)
        check_cancel(cancel)
        with self._lock:
            self.load()
            baseline = self.candidate.predict(image, cropped_face_confirmed=True)
            raw = baseline["raw_overall_1_to_5"]
            if raw is None:
                raise ValueError("The candidate has no trained overall-score head")
            comparisons = []
            exposure_trials = []
            all_visible = all(visible.values())
            if all_visible:
                blurred = image.filter(ImageFilter.GaussianBlur(max(5, min(image.size) * 0.07)))
                for group in GROUPS:
                    check_cancel(cancel)
                    changed = Image.composite(blurred, image, region_mask(image, points, group))
                    prediction = self.candidate.predict(changed, cropped_face_confirmed=True)
                    perturbed = prediction["raw_overall_1_to_5"]
                    comparisons.append(
                        {
                            "region": group,
                            "delta_score_100_after_blur": round((perturbed - raw) * 25, 3),
                            "blurred_raw_1_to_5": perturbed,
                        }
                    )
                check_cancel(cancel)
                attention = self._gradcam(image)
                for factor in (0.9, 1.1):
                    check_cancel(cancel)
                    trial = ImageEnhance.Brightness(image).enhance(factor)
                    trial_raw = self.candidate.predict(trial, cropped_face_confirmed=True)[
                        "raw_overall_1_to_5"
                    ]
                    exposure_trials.append(
                        {
                            "brightness_factor": factor,
                            "score_100": score_to_100(trial_raw),
                            "delta_100": round((trial_raw - raw) * 25, 3),
                        }
                    )
            else:
                attention = None
            before = None
            if original is not None and all_visible:
                before = self.candidate.predict(original, cropped_face_confirmed=True)[
                    "raw_overall_1_to_5"
                ]
        check_cancel(cancel)
        return {
            "raw_score_1_to_5": raw if all_visible else None,
            "score_0_to_100": score_to_100(raw) if all_visible else None,
            "scale_mapping": "(raw_1_to_5 - 1) * 25",
            "distance_to_scale_ceiling": round(100 - score_to_100(raw), 2) if all_visible else None,
            "score_status": "experimental_model_estimate" if all_visible else "withheld_occlusion",
            "component_scores": None,
            "confidence": None,
            "regions": comparisons,
            "exposure_stability": {
                "kind": "controlled_exposure_stress_not_confidence",
                "trials": exposure_trials,
                "largest_abs_change": max(
                    (abs(t["delta_100"]) for t in exposure_trials), default=None
                ),
                "unstable_heuristic": any(abs(t["delta_100"]) > 5 for t in exposure_trials),
                "heuristic_threshold": 5,
            },
            "gradcam": attention,
            "original_raw_1_to_5": before,
            "adjustment_delta_100": round((raw - before) * 25, 3) if before is not None else None,
            "explanation_kind": "local_model_sensitivity_not_causal_or_additive_deductions",
            "evaluation": {
                "dataset": "SCUT-FBP5500",
                "test_images": self.candidate.report["test"]["images"],
                "test_mae_1_to_5": self.candidate.report["test"]["overall_mae_1_to_5"],
                "identity_split_verified": False,
                "production_validated": False,
            },
            "checkpoint_sha256": self.candidate.report["checkpoint_sha256"],
            "geometry": measurements(points, image.size, visible),
            "palette": photo_palette(image),
            "limitations": [
                "Overall score models the training raters preferences, not objective beauty.",
                "No trained component beauty scores or exact point deductions exist.",
                "Blurring can create out-of-distribution inputs; effects overlap and do not sum.",
                "Grad-CAM is coarse positive sensitivity, not proof of causation.",
                "Occlusion, pose, age, identity, personality and health are not detected.",
            ],
        }

    def _gradcam(self, image):
        if hasattr(self.candidate, "gradcam"):
            return self.candidate.gradcam(image)
        import torch
        from torchvision.transforms import functional as transforms

        model = self.candidate.model
        tensor = transforms.to_tensor(image.convert("RGB").resize((224, 224)))
        tensor = transforms.normalize(tensor, [0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
        activations = []
        handle = model.backbone.layer4.register_forward_hook(
            lambda module, args, out: activations.append(out)
        )
        try:
            with torch.enable_grad():
                prediction = model(tensor.unsqueeze(0).to(self.candidate.device))["overall"][0]
                gradient = torch.autograd.grad(prediction, activations[0])[0]
                weights = gradient.mean(dim=(2, 3), keepdim=True)
                cam = (weights * activations[0]).sum(dim=1)[0].relu().detach().cpu().numpy()
            peak = float(cam.max())
            if not np.isfinite(cam).all() or peak < 1e-10:
                return {"status": "no_positive_signal", "values": None}
            return {
                "status": "available",
                "values": (cam / peak).round(5).tolist(),
                "layer": "shared_backbone.layer4",
                "scope": "positive_model_sensitivity",
            }
        finally:
            handle.remove()


def compact_analysis(report: dict) -> dict:
    """Bounded evidence for chat; no photo or 86-point biometric array in the LLM context."""
    return {
        "status": "research_preview",
        "photo_sha256": report["source_photo_sha256"],
        "score_0_to_100": report["score_0_to_100"],
        "raw_score_1_to_5": report["raw_score_1_to_5"],
        "score_status": report["score_status"],
        "scale_mapping": report["scale_mapping"],
        "component_scores": None,
        "confidence": None,
        "metrics": report["geometry"]["metrics"],
        "landmark_review_flags": report["geometry"].get("review_flags", []),
        "points_manually_reviewed": report.get("points_manually_reviewed"),
        "blur_sensitivity": report["regions"],
        "explanation_kind": report["explanation_kind"],
        "adjustment_delta_100": report.get("adjustment_delta_100"),
        "exposure_stability": report.get("exposure_stability"),
        "limitations": report["limitations"],
        "checkpoint_sha256": report["checkpoint_sha256"],
    }


def active_analysis(messages, current_photo_sha256):
    for message in reversed(messages):
        report = message.get("metadata", {}).get("analysis")
        if report and report.get("source_photo_sha256") == current_photo_sha256:
            return compact_analysis(report)
    return None


def finish_report(
    result, *, source, crop_box, source_photo_sha256, edited_points, preparation, points
):
    result = dict(result)
    stored_points = validate_points(points).round(6).tolist()
    for group, numbers in GROUPS.items():
        if not result["geometry"]["visibility"][group]:
            for number in numbers:
                stored_points[number - 1] = None
    result.update(
        schema_version=1,
        status="research_preview",
        source_photo_sha256=source_photo_sha256,
        working_photo_sha256=photo_digest(source),
        crop_box=list(crop_box),
        landmarks=stored_points,
        landmarks_source="user_reviewed_and_edited"
        if edited_points
        else "model_points_user_reviewed",
        preparation=preparation,
    )
    # Refuse NaN or non-JSON objects before evidence reaches storage.
    json.dumps(result, allow_nan=False)
    return result
