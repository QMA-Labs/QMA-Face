# Research protocol and interpretation

## Dataset and split

The historical face engine used SCUT-FBP5500, with overall subjective ratings and 86 annotated points. The project's hash-based grouping produced 4,407 training, 568 validation, and 525 test images. One image lacked landmark annotations. Exact duplicate handling is implemented; identity separation across different photos has not been independently verified.

This is the project's split, not a claim to reproduce the dataset authors' official benchmark split. Obtain data under its own terms from the [authors' repository](https://github.com/HCIILAB/SCUT-FBP5500-Database-Release). Training images and original annotation files are not included here.

## Training

`qma_face.research.data` audits images/annotations and records a local manifest. Absent labels are masked, not invented. The model is one shared ResNet-18 with trained overall and landmark heads; component/visibility/region heads without labels remain untrained and are not exported as functioning capabilities.

```powershell
python -m qma_face.research.train --dataset "D:\Datasets\SCUT-FBP5500_v2" --output build/research --epochs 24 --batch-size 32 --augment --cache-images --workers 0 --patience 6
```

This is a training entry point, not a recipe guaranteed to reproduce the published weights from a fresh initialization. Historical weights had prior training stages before 0.14 refinement. Record seeds, initialization hash, completed epochs, selected epoch, splits, and all hyperparameters.

## Landmark-only refinement in 0.14

An initial 7-epoch full fine-tuning experiment did not improve landmarks and was not deployed. The accepted experiment froze the backbone and overall head, cached six augmented feature views per existing training image, and optimized only the landmark head. It completed 80 epochs and selected epoch 78 using validation mean/eye-region errors. Non-landmark parameters were checked for bitwise equality.

```powershell
python -m qma_face.research.refine_landmarks --manifest build/research/dataset-manifest.local.json --initialize models/weights/qma-face-engine-research-v1.pt --output build/refinement
```

Augmentation includes paired image/point 2D rotation, translation, scale, brightness, and contrast transforms. Out-of-bounds annotations are masked. These are not new people/photos and do not supply 3D pose labels.

[Comparison data](refine014-comparison.json) records validation and the previously used test split. Validation gates required no rating regression and improvement in overall landmark and eye-region error. Do not use the test split to select checkpoints. No independent external validation or calibrated confidence is claimed.

## ONNX export

With compatible PT weights/evaluation metadata under `models`, run:

```powershell
python tools/export_compact_engine.py --manifest build/research/dataset-manifest.local.json
```

The tool checks exported rating/point parity against the PT implementation on the manifest's test records and checks a subset of Grad-CAM outputs. Keep any new run's evaluation/export metadata alongside the exact checkpoint. Conversion parity is not new scientific accuracy validation.

## Interpretation boundaries

- Subjective ratings reflect the dataset/model/raters, not a universal or objective standard.
- The 0–100 score is `(rating_1_to_5 - 1) * 25`, not a probability or accuracy percentage.
- Geometry uses pixels in the selected crop. Lens, framing, pose, expression, and landmark errors affect it; the same image framed differently can score differently.
- Eye/outline warning thresholds are heuristics requesting map review, not diagnoses or calibrated rejection probabilities.
- Region blur and Grad-CAM reflect sensitivity to the edited input. Effects overlap, are non-additive, and do not prove why a feature is attractive.
- No per-feature beauty labels, genuine 3D pose supervision, calibrated face acceptance confidence, or character labels are available.

Priorities before broader deployment: independently reviewed identity grouping, consent/data rights, held-out external conditions and populations, crop/point robustness, calibrated uncertainty, and clean-system packaging validation.
