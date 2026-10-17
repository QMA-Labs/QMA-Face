import torch
from torch import nn
from torchvision.models import resnet18

COMPONENTS = ("eyes", "eyebrows", "nose", "lips", "jaw", "harmony")


class FaceEngine(nn.Module):
    """One shared backbone, one checkpoint; absent supervision does not train a head."""

    def __init__(self, landmark_count: int = 86):
        super().__init__()
        self.landmark_count = landmark_count
        self.backbone = resnet18(weights=None)
        self.backbone.fc = nn.Identity()
        self.overall = nn.Linear(512, 1)
        self.landmarks = nn.Linear(512, landmark_count * 2)
        self.region = nn.Linear(512, 4)
        self.visibility = nn.Linear(512, landmark_count)
        self.components = nn.Linear(512, len(COMPONENTS))

    def forward(self, images):
        features = self.backbone(images)
        corners = torch.sigmoid(self.region(features)).reshape(-1, 2, 2)
        return {
            "overall": 1 + 4 * torch.sigmoid(self.overall(features)).squeeze(-1),
            "landmarks": torch.sigmoid(self.landmarks(features)).reshape(
                -1, self.landmark_count, 2
            ),
            "region": torch.cat((corners.min(dim=1).values, corners.max(dim=1).values), dim=1),
            "visibility_logits": self.visibility(features),
            "components": 1 + 4 * torch.sigmoid(self.components(features)),
        }


def masked_loss(predictions: dict, targets: dict) -> tuple[torch.Tensor, dict]:
    losses = {}
    for name in ("overall", "landmarks", "region", "components"):
        if name not in targets:
            continue
        expected, mask = targets[name]
        if mask.any():
            differences = (predictions[name] - expected).square()
            losses[name] = differences[mask].mean()
    if "visibility" in targets:
        expected, mask = targets["visibility"]
        if mask.any():
            losses["visibility"] = nn.functional.binary_cross_entropy_with_logits(
                predictions["visibility_logits"][mask], expected[mask]
            )
    if not losses:
        raise ValueError("No genuine labeled targets in this batch")
    weights = {"landmarks": 100.0, "region": 10.0}
    total = sum(loss * weights.get(name, 1.0) for name, loss in losses.items())
    return total, {name: float(value.detach()) for name, value in losses.items()}
