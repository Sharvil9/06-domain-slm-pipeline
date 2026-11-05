# Repository instructions

## Project

This repository rebuilds a reproducible domain-SLM adaptation pipeline. Its project-specific target is the pinned `google/gemma-4-E4B-it` checkpoint with MLX-LM and LoRA on Apple Silicon. `SPEC.md` is the technical source of truth; `PLAN.md` records verified progress and blockers.

The current runnable code prepares a small synthetic card-payment intent dataset. It is only a bootstrap example: it is not the intended Text-to-SQL task, a public benchmark, model training, or evidence of model quality. The historical training artifacts were not recovered. Never imply otherwise.

## Project-specific execution brief

Work upward from verifiable foundations, preserving the existing Git history:

1. Check the actual OS, processor, memory limit, accelerator, Python, and installed ML stack before selecting commands or downloading weights. The cloud executor is Linux x86_64 and cannot validate MLX or Apple Metal; recheck each environment rather than treating this note as permanent hardware evidence.
2. Prove the pinned Gemma 4 checkpoint and exact MLX-LM/LoRA path with a tiny real run before scaling: verify tokenizer/chat formatting and supervised-token masking, take at least two optimizer steps, show nonzero gradients and changed adapter weights while base weights remain frozen, then save, reload in a fresh process, and generate a real prediction.
3. Build the intended Text-to-SQL data path with explicit provenance and redistribution rights. Split by database, validate SQL references, and execute checks against bounded read-only SQLite connections. Keep validation and final test databases separate.
4. Compare the unmodified base and tuned adapter on identical prompts and decoding settings. Freeze metrics and acceptance gates before looking at final-test results; preserve failed runs and their evidence.
5. Register and expose only artifacts whose base revision, dataset, configuration, adapter hashes, and evaluation status are verified.

Do not replace the selected checkpoint or backend just to make an unsupported executor appear successful. If the required Apple Silicon runtime is unavailable, complete independent portable work, record the exact blocker in `PLAN.md`, and leave model compatibility/training claims unresolved. Mocks may test interfaces but never count as real model evidence.

## Layout and commands

- `src/domain_slm/`: pipeline code.
- `tests/`: automated tests.
- `data/`: small, licensed or clearly labelled sample inputs.
- `configs/`: checked-in, non-secret experiment configurations.
- `outputs/` and `artifacts/`: generated local files, excluded from Git.
- `make check`: syntax check and automated tests. Python 3.11+ is required.
- `make demo`: prepare the synthetic sample once; the output directory must not already exist.

## Engineering rules

- Work within this repository. Keep configuration and experiments reproducible; record dataset provenance and distinguish validation from held-out test data.
- Use genuine pretrained weights and verified parameter-efficient training for any training claim. Prefer Gemma, then DeepSeek, then Llama; do not select Qwen. Verify model, framework, license, hardware, and adapter compatibility before training.
- Prefer local execution and lightweight dependencies. Run resource-intensive model jobs sequentially and avoid loading multiple large models at once.
- Do not commit credentials, `.env` files, virtual environments, caches, model weights, datasets with uncertain redistribution rights, or generated artifacts. Keep samples small and label synthetic data.
- Run relevant checks, inspect `git status` and staged files, then commit and push after each meaningful milestone. Do not rewrite existing history.
