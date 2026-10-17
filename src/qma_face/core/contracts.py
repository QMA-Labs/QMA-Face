"""Evidence contracts: unavailable results stay unavailable."""

from dataclasses import dataclass, field
from enum import StrEnum
from math import isfinite


class EvidenceKind(StrEnum):
    MEASUREMENT = "measurement"
    MODEL_PREDICTION = "model_prediction"
    SOURCE_CLAIM = "source_claim"


class Visibility(StrEnum):
    VISIBLE = "visible"
    PARTIAL = "partial"
    NOT_VISIBLE = "not_visible"


@dataclass(frozen=True)
class Citation:
    source_id: str
    page: int | None = None
    doi: str | None = None

    def __post_init__(self) -> None:
        if not self.source_id.strip():
            raise ValueError("A source identifier is required.")
        if self.page is not None and self.page < 1:
            raise ValueError("Page numbers start at one.")


@dataclass(frozen=True)
class FeatureResult:
    name: str
    kind: EvidenceKind
    value: float | str | None = None
    unit: str | None = None
    visibility: Visibility = Visibility.VISIBLE
    confidence: float | None = None
    calibration_id: str | None = None
    model_version: str | None = None
    citations: tuple[Citation, ...] = ()

    def __post_init__(self) -> None:
        if self.visibility == Visibility.NOT_VISIBLE and self.value is not None:
            raise ValueError("An invisible feature cannot have an observed result.")
        if isinstance(self.value, float) and not isfinite(self.value):
            raise ValueError("Numerical evidence must be finite.")
        if self.confidence is not None:
            if not 0 <= self.confidence <= 1 or not self.calibration_id:
                raise ValueError("Confidence requires a valid range and calibration reference.")
        if self.kind == EvidenceKind.SOURCE_CLAIM and not self.citations:
            raise ValueError("A source claim needs a citation.")
        if self.kind == EvidenceKind.MODEL_PREDICTION and not self.model_version:
            raise ValueError("A model prediction needs a model version.")


@dataclass(frozen=True)
class BeautyScore:
    component: str
    value: float
    model_version: str
    reference_dataset: str
    evaluation_id: str

    def __post_init__(self) -> None:
        if not isfinite(self.value) or not 0 <= self.value <= 100:
            raise ValueError("Beauty scores must be finite and between zero and one hundred.")
        if not all(
            (self.component, self.model_version, self.reference_dataset, self.evaluation_id)
        ):
            raise ValueError("Scores require their model, reference data and evaluation.")


@dataclass(frozen=True)
class AnalysisResult:
    analysis_id: str
    original_image_id: str
    status: str = "not_available"
    features: tuple[FeatureResult, ...] = ()
    scores: tuple[BeautyScore, ...] = ()
    warnings: tuple[str, ...] = ()
    transformations: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.status not in {"not_available", "processing", "partial", "completed", "failed"}:
            raise ValueError("Unsupported analysis status.")
        if self.status in {"not_available", "processing", "failed"} and (
            self.scores or self.features
        ):
            raise ValueError("Unavailable analysis cannot expose invented results.")
