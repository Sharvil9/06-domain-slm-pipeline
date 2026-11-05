"""Protect local credentials and generated artifacts from accidental staging."""

from pathlib import Path
import subprocess
import unittest


class GitignoreTests(unittest.TestCase):
    def test_local_artifacts_are_ignored_but_env_example_is_allowed(self):
        root = Path(__file__).resolve().parents[1]
        paths = [
            ".env", ".env.local", ".venv/lib/example.py",
            ".cache/example", "data/raw/example.jsonl",
            "outputs/run.json", "artifacts/adapter.json",
            "models/model.safetensors", "models/model.bin", ".env.example",
        ]
        result = subprocess.run(
            ["git", "check-ignore", "--stdin"], cwd=root,
            input="\n".join(paths) + "\n", text=True,
            capture_output=True, check=True,
        )
        self.assertEqual(set(result.stdout.splitlines()), set(paths) - {".env.example"})


if __name__ == "__main__":
    unittest.main()
