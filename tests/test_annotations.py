import json

import pytest

from qma_face.research.annotations import read_annotations


def specimen():
    return {
        "schema_version": 1,
        "human_reviewed": True,
        "subject_id": "consenting-subject-1",
        "consent_reference": "local-consent-record-1",
        "image_sha256": "a" * 64,
        "component_ratings": {
            "eyes": [
                {"rater_id": "r1", "score_1_to_5": 2},
                {"rater_id": "r2", "score_1_to_5": 3},
                {"rater_id": "r3", "score_1_to_5": 4},
            ]
        },
    }


def test_human_labels_preserve_missing_components_and_rater_variation(tmp_path):
    path = tmp_path / "annotations.jsonl"
    path.write_text(json.dumps(specimen()))
    item = read_annotations(path)["a" * 64]
    assert item["components"] == [3.0, None, None, None, None, None]
    assert item["component_rater_variation"][0] == {"raters": 3, "sample_sd": 1.0}
    assert item["visibility"] is None


@pytest.mark.parametrize("issue", ["consent", "raters", "character", "invalid_score"])
def test_unreviewed_or_inappropriate_annotation_is_rejected(tmp_path, issue):
    item = specimen()
    if issue == "consent":
        item["consent_reference"] = ""
    elif issue == "raters":
        item["component_ratings"]["eyes"][1]["rater_id"] = "r1"
    elif issue == "character":
        item["component_ratings"]["honesty"] = []
    else:
        item["component_ratings"]["eyes"][0]["score_1_to_5"] = float("nan")
    path = tmp_path / "annotations.jsonl"
    path.write_text(json.dumps(item))
    with pytest.raises(ValueError):
        read_annotations(path)
