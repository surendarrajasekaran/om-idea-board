"""CLI imports must work when Python puts scripts/ first on sys.path."""

from pathlib import Path
import subprocess
import sys
import unittest


class CLITests(unittest.TestCase):
    def test_application_repository_does_not_track_helm_chart_copies(self):
        root = Path(__file__).resolve().parents[1]
        tracked = subprocess.check_output(
            [
                "git",
                "ls-files",
                "--",
                "helm-common",
                "helm-overides",
                "helm-templates",
                "docs",
                "deploy",
                "infra",
                "terraform",
            ],
            cwd=root,
            text=True,
        )
        self.assertEqual(
            tracked.strip(),
            "",
            "Platform configuration belongs in the GitOps/Terraform repositories",
        )

    def test_entrypoints_do_not_shadow_standard_library(self):
        root = Path(__file__).resolve().parents[1]
        for name in (
            "smoke",
            "probe",
            "ai_ops",
            "security_scan",
            "gitops_release",
            "gitops_monitor",
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
