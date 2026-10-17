import os
import sys
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = (
    Path(sys.executable).resolve().parent
    if getattr(sys, "frozen", False)
    else Path(__file__).resolve().parents[3]
)


@dataclass(frozen=True)
class Settings:
    app_name: str = "QMA Face"
    version: str = "0.14.0"
    default_language: str = "en"
    supported_languages: tuple[str, ...] = ("en", "fr")
    maximum_models: int = 2
    save_original_photos: bool = False
    analysis_enabled: bool = True
    project_root: Path = PROJECT_ROOT


settings = Settings()


def data_directory() -> Path:
    default = PROJECT_ROOT / ".local-data"
    if getattr(sys, "frozen", False):
        default = (
            Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData/Local")))
            / "QMA/Face/Data"
        )
    return Path(os.environ.get("QMA_FACE_DATA_DIR", str(default)))
