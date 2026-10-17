"""Classical photo checks; thresholds are heuristics, never accuracy percentages."""

import hashlib

import numpy as np
from PIL import Image, ImageFilter


def photo_digest(image: Image.Image) -> str:
    image = image.convert("RGB")
    digest = hashlib.sha256()
    digest.update(f"{image.width}x{image.height}:RGB:".encode())
    digest.update(image.tobytes())
    return digest.hexdigest()


def inspect_photo(image: Image.Image) -> dict:
    image = image.convert("RGB")
    sample = image.copy()
    sample.thumbnail((512, 512))
    gray = np.asarray(sample.convert("L"), dtype=np.float32)
    # The user selects the face. Evaluate the central area to reduce background clipping bias;
    # this remains a heuristic, not an automatic face segmentation or detector.
    if min(gray.shape) >= 20:
        y, x = round(gray.shape[0] * 0.15), round(gray.shape[1] * 0.15)
        gray = gray[y : gray.shape[0] - y, x : gray.shape[1] - x]
    mean, spread = float(gray.mean()), float(gray.std())
    clipped_dark, clipped_light = float((gray <= 5).mean()), float((gray >= 250).mean())
    laplacian = (
        -4 * gray[1:-1, 1:-1] + gray[:-2, 1:-1] + gray[2:, 1:-1] + gray[1:-1, :-2] + gray[1:-1, 2:]
    )
    sharpness = float(laplacian.var()) if laplacian.size else 0.0
    noise = (
        float(np.median(np.abs(laplacian - np.median(laplacian))) / (0.6745 * np.sqrt(20)))
        if laplacian.size
        else 0.0
    )
    blocking, warnings = [], []
    if min(image.size) < 96:
        blocking.append("too_small")
    elif min(image.size) < 224:
        warnings.append("limited_resolution")
    if spread < 5:
        blocking.append("no_detail")
    elif sharpness < 8:
        blocking.append("blurred")
    if clipped_dark > 0.45 or clipped_light > 0.45:
        blocking.append("clipped")
    if mean < 60:
        warnings.append("dark")
    if mean > 205:
        warnings.append("bright")
    status = "retake" if blocking else "adjustable" if mean < 60 or mean > 205 else "usable"
    return {
        "status": status,
        "blocking": blocking,
        "warnings": warnings,
        "width": image.width,
        "height": image.height,
        "mean_luma_0_to_255": round(mean, 3),
        "luma_std": round(spread, 3),
        "laplacian_variance": round(sharpness, 3),
        "estimated_noise_sigma": round(noise, 3),
        "dark_clip_fraction": round(clipped_dark, 4),
        "light_clip_fraction": round(clipped_light, 4),
        "method": "classical_heuristics_v1_not_calibrated_face_acceptance",
        "area": "central_70_percent_of_manually_selected_crop",
        "automatic_face_count": None,
        "pose": None,
        "occlusion": None,
        "quality_percentage": None,
    }


def prepare_photo(image: Image.Image, *, lighting: bool = True, denoise: bool = False):
    original = image.convert("RGB")
    result = original.copy()
    operations = []
    before = inspect_photo(result)
    if lighting and before["mean_luma_0_to_255"] < 75:
        gamma = 0.8
    elif lighting and before["mean_luma_0_to_255"] > 195:
        gamma = 1.2
    else:
        gamma = 1.0
    if gamma != 1:
        table = [round(255 * (value / 255) ** gamma) for value in range(256)]
        result = result.point(table * 3)
        operations.append({"operation": "gamma", "gamma": gamma})
    if denoise:
        result = result.filter(ImageFilter.MedianFilter(3))
        operations.append({"operation": "median_filter", "kernel": 3})
    return result, {
        "operations": operations,
        "before": before,
        "after": inspect_photo(result),
        "original_sha256": photo_digest(original),
        "prepared_sha256": photo_digest(result),
        "geometric_warp": False,
        "generated_detail": False,
    }


def auto_prepare_photo(image: Image.Image):
    """Try reversible classical corrections, retaining the original for comparison."""
    original = image.convert("RGB")
    result, report = prepare_photo(original)
    # Robust high-pass estimate can also respond to texture. Never label it a calibrated
    # detection probability. Reject a noise-filter candidate that loses too much contrast
    # or introduces a blocking quality condition.
    noise = report["before"]["estimated_noise_sigma"]
    if noise > 12 and report["after"]["status"] != "retake":
        candidate, trial = prepare_photo(original, denoise=True)
        if (
            trial["after"]["status"] != "retake"
            and trial["after"]["luma_std"] >= report["after"]["luma_std"] * 0.85
        ):
            result, report = candidate, trial
    report["automatic_preparation"] = True
    report["noise_selection"] = "robust_highpass_heuristic_not_calibrated"
    return result, report
