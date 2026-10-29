"""CLI imports must work when Python puts scripts/ first on sys.path."""

from pathlib import Path
import subprocess
import sys
import unittest


class CLITests(unittest.TestCase):
    def test_entrypoints_do_not_shadow_standard_library(self):
        root = Path(__file__).resolve().parents[1]
        for name in (
            "smoke",
            "probe",
            "deploy",
            "run_platform",
            "infra_init",
            "ai_ops",
        ):
            with self.subTest(script=name):
                result = subprocess.run(
                    [sys.executable, str(root / f"scripts/{name}.py"), "--help"],
                    capture_output=True,
                    text=True,
                    cwd=root,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("usage:", result.stdout)
