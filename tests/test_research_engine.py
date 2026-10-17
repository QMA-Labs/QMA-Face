import struct

import numpy as np
import pytest
import torch

from qma_face.research.data import read_scut_points, split_by_group
from qma_face.research.engine import FaceEngine, masked_loss


def test_binary_scut_landmarks_and_malformed_inputs(tmp_path):
    path = tmp_path / "face.pts"
    points = np.arange(172, dtype=np.float32).reshape(86, 2)
    path.write_bytes(struct.pack("<I", 86) + points.astype("<f4").tobytes())
    np.testing.assert_array_equal(read_scut_points(path), points)
    path.write_bytes(path.read_bytes()[:-4])
    with pytest.raises(ValueError):
        read_scut_points(path)


def test_same_identity_and_duplicate_chains_never_cross_splits():
    records = [
        {"sha256": "a", "subject_id": "person1"},
        {"sha256": "b", "subject_id": "person1"},
        {"sha256": "b", "subject_id": "person2"},
        {"sha256": "c", "subject_id": "person2"},
        {"sha256": "d", "subject_id": None},
    ]
    split_by_group(records)
    assert len({r["split"] for r in records[:4]}) == 1
    assert len({r["group_id"] for r in records[:4]}) == 1


def test_missing_component_and_visibility_labels_never_train_those_heads():
    torch.set_num_threads(2)
    model = FaceEngine()
    output = model(torch.zeros(2, 3, 64, 64))
    targets = {
        "overall": (torch.tensor([2.0, 3.0]), torch.tensor([True, True])),
        "landmarks": (torch.full((2, 86, 2), 0.4), torch.ones(2, 86, 2, dtype=torch.bool)),
    }
    loss, tasks = masked_loss(output, targets)
    loss.backward()
    assert set(tasks) == {"overall", "landmarks"}
    assert model.overall.weight.grad is not None
    assert model.landmarks.weight.grad is not None
    for head in (model.region, model.components, model.visibility):
        assert head.weight.grad is None
    assert output["landmarks"].shape == (2, 86, 2)
    assert (output["region"][:, :2] <= output["region"][:, 2:]).all()


def test_unlabeled_batches_fail_and_masked_values_have_no_gradient():
    prediction = torch.tensor([2.0, 3.0], requires_grad=True)
    loss, _ = masked_loss(
        {"overall": prediction},
        {"overall": (torch.tensor([4.0, 999.0]), torch.tensor([True, False]))},
    )
    loss.backward()
    assert prediction.grad[1] == 0
    with pytest.raises(ValueError, match="No genuine"):
        masked_loss({"overall": prediction}, {})
