# Repository instructions

## Project

This independent Python project rebuilds a reusable domain-specific small language model adaptation pipeline. Preserve a clear distinction between implemented functionality and planned capabilities. Never represent a mock or a data transform as model fine-tuning.

## Layout and commands

- `src/domain_slm/`: pipeline code.
- `tests/`: automated tests.
- `data/`: small, licensed or clearly labelled sample inputs.
- `outputs/` and `artifacts/`: generated local files, excluded from Git.
- `make check`: syntax check and automated tests. Python 3.11+ is required.

## Engineering rules

- Work within this repository. Keep configuration and experiments reproducible; record dataset provenance and distinguish validation from held-out test data.
- Use genuine pretrained weights and verified parameter-efficient training for any training claim. Prefer Gemma, then DeepSeek, then Llama; do not select Qwen. Verify model, framework, license, hardware, and adapter compatibility before training.
- Prefer local execution and lightweight dependencies. Run resource-intensive model jobs sequentially and avoid loading multiple large models at once.
- Do not commit credentials, `.env` files, virtual environments, caches, model weights, datasets with uncertain redistribution rights, or generated artifacts. Keep samples small and label synthetic data.
- Run relevant checks, inspect `git status` and staged files, then commit and push after each meaningful milestone. Do not rewrite existing history.
