# Rebuild specification

## Purpose

Build a reusable, configuration-driven pipeline for adapting a small language model to a narrow task using real parameter-efficient fine-tuning. Preparation, training, baseline and adapter evaluation, quality gates, experiment metadata, artifact registration, and local inference are separate responsibilities. The current implementation covers preparation only.

## Initial data slice

The included synthetic card-payment intent examples exercise JSONL ingestion, validation, normalized duplicate handling, label-stratified deterministic splits, and artifact fingerprints. They do not represent BANKING77 or an independently verified benchmark. Prepared message records are not tokenized training inputs; the model's actual chat template and assistant-only loss mask must be verified before optimization. A real training run requires appropriately licensed, provenance-tracked data and a genuinely held-out test set.

## Intended model and backend

The previously selected shared flagship checkpoint is `google/gemma-4-E4B-it` at revision `ee0ef6023621cff504d758262d4e04895a5af4a2`, with MLX-LM on Apple Silicon as the prospective backend. Pin and verify all framework versions, original weights, conversion provenance, tokenizer, and LoRA target modules in the rebuilt implementation. A quantized inference path does not establish training support. The earlier BANKING77 demonstration used a different Gemma 3 270M checkpoint; it must not be presented as an adapter for the flagship checkpoint.

The earlier execution artifacts and source were lost and are unavailable in this workspace. Prior reports about compatibility or performance are historical context, not evidence that this rebuild has passed those checks. This environment is Linux x86_64 with an 8 GiB memory limit; it cannot verify the intended Apple Metal execution path.

## Acceptance requirements

- Before substantial training, load the pinned base on suitable hardware and perform at least two real optimizer steps with verified supervised-token masks, nonzero gradients, changed adapter parameters, and unchanged frozen base weights.
- Save and reload the adapter in a fresh process with the exact base, then generate and record an actual prediction. Capture versions, hashes, duration, and memory usage.
- Train on a provenance-tracked task dataset; compare baseline and adapter with identical validation prompts and decoding. Record meaningful task metrics and failures; do not treat training loss as task quality.
- Freeze deterministic quality criteria before inspecting candidate results. Preserve rejected runs and keep final test data untouched until the candidate and protocol are frozen.
- Only approved and integrity-verified adapters may be made available for local inference. Every run must identify its configuration, dataset fingerprint, base revision, adapter, metrics, and status.
