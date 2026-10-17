# Source setup

## Requirements and scope

- Primary target: Windows x64, Windows 10 build 19041 or later.
- Python 3.11–3.13; the local validation environment used Python 3.11.
- Use an editable install from the repository root. The application reads `assets`, `models`, and `sources` relative to this source tree; this is not a self-contained wheel distribution.
- Native Qt/ONNX dependencies are declared in `pyproject.toml`. PyTorch/torchvision are research extras, not required for the UI or compact ONNX runtime.
- Real model execution was tested on the developer's laptop, not a clean VM or every supported Windows/GPU configuration. CPU fallback can be much slower than GPU chat. No general memory or latency guarantee is claimed.

Follow the launch commands in the root README. `Start-QMA-Face.cmd` uses the local virtual environment through `launch.ps1`; `QMA_FACE_PYTHON` can select another installed interpreter.

## Model assets

The public clone does not include any weights or inference binaries. Starting the UI is separate from enabling inference. Files are not silently downloaded.

### Vision/chat

The configured role expects these files under `models/weights/`:

```text
Qwen3VL-4B-Instruct-Q4_K_M.gguf
mmproj-Qwen3VL-4B-Instruct-F16.gguf
```

Use the official [Qwen GGUF model repository](https://huggingface.co/Qwen/Qwen3-VL-4B-Instruct-GGUF), read its model card, and match artifacts/checksums in `models/manifest.json`. Changing model artifacts requires updating the manifest and validating the result; do not merely rename a different model.

The Windows local server belongs under `runtime/llama-cuda/llama-server.exe`, with its matching runtime DLLs. The private build used llama.cpp b11612 with CUDA 12.4. Obtain compatible binaries from the [official llama.cpp project](https://github.com/ggml-org/llama.cpp), retain the relevant notices, and validate compatibility. The code attempts GPU startup and then CPU fallback using the available local executable; CUDA dependency availability still matters.

### Face engine

The compact role expects:

```text
models/weights/qma-face-engine-research-v1.onnx
models/engine-evaluation.json
models/engine-export.json
```

The repository includes historical evaluation/export metadata, **not** the corresponding ONNX/PT weights. Research weights are not publicly redistributed while rights and validation gates remain unresolved. A public clone therefore cannot perform face analysis out of the box.

For an authorized research experiment, train the architecture using appropriately licensed data, retain its evaluation report, and perform ONNX export/parity checking. Keep the evaluation checkpoint hash and export hashes consistent. The PT fallback requires the research dependencies. See [RESEARCH.md](RESEARCH.md).

## Your own PDFs

Optional PDF indexing requires the `library` extra:

```powershell
python tools/import_personal_pdfs.py --pdf "D:\MyDocuments\notes.pdf" --source-id personal-notes --title "My research notes"
```

The tool appends/replaces that document's passages in `sources/local-only/pages.json`. It never uploads the PDF. Keep the PDF and index private; their paths, page text, and hashes are personal data. The public repository includes only curated article summaries. Do not force-add private files to Git.

## Data and configuration

| Setting | Purpose |
| --- | --- |
| `QMA_FACE_DATA_DIR` | Override the data directory. Development defaults to `.local-data`; frozen Windows builds use the user's local app-data directory. |
| `QMA_FACE_DEVICE=cpu` | Request the local chat backend's CPU mode. Startup remains dependent on compatible runtime files. |
| `QMA_FACE_PYTHON` | Select the interpreter used by the optional Windows launcher. |

The main UI supports English and French. The translator additionally supports Persian; its output is machine translation and must be checked for important numeric/source-sensitive meaning.

## Building a Windows bundle

This source includes the build recipe, **not a cleared public binary release**. Before a distribution, separately review model, data, runtime, Qt, and other dependency terms and include the required notices. The existing private installer must not be uploaded: it contains personal PDFs and artifacts not cleared for public redistribution.

With locally provisioned model/runtime files and the `build` extra installed:

```powershell
python tools/build_windows.py
```

This creates `build/windows/stage/QMAFace`. Its default source copy includes article summaries and a path-free registry, not personal PDFs/indexes. The script uses Windows system MSVC DLLs and a specific Qt/ICU compatibility adjustment from the local build; verify the resulting dependency set on your target system.

The Inno Setup recipe is `tools/windows-installer.iss`. Its default build and output roots are relative to the project; compiler definitions can override `BuildRoot` and `OutputRoot`. It uses the same application ID as the personal version. Do not run installer experiments against an existing user installation; use a separate VM for release testing.

`--resources-only` refreshes an existing staged executable's resources. It does not rebuild changed Python code. Use a full build after code changes.
