import json

import pytest

from qma_face.core.contracts import (
    AnalysisResult,
    BeautyScore,
    Citation,
    EvidenceKind,
    FeatureResult,
    Visibility,
)
from qma_face.core.registry import load_model_manifest, validate_release_manifest


def test_an_invisible_feature_cannot_be_reconstructed_as_observation():
    with pytest.raises(ValueError, match="invisible"):
        FeatureResult("left_eye", EvidenceKind.MEASUREMENT, 12.0, visibility=Visibility.NOT_VISIBLE)


def test_unknown_feature_can_be_explicitly_missing():
    result = FeatureResult("left_eye", EvidenceKind.MEASUREMENT, visibility=Visibility.NOT_VISIBLE)
    assert result.value is None


def test_a_source_claim_requires_traceable_source():
    with pytest.raises(ValueError, match="citation"):
        FeatureResult("source_interpretation", EvidenceKind.SOURCE_CLAIM, "claim")
    result = FeatureResult(
        "source_interpretation",
        EvidenceKind.SOURCE_CLAIM,
        "claim",
        citations=(Citation("personal-notes", page=4),),
    )
    assert result.citations[0].page == 4


def test_confidence_cannot_be_a_model_self_assessment():
    with pytest.raises(ValueError, match="calibration"):
        FeatureResult("ratio", EvidenceKind.MEASUREMENT, 0.7, confidence=0.95)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -1, 101])
def test_invalid_scores_never_reach_the_ui(value):
    with pytest.raises(ValueError):
        BeautyScore("overall", value, "engine-1", "reference", "evaluation-1")


def test_unavailable_analysis_cannot_expose_scores():
    with pytest.raises(ValueError, match="invented"):
        AnalysisResult(
            "analysis-1",
            "image-1",
            scores=(BeautyScore("overall", 80, "engine-1", "reference", "evaluation-1"),),
        )


def test_unvalidated_candidate_models_cannot_be_released():
    manifest = load_model_manifest()
    assert len(manifest["models"]) == 2
    with pytest.raises(ValueError, match="tested"):
        validate_release_manifest(manifest)


def test_cleared_license_does_not_replace_weight_integrity():
    manifest = json.loads(json.dumps(load_model_manifest()))
    for entry in manifest["models"]:
        entry.update(status="validated", redistribution="cleared", evaluation_id="eval-1")
        entry["artifacts"] = [{"name": "weights", "sha256": None}]
    with pytest.raises(ValueError, match="checksum"):
        validate_release_manifest(manifest)
