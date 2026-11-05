# Rebuild plan

- [x] Bootstrap an independent repository, document safe exclusions, run checks, and push the first commit.
- [x] Implement and test a configuration-driven synthetic JSONL preparation slice with deterministic split receipts; push the milestone.
- [x] Record the intended architecture, recovered model selection, and the current environment limitation.
- [x] Persist a project-specific execution brief and add a non-invasive MLX/Metal environment preflight; validate on the current Linux executor.
- [ ] Establish a reproducible Apple Silicon environment and prove the selected Gemma 4 E4B backend with real loading, two LoRA optimizer steps, adapter changes, save/reload, and inference. Record resource usage and artifact hashes.
- [ ] Prepare a licensed Text-to-SQL dataset with database-level separation, validated references, and bounded read-only SQLite execution. Freeze evaluation and gate criteria before candidate results.
- [ ] Run one complete adapter experiment, compare it with the original base under matched validation conditions, and preserve honest results.
- [ ] Add only the tracking, approval, registration, and explicit skill selection needed to reproduce and serve verified adapters. Evaluate a frozen release candidate once on an untouched final test set.
- [ ] Reconstruct a separate historical banking benchmark and later a second skill adapter only after the first flagship workflow is verified.

Each meaningful milestone requires appropriate checks, `git status`, a descriptive commit, and a push. A missing Mac execution channel blocks the flagship smoke test; it does not establish that the Mac configuration will succeed.
