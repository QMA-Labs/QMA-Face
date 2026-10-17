import time
from pathlib import Path

from qma_face.core.config import PROJECT_ROOT


class ResearchBeauty:
    """Experimental overall-score baseline, not the final multi-output face engine."""

    def __init__(self, root: Path = PROJECT_ROOT):
        self.root = root
        self.model = None
        self.device = None

    def load(self, device: str | None = None) -> None:
        import numpy as np
        import torch
        from torchvision.models import resnet18

        path = self.root / "models/weights/resnet18_py3.pth"
        if not path.is_file():
            raise FileNotFoundError("Research beauty weights are missing")
        # The converted checkpoint includes numeric NumPy scalars. Only these known numeric
        # types are allowed; arbitrary pickle globals and unsafe loading are never enabled.
        numeric_types = [np.dtype, type(np.dtype("float32")), type(np.dtype("float64"))]
        scalar = np.core.multiarray.scalar
        with torch.serialization.safe_globals(
            numeric_types + [(scalar, "numpy.core.multiarray.scalar")]
        ):
            checkpoint = torch.load(path, map_location="cpu", weights_only=True)
        state = checkpoint.get("state_dict", checkpoint)
        renamed = {}
        for key, value in state.items():
            key = key.removeprefix("module.")
            if key.startswith("group1."):
                key = key.removeprefix("group1.")
            key = key.replace(".group1.", ".").replace("group2.fullyconnected.", "fc.")
            renamed[key] = value
        state = renamed
        model = resnet18(weights=None, num_classes=1)
        model.load_state_dict(state, strict=True)
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.model = model.eval().to(self.device)

    def predict(self, image, *, cropped_face_confirmed: bool = False) -> dict:
        import torch
        from torchvision import transforms

        if not cropped_face_confirmed:
            raise ValueError("The research baseline requires an explicitly selected face crop")
        if self.model is None:
            self.load()
        preprocess = transforms.Compose(
            [
                transforms.Resize((224, 224)),
                transforms.ToTensor(),
                transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
            ]
        )
        tensor = preprocess(image.convert("RGB")).unsqueeze(0).to(self.device)
        if self.device == "cuda":
            torch.cuda.synchronize()
        started = time.perf_counter()
        with torch.inference_mode():
            score = float(self.model(tensor).item())
        if self.device == "cuda":
            torch.cuda.synchronize()
        return {
            "raw_score_1_to_5": score,
            "model": "SCUT-FBP5500 ResNet-18 research mirror",
            "source": "https://huggingface.co/Gustrd/SCUT-FBP5500-PyTorch-Model",
            "device": self.device,
            "forward_ms": round((time.perf_counter() - started) * 1000, 3),
            "status": "research_runtime_test_only",
            "component_scores": None,
            "scientific_validation": "not_completed",
            "redistribution": "not_cleared",
            "preprocessing": "224x224 RGB, ImageNet normalization; validation pending",
        }
