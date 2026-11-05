"""End-to-end and safety checks for Text-to-SQL preparation."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from domain_slm import sql_prepare


class SQLPrepareTests(unittest.TestCase):
    def run_cli(self, config, output):
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT / "src")
        return subprocess.run(
            [sys.executable, "-m", "domain_slm", "prepare-sql",
             "--config", str(config), "--output", str(output)],
            cwd=ROOT, env=env, text=True, capture_output=True,
        )

    def test_sample_is_deterministic_and_database_level_disjoint(self):
        with tempfile.TemporaryDirectory() as temporary:
            first, second = Path(temporary) / "first", Path(temporary) / "second"
            config = ROOT / "configs/text2sql_sample.toml"
            for output in (first, second):
                result = self.run_cli(config, output)
                self.assertEqual(result.returncode, 0, result.stderr)
            names = ("train.jsonl", "validation.jsonl", "test.jsonl", "manifest.json")
            for name in names:
                self.assertEqual((first / name).read_bytes(), (second / name).read_bytes())

            manifest = json.loads((first / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["source"], "Synthetic Text-to-SQL examples authored for this repository")
            self.assertFalse(manifest["final_evaluation_ready"])
            self.assertEqual(manifest["reference_queries_validated"], 9)
            self.assertEqual(manifest["database_count"], 3)
            split_ids = []
            for split in ("train", "validation", "test"):
                content = (first / f"{split}.jsonl").read_bytes()
                self.assertEqual(hashlib.sha256(content).hexdigest(), manifest["files_sha256"][f"{split}.jsonl"])
                rows = [json.loads(line) for line in content.splitlines()]
                self.assertEqual(len(rows), 3)
                database_ids = {row["db_id"] for row in rows}
                self.assertEqual(len(database_ids), 1)
                split_ids.extend(database_ids)
                for row in rows:
                    self.assertNotIn("expected", row)
                    self.assertEqual(len(row["reference_result_sha256"]), 64)
                    self.assertEqual(row["messages"][1]["role"], "assistant")
            self.assertEqual(len(split_ids), len(set(split_ids)))

    def test_existing_output_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "existing"
            output.mkdir()
            marker = output / "keep.txt"
            marker.write_text("preserve", encoding="utf-8")
            result = self.run_cli(ROOT / "configs/text2sql_sample.toml", output)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(marker.read_text(encoding="utf-8"), "preserve")

    def test_reference_query_denies_writes_and_unconfigured_tables(self):
        database = {
            "tables": {
                "items": {
                    "columns": [{"name": "id", "type": "INTEGER"}],
                    "rows": [[1]],
                },
            },
        }
        forbidden = (
            "DELETE FROM items",
            "UPDATE items SET id = 2",
            "DROP TABLE items",
            "ATTACH DATABASE ':memory:' AS other",
            "PRAGMA query_only = OFF",
            "SELECT * FROM sqlite_master",
            "SELECT random()",
            "SELECT load_extension('unavailable')",
        )
        for query in forbidden:
            with self.subTest(query=query):
                with self.assertRaisesRegex(ValueError, "SQL reference was rejected"):
                    sql_prepare.execute_reference(database, query)

    def test_reference_query_stops_at_instruction_budget(self):
        database = {
            "tables": {
                "items": {
                    "columns": [{"name": "id", "type": "INTEGER"}],
                    "rows": [[1]],
                },
            },
        }
        query = "WITH RECURSIVE n(x) AS (VALUES(1) UNION ALL SELECT x+1 FROM n) SELECT SUM(x) FROM n"
        with patch.object(sql_prepare, "_MAX_SQL_STEPS", 5000):
            with self.assertRaisesRegex(ValueError, "SQL reference was rejected"):
                sql_prepare.execute_reference(database, query)

    def test_reference_query_enforces_result_row_limit(self):
        database = {
            "tables": {
                "items": {
                    "columns": [{"name": "id", "type": "INTEGER"}],
                    "rows": [[1]],
                },
            },
        }
        query = "WITH RECURSIVE n(x) AS (VALUES(1) UNION ALL SELECT x+1 FROM n WHERE x<600) SELECT x FROM n"
        with self.assertRaisesRegex(ValueError, "result-row limit"):
            sql_prepare.execute_reference(database, query)


if __name__ == "__main__":
    unittest.main()
