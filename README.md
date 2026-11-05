# Domain SLM Pipeline

A fresh rebuild of a configuration-driven pipeline for adapting small language models to domain tasks. The intended workflow covers dataset preparation, genuine parameter-efficient fine-tuning, matched baseline evaluation, quality gates, experiment records, and local inference.

This rebuild currently supports dataset preparation. No model training or evaluation has been run in this rebuild. Previous experiment artifacts and their Git history were not recovered into this workspace.

## Requirements and checks

Python 3.11 or newer and `make` are required. No Python packages are required for the bootstrap.

```sh
make check
```

`make check` compiles the Python source and runs the test suite.

## Check model-runtime prerequisites

Before installing MLX or downloading model weights, run:

```sh
make doctor
```

The JSON report includes the current OS, architecture, CPU and memory limits, installed `mlx` and `mlx-lm` versions, and whether Apple Metal is available. `smoke_test_ready` is only an environment preflight; it does not load Gemma, prove training compatibility, or run inference. The command performs no network access and loads no model weights. On Linux or Intel macOS it reports the blocker while exiting successfully.

## Prepare the sample dataset

```sh
make demo
cat outputs/sample/manifest.json
```

The command reads `configs/sample.toml` and `data/sample.jsonl`, then writes `train.jsonl`, `validation.jsonl`, `test.jsonl`, and `manifest.json` to `outputs/sample/`. The sample consists of 15 hand-written synthetic examples; it is not BANKING77 or a benchmark. Its test split is a demonstration fixture, not a final evaluation set.

For another experiment, supply a TOML configuration and a JSONL file containing string `text` and `label` fields. Dataset paths are relative to the configuration file. The output directory must not exist:

```sh
PYTHONPATH=src python3 -m domain_slm --config configs/sample.toml --output outputs/another-run
```

The command validates records and labels, removes normalized duplicates, rejects conflicting labels, and assigns each unique input to one deterministic, label-stratified split. The manifest records hashes, counts, and the seed. Prepared messages describe the desired task; model-specific chat templates and target-token masking must be applied and verified during the later training stage. Outputs are not model weights or evaluation results.

## Layout

- `src/domain_slm/` — pipeline implementation.
- `tests/` — automated checks.
- `data/` — small, clearly identified sample data.
- `configs/` — task, input, and split configuration.
- `outputs/` — local generated output, excluded from Git.
- `.github/workflows/` — basic continuous integration.

Future training will use real pretrained weights and adapters. Large datasets, generated artifacts, model weights, credentials, and virtual environments stay outside Git. See `AGENTS.md` for engineering constraints.

See [SPEC.md](SPEC.md) for the intended architecture and [PLAN.md](PLAN.md) for the verified rebuild milestones and current hardware blocker.
