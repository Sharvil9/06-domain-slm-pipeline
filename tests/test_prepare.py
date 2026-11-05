"""End-to-end checks for the dataset preparation CLI."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class PrepareTests(unittest.TestCase):
    def run_cli(self, config, output):
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT / "src")
        return subprocess.run(
            [sys.executable, "-m", "domain_slm", "--config", str(config), "--output", str(output)],
            cwd=ROOT, env=env, text=True, capture_output=True,
        )

    def test_end_to_end_is_deterministic_and_prevents_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            one, two = Path(tmp) / "one", Path(tmp) / "two"
            config = ROOT / "configs/sample.toml"
            for output in (one, two):
                result = self.run_cli(config, output)
                self.assertEqual(result.returncode, 0, result.stderr)
            names = ("train.jsonl", "validation.jsonl", "test.jsonl", "manifest.json")
            for name in names:
                self.assertEqual((one / name).read_bytes(), (two / name).read_bytes())
            manifest = json.loads((one / "manifest.json").read_text())
            self.assertEqual(manifest["raw_records"], 15)
            self.assertEqual([manifest["splits"][p]["total"] for p in ("train", "validation", "test")], [9, 3, 3])
            ids = []
            for part in ("train", "validation", "test"):
                contents = (one / f"{part}.jsonl").read_bytes()
                self.assertEqual(hashlib.sha256(contents).hexdigest(), manifest["files_sha256"][f"{part}.jsonl"])
                records = [json.loads(line) for line in contents.splitlines()]
                ids.extend(record["id"] for record in records)
                for record in records:
                    self.assertEqual(json.loads(record["messages"][1]["content"])["intent"], record["label"])
            self.assertEqual(len(ids), len(set(ids)))
            before = (one / "manifest.json").read_bytes()
            self.assertNotEqual(self.run_cli(config, one).returncode, 0)
            self.assertEqual((one / "manifest.json").read_bytes(), before)

    def test_same_label_normalized_duplicate_is_removed(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            sample = (ROOT / "data/sample.jsonl").read_text(encoding="utf-8")
            duplicate = json.loads(sample.splitlines()[0])
            duplicate["text"] = "  " + duplicate["text"].upper() + "  "
            (base / "input.jsonl").write_text(sample + json.dumps(duplicate) + "\n", encoding="utf-8")
            config = (ROOT / "configs/sample.toml").read_text(encoding="utf-8")
            (base / "config.toml").write_text(config.replace("../data/sample.jsonl", "input.jsonl"), encoding="utf-8")
            result = self.run_cli(base / "config.toml", base / "out")
            self.assertEqual(result.returncode, 0, result.stderr)
            manifest = json.loads((base / "out/manifest.json").read_text(encoding="utf-8"))
            self.assertEqual((manifest["raw_records"], manifest["unique_records"], manifest["duplicates_removed"]), (16, 15, 1))

    def test_conflicting_normalized_duplicates_fail_without_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "input.jsonl").write_text(
                '{"text":"Payment rejected","label":"a"}\n'
                '{"text":"  PAYMENT   rejected  ","label":"b"}\n', encoding="utf-8")
            (base / "config.toml").write_text(
                '[dataset]\npath="input.jsonl"\nlabels=["a","b"]\n'
                '[task]\ninstruction="Classify"\n'
                '[split]\nseed=42\nvalidation=0.2\ntest=0.2\n', encoding="utf-8")
            output = base / "out"
            result = self.run_cli(base / "config.toml", output)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("conflicting labels", result.stderr)
            self.assertFalse(output.exists())

    def test_invalid_json_fails_without_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "input.jsonl").write_text('{bad json}\n', encoding="utf-8")
            (base / "config.toml").write_text(
                '[dataset]\npath="input.jsonl"\nlabels=["a"]\n'
                '[task]\ninstruction="Classify"\n'
                '[split]\nseed=42\nvalidation=0.2\ntest=0.2\n', encoding="utf-8")
            result = self.run_cli(base / "config.toml", base / "out")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("invalid JSON", result.stderr)
            self.assertFalse((base / "out").exists())


if __name__ == "__main__":
    unittest.main()
