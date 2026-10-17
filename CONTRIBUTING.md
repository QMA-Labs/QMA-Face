# Contributing

Before sending a substantial code contribution, open an issue to agree scope and contribution terms: the project does not yet have a general software license grant.

## Useful reports

Include your Windows/Python versions, the application version, the action you took, expected and actual behavior, and a minimal reproduction. Prefer generated diagrams or synthetic fixtures over photos of real people. Do not post model server keys, personal PDF indexes, private chats, or absolute personal file paths.

## Local checks

Install the development and research extras shown in the README, then run:

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
python -m pytest -q
python -m ruff check src tests tools
```

Private document retrieval is intentionally skipped when the private page index is absent. Model-free tests should not download model weights or call hosted inference. GPU/real-model and installer validation are separate from ordinary source tests.

## Scientific changes

Keep training, validation, and test roles distinct. Report dataset identities/duplicates and missing labels. Use validation for selection; disclose previously evaluated test sets. Never relabel correlation, brightness perturbations, or subjective ratings as calibrated accuracy. Do not fabricate component labels, visibility, missing facial detail, or character classifications.
