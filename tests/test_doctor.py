"""Tests for the non-invasive model-runtime preflight."""

import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from domain_slm import doctor


class DoctorTests(unittest.TestCase):
    def test_linux_is_reported_as_blocked_without_probing_metal(self):
        metal_probe = Mock(side_effect=AssertionError("Metal must not be imported on Linux"))
        report = doctor.inspect_environment(
            system="Linux", machine="x86_64", mlx_version="1.0", mlx_lm_version="1.0",
            metal_probe=metal_probe,
        )
        self.assertFalse(report["smoke_test_ready"])
        self.assertIsNone(report["metal_available"])
        self.assertFalse(report["model_loaded"])
        self.assertIn("requires macOS on Apple Silicon", report["blockers"][0])
        metal_probe.assert_not_called()

    def test_apple_silicon_requires_packages_and_verified_metal(self):
        report = doctor.inspect_environment(
            system="Darwin", machine="arm64", mlx_version=None, mlx_lm_version=None,
            metal_probe=Mock(side_effect=AssertionError("No mlx package to probe")),
        )
        self.assertFalse(report["smoke_test_ready"])
        self.assertTrue(any("mlx package" in item for item in report["blockers"]))

    def test_apple_silicon_is_ready_only_after_metal_probe(self):
        probe = Mock(return_value=(True, None))
        report = doctor.inspect_environment(
            system="Darwin", machine="arm64", mlx_version="0.30.0", mlx_lm_version="0.30.0",
            metal_probe=probe,
        )
        self.assertTrue(report["smoke_test_ready"])
        self.assertEqual(report["metal_available"], True)
        self.assertEqual(report["blockers"], [])
        probe.assert_called_once_with()

    def test_cli_emits_machine_readable_report_without_loading_a_model(self):
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT / "src")
        result = subprocess.run(
            [sys.executable, "-m", "domain_slm", "doctor"],
            cwd=ROOT, env=env, text=True, capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertIn("system", report)
        self.assertIn("memory_limit_bytes", report)
        self.assertIn("smoke_test_ready", report)
        self.assertFalse(report["model_loaded"])


if __name__ == "__main__":
    unittest.main()
