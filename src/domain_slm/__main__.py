"""Prepare small intent datasets. This command does not train a model."""

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import logging
from pathlib import Path
import shutil
import sys
import tomllib
import unicodedata

LOG = logging.getLogger("domain_slm")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def normalized(text):
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split())


def prepare(config_path, output):
    config_path = Path(config_path).resolve()
    config_bytes = config_path.read_bytes()
    config = tomllib.loads(config_bytes.decode("utf-8"))
    data_cfg, task, split = config["dataset"], config["task"], config["split"]
    labels = data_cfg["labels"]
    instruction = task["instruction"]
    seed, val, test = split["seed"], split["validation"], split["test"]
    if (not isinstance(labels, list) or not labels or
            any(not isinstance(x, str) or not x.strip() for x in labels) or
            len(set(labels)) != len(labels)):
        raise ValueError("dataset.labels must contain unique nonempty strings")
    if not isinstance(instruction, str) or not instruction.strip():
        raise ValueError("task.instruction must be a nonempty string")
    if (type(seed) is not int or type(val) not in (int, float) or
            type(test) not in (int, float) or not 0 < val < 1 or
            not 0 < test < 1 or val + test >= 1):
        raise ValueError("split requires an integer seed and positive validation/test fractions totaling less than one")
    source = (config_path.parent / data_cfg["path"]).resolve()
    source_bytes = source.read_bytes()
    records = {}
    raw_count = 0
    for line_number, line in enumerate(source_bytes.decode("utf-8").splitlines(), 1):
        if not line.strip():
            raise ValueError(f"line {line_number}: blank record")
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"line {line_number}: invalid JSON: {exc.msg}") from exc
        if not isinstance(item, dict):
            raise ValueError(f"line {line_number}: expected an object")
        text, label = item.get("text"), item.get("label")
        if not isinstance(text, str) or not text.strip() or len(text) > 4096:
            raise ValueError(f"line {line_number}: text must contain 1–4096 characters")
        if not isinstance(label, str) or label not in labels:
            raise ValueError(f"line {line_number}: unsupported label")
        raw_count += 1
        key = normalized(text)
        if key in records:
            if records[key]["label"] != label:
                raise ValueError(f"line {line_number}: normalized duplicate has conflicting labels")
            continue
        records[key] = {"text": text.strip(), "label": label}
    by_label = defaultdict(list)
    for key, item in records.items():
        identifier = digest((item["label"] + "\0" + key).encode("utf-8"))
        order = digest((str(seed) + "\0" + identifier).encode("utf-8"))
        by_label[item["label"]].append((order, identifier, item))
    partitions = {"train": [], "validation": [], "test": []}
    for label in labels:
        items = sorted(by_label[label])
        if len(items) < 3:
            raise ValueError(f"label {label!r} needs at least three distinct examples")
        n_val, n_test = max(1, int(len(items) * val)), max(1, int(len(items) * test))
        if n_val + n_test >= len(items):
            raise ValueError(f"label {label!r} has no training examples under these split fractions")
        for index, (_, identifier, item) in enumerate(items):
            part = "validation" if index < n_val else "test" if index < n_val + n_test else "train"
            partitions[part].append({
                "id": identifier, "label": label,
                "messages": [
                    {"role": "user", "content": instruction.strip() + "\n\n" + item["text"]},
                    {"role": "assistant", "content": json.dumps({"intent": label}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))},
                ],
            })
    payloads = {}
    counts = {}
    for name, items in partitions.items():
        items.sort(key=lambda item: item["id"])
        payloads[name] = b"".join((json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8") for item in items)
        counts[name] = {"total": len(items), "labels": dict(sorted(Counter(item["label"] for item in items).items()))}
    manifest = {
        "schema_version": 1, "source_sha256": digest(source_bytes),
        "config_sha256": digest(config_bytes), "seed": seed,
        "raw_records": raw_count, "unique_records": len(records),
        "duplicates_removed": raw_count - len(records), "splits": counts,
        "files_sha256": {f"{name}.jsonl": digest(data) for name, data in payloads.items()},
    }
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.mkdir()  # Exclusive creation: never overwrite an existing run.
    try:
        for name, data in payloads.items():
            (output / f"{name}.jsonl").write_bytes(data)
        (output / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except Exception:
        shutil.rmtree(output)
        raise
    LOG.info("Prepared %s unique records (%s duplicates removed) in %s", len(records), raw_count - len(records), output)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, help="TOML configuration file")
    parser.add_argument("--output", required=True, help="New output directory; must not already exist")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    try:
        prepare(args.config, args.output)
    except (OSError, ValueError, KeyError, TypeError, UnicodeError) as exc:
        LOG.error("Preparation failed: %s", exc)
        return 2
    return 0


if __name__ == "__main__":
    if sys.argv[1:2] == ["doctor"]:
        from .doctor import main as doctor_main

        sys.exit(doctor_main(sys.argv[2:]))
    sys.exit(main())
