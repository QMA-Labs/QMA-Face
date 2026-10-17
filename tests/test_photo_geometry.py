import copy

import numpy as np
import pytest
from PIL import Image, ImageFilter

from qma_face.services.analysis import active_analysis, score_to_100
from qma_face.services.geometry import GROUPS, measurements, photo_palette
from qma_face.services.local_ai import bounded_messages
from qma_face.services.photo_quality import inspect_photo, photo_digest, prepare_photo


def patterned_photo(size=256):
    y, x = np.indices((size, size))
    gray = (60 + ((x // 9 + y // 9) % 2) * 120).astype(np.uint8)
    return Image.fromarray(np.repeat(gray[..., None], 3, axis=2))


def synthetic_points():
    points = np.full((86, 2), 0.5)
    # Deliberately synthetic positions for mathematical invariance checks, not a face dataset.
    for number, point in {
        1: (0.5, 0.1),
        12: (0.5, 0.9),
        6: (0.15, 0.4),
        18: (0.85, 0.4),
        59: (0.35, 0.4),
        60: (0.65, 0.4),
        65: (0.4, 0.6),
        69: (0.6, 0.6),
        74: (0.7, 0.75),
        80: (0.3, 0.75),
        43: (0.4, 0.4),
        47: (0.2, 0.4),
        45: (0.3, 0.37),
        49: (0.3, 0.43),
        51: (0.8, 0.4),
        55: (0.6, 0.4),
        53: (0.7, 0.37),
        57: (0.7, 0.43),
        27: (0.2, 0.3),
        33: (0.8, 0.3),
        77: (0.5, 0.72),
        83: (0.5, 0.78),
        9: (0.25, 0.7),
        15: (0.75, 0.7),
    }.items():
        points[number - 1] = point
    return points


def test_blur_darkness_clipping_and_true_resolution_checks():
    photo = patterned_photo()
    assert inspect_photo(photo)["status"] == "usable"
    assert inspect_photo(photo.filter(ImageFilter.GaussianBlur(12)))["status"] == "retake"
    assert "too_small" in inspect_photo(photo.resize((80, 80)))["blocking"]
    assert inspect_photo(Image.new("RGB", (256, 256), "black"))["status"] == "retake"
    assert inspect_photo(Image.new("RGB", (256, 256), "white"))["status"] == "retake"
    checks = inspect_photo(photo)
    assert checks["automatic_face_count"] is None and checks["quality_percentage"] is None


def test_classical_adjustment_preserves_source_and_records_actual_work():
    photo = patterned_photo().point([round(v * 0.25) for v in range(256)] * 3)
    digest = photo_digest(photo)
    corrected, report = prepare_photo(photo)
    assert photo_digest(photo) == digest
    assert corrected.size == photo.size
    assert report["operations"] == [{"operation": "gamma", "gamma": 0.8}]
    assert report["after"]["mean_luma_0_to_255"] > report["before"]["mean_luma_0_to_255"]
    assert report["generated_detail"] is False and report["geometric_warp"] is False
    assert report["original_sha256"] != report["prepared_sha256"]


def test_unchanged_exposure_has_no_fictional_correction():
    photo = patterned_photo()
    corrected, report = prepare_photo(photo)
    assert report["operations"] == []
    assert photo_digest(photo) == photo_digest(corrected)


def test_geometry_ratios_are_scale_invariant_and_not_beauty_scores():
    visible = dict.fromkeys(GROUPS, True)
    first = measurements(synthetic_points(), (300, 400), visible)
    second = measurements(synthetic_points(), (600, 800), visible)
    assert first["metrics"] == second["metrics"]
    assert first["beauty_component_scores"] is None
    ratio = next(m["value"] for m in first["metrics"] if m["name"] == "nose_to_mouth_width")
    assert ratio == 0.5


def test_unknown_parts_never_get_dependent_measurements():
    visible = dict.fromkeys(GROUPS, True)
    visible["nose"] = False
    report = measurements(synthetic_points(), (300, 400), visible)
    assert next(m["value"] for m in report["metrics"] if m["name"] == "nose_to_mouth_width") is None
    assert (
        next(m["value"] for m in report["metrics"] if m["name"] == "paired_image_asymmetry") is None
    )
    assert (
        next(m["value"] for m in report["metrics"] if m["name"] == "mouth_width_to_face_width")
        is not None
    )
    with pytest.raises(ValueError):
        measurements(np.zeros((68, 2)), (300, 400), visible)
    with pytest.raises(ValueError):
        measurements(np.full((86, 2), float("nan")), (300, 400), visible)


@pytest.mark.parametrize("raw, expected", [(1, 0), (3, 50), (5, 100)])
def test_score_mapping_is_explicit_arithmetic(raw, expected):
    assert score_to_100(raw) == expected
    for invalid in [-1, 6, float("nan")]:
        with pytest.raises(ValueError):
            score_to_100(invalid)


def test_palette_is_marked_as_photo_color_not_skin_or_ethnicity():
    report = photo_palette(patterned_photo())
    assert report["calibrated_skin_color"] is False
    assert report["lighting_dependent"] is True
    assert abs(sum(c["pixel_fraction"] for c in report["colors"]) - 1) < 0.001


def test_stale_and_unconfirmed_analysis_cannot_enter_model_context():
    messages = [
        {
            "role": "assistant",
            "content": "old report",
            "metadata": {"analysis": {"source_photo_sha256": "old"}},
        },
        {
            "role": "assistant",
            "content": "old score explanation",
            "metadata": {"analysis_photo_sha256": "old"},
        },
        {"role": "user", "content": "Why this score?", "metadata": {"_photo_sha256": "new"}},
    ]
    assert active_analysis(messages, "new") is None
    context = bounded_messages(messages, "en", b"photo")
    assert not any(
        "old score" in str(m["content"]) or m["content"] == "old report" for m in context
    )
    assert not any(str(m["content"]).startswith("RESEARCH_ANALYSIS_JSON\n") for m in context)
    messages[-1]["metadata"]["_active_analysis"] = {
        "status": "research_preview",
        "photo_sha256": "old",
        "score_0_to_100": 60,
    }
    context = bounded_messages(messages, "en", b"photo")
    assert not any(str(m["content"]).startswith("RESEARCH_ANALYSIS_JSON\n") for m in context)
    matching = copy.deepcopy(messages)
    matching[-1]["metadata"]["_active_analysis"]["photo_sha256"] = "new"
    context = bounded_messages(matching, "fr", b"photo")
    assert any(str(m["content"]).startswith("RESEARCH_ANALYSIS_JSON\n") for m in context)
    assert context[-1]["content"][0]["text"] == "Why this score?"
