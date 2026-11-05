# Domain SLM Pipeline

A fresh rebuild of a configuration-driven pipeline for adapting small language models to domain tasks. The intended workflow covers dataset preparation, genuine parameter-efficient fine-tuning, matched baseline evaluation, quality gates, experiment records, and local inference.

This repository currently contains the bootstrap only. No model training or evaluation has been run in this rebuild. Previous experiment artifacts and their Git history were not recovered into this workspace.

## Requirements and checks

Python 3.11 or newer and `make` are required. No Python packages are required for the bootstrap.

```sh
make check
```

`make check` compiles the Python source and runs the test suite. The first data-preparation slice and its smoke tests are the next milestone.

## Layout

- `src/domain_slm/` — pipeline implementation.
- `tests/` — automated checks.
- `data/` — small, clearly identified sample data (added with the data slice).
- `outputs/` — local generated output, excluded from Git.
- `.github/workflows/` — basic continuous integration.

Future training will use real pretrained weights and adapters. Large datasets, generated artifacts, model weights, credentials, and virtual environments stay outside Git. See `AGENTS.md` for engineering constraints.
