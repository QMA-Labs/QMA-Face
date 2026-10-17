"""Reproducible personal-use bundle; public release validation remains a separate gate."""

import argparse
import hashlib
import importlib.metadata
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "build/windows"
STAGE = WORK / "stage/QMAFace"


def copy(source, target):
    source, target = Path(source), Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    if source.is_dir():
        shutil.copytree(source, target, dirs_exist_ok=True)
    else:
        if target.exists():
            target.chmod(0o666)
        shutil.copy2(source, target)


def main(resources_only=False):
    WORK.mkdir(parents=True, exist_ok=True)
    # A code-drawn icon, without external art or redistributed system fonts.
    from PIL import Image, ImageDraw

    icon = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    draw = ImageDraw.Draw(icon)
    draw.rounded_rectangle((6, 6, 250, 250), radius=60, fill="#F4F0FE")
    draw.rounded_rectangle((44, 112, 214, 184), radius=35, fill="#8273D9")
    draw.ellipse((75, 65, 163, 154), fill="#8273D9")
    draw.ellipse((131, 91, 198, 159), fill="#8273D9")
    draw.ellipse((104, 134, 113, 143), fill="white")
    draw.ellipse((150, 134, 159, 143), fill="white")
    icon.save(
        WORK / "qma-face.ico",
        sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--onedir",
        "--windowed",
        "--name",
        "QMAFace",
        "--distpath",
        str(WORK / "stage"),
        "--workpath",
        str(WORK / "pyinstaller"),
        "--specpath",
        str(WORK),
        "--paths",
        str(ROOT / "src"),
        "--icon",
        str(WORK / "qma-face.ico"),
        "--collect-binaries",
        "onnxruntime",
    ]
    for name in (
        "torch",
        "torchvision",
        "qma_face.research",
        "onnx",
        "scipy",
        "pandas",
        "matplotlib",
        "sklearn",
        "sympy",
        "tkinter",
        "PySide6.QtQml",
        "PySide6.QtQuick",
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineWidgets",
    ):
        command.extend(["--exclude-module", name])
    command.append(str(ROOT / "tools/desktop_entry.py"))
    if resources_only:
        if not (STAGE / "QMAFace.exe").is_file():
            raise FileNotFoundError("Build the executable before refreshing model resources")
    else:
        with (WORK / "freeze-build.log").open("w", encoding="utf-8") as log:
            build_env = os.environ.copy()
            windows = Path(os.environ.get("WINDIR", "C:/Windows"))
            build_env["PATH"] = str(windows / "System32") + os.pathsep + build_env.get("PATH", "")
            subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True, env=build_env)
    align_native_dependencies()
    copy(ROOT / "assets", STAGE / "assets")
    # Only the CPU provider is used for the face engine. These optional GPU plugins
    # are separate backends, unused by our session, and need not be shipped.
    for name in ("onnxruntime_providers_cuda.dll", "onnxruntime_providers_tensorrt.dll"):
        (STAGE / "_internal/onnxruntime/capi" / name).unlink(missing_ok=True)
    for name in ("engine-evaluation.json", "engine-export.json"):
        copy(ROOT / "models" / name, STAGE / "models" / name)
    manifest = json.loads((ROOT / "models/manifest.json").read_text(encoding="utf-8"))
    export = json.loads((ROOT / "models/engine-export.json").read_text(encoding="utf-8"))
    onnx = ROOT / "models/weights/qma-face-engine-research-v1.onnx"
    manifest["models"][1]["artifacts"] = [
        {"name": onnx.name, "sha256": export["onnx_sha256"], "bytes": onnx.stat().st_size}
    ]
    manifest["models"][1]["source_checkpoint_sha256"] = export["source_checkpoint_sha256"]
    manifest["build_channel"] = "personal_noncommercial_research_not_public_release"
    from qma_face import __version__

    manifest["version"] = __version__
    for model in manifest["models"]:
        for artifact in model["artifacts"]:
            copy(
                ROOT / "models/weights" / artifact["name"],
                STAGE / "models/weights" / artifact["name"],
            )
    (STAGE / "models/manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    # Public-source builds include curated article summaries only.
    # Personal PDF indexes and documents must never be bundled implicitly.
    copy(ROOT / "sources/articles.json", STAGE / "sources/articles.json")
    registry = json.loads((ROOT / "sources/registry.json").read_text(encoding="utf-8"))
    registry["sources"] = [item for item in registry["sources"] if not item.get("path")]
    (STAGE / "sources/registry.json").write_text(json.dumps(registry, indent=2), encoding="utf-8")
    runtime = ROOT / "runtime/llama-cuda"
    for path in runtime.iterdir():
        if path.suffix.lower() == ".dll" or path.name in {
            "llama-server.exe",
            "LICENSE-LLVM-OpenMP",
        }:
            copy(path, STAGE / "runtime/llama-cuda" / path.name)
    licenses = STAGE / "licenses"
    for distribution in (
        "onnxruntime",
        "numpy",
        "Pillow",
        "PyInstaller",
        "PySide6_Essentials",
        "PySide6_Addons",
        "shiboken6",
    ):
        dist = importlib.metadata.distribution(distribution)
        for file in dist.files or []:
            if any(word in str(file).lower() for word in ("license", "notice", "copying")):
                source = Path(dist.locate_file(file))
                if source.is_file():
                    copy(source, licenses / distribution / Path(str(file)))
    for path in (WORK / "legal").glob("*"):
        copy(path, licenses / path.name)
    copy(ROOT / "docs/distribution-notice.txt", STAGE / "PERSONAL-USE.txt")
    copy(ROOT / "docs/SETUP.md", STAGE / "READ-ME.md")
    copy(WORK / "qma-face.ico", STAGE / "qma-face.ico")
    inventory = []
    for path in sorted(STAGE.rglob("*")):
        if path.is_file():
            with path.open("rb") as stream:
                digest = hashlib.file_digest(stream, "sha256").hexdigest()
            inventory.append(
                {
                    "path": path.relative_to(STAGE).as_posix(),
                    "bytes": path.stat().st_size,
                    "sha256": digest,
                }
            )
    assert len(manifest["models"]) == 2
    assert not any(p["path"].endswith((".pt", ".pth")) or "/torch/" in p["path"] for p in inventory)
    (STAGE / "payload-inventory.json").write_text(
        json.dumps({"files": inventory}, indent=2), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "files": len(inventory),
                "uncompressed_bytes": sum(p["bytes"] for p in inventory),
                "staging": str(STAGE),
            },
            indent=2,
        )
    )


def align_native_dependencies():
    # Qt uses the Windows ICU API. Poppler's versioned ICU on the build machine's
    # PATH is incompatible and must never shadow that OS library in a frozen app.
    for name in ("icuuc.dll", "icudt78.dll"):
        path = STAGE / "_internal" / name
        path.resolve().relative_to(STAGE.resolve())
        if path.exists():
            path.chmod(0o666)
            path.unlink()
    system = Path(os.environ.get("WINDIR", "C:/Windows")) / "System32"
    for name in (
        "msvcp140.dll",
        "msvcp140_1.dll",
        "msvcp140_2.dll",
        "vcruntime140.dll",
        "vcruntime140_1.dll",
    ):
        copy(system / name, STAGE / "_internal" / name)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--resources-only", action="store_true")
    main(resources_only=parser.parse_args().resources_only)
