import copy
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import yaml

from scripts.deploy import GITOPS_ROOT


@unittest.skipUnless(
    shutil.which("helm"), "Helm is required for application-chart tests"
)
class ArgoApplicationsTests(unittest.TestCase):
    def setUp(self):
        self.chart = GITOPS_ROOT / "helm-templates/argocd-app-controller"
        self.values = yaml.safe_load(
            (
                GITOPS_ROOT / "helm-overides/argocd-app-controller/custom-values.yaml"
            ).read_text()
        )

    def render(self, values, success=True):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "values.yaml"
            path.write_text(yaml.safe_dump(values))
            result = subprocess.run(
                [
                    "helm",
                    "template",
                    "example-apps",
                    str(self.chart),
                    "--namespace",
                    "argocd",
                    "-f",
                    str(path),
                ],
                capture_output=True,
                text=True,
            )
        if not success:
            self.assertNotEqual(result.returncode, 0)
            return
        self.assertEqual(result.returncode, 0, result.stderr)
        return [item for item in yaml.safe_load_all(result.stdout) if item]

    def test_two_separate_applications_with_one_security_control_owner(self):
        apps = {item["metadata"]["name"]: item for item in self.render(self.values)}
        self.assertEqual(set(apps), {"idea-board-backend", "idea-board-frontend"})
        backend, frontend = apps["idea-board-backend"], apps["idea-board-frontend"]
        self.assertEqual(len(backend["spec"]["sources"]), 2)
        self.assertEqual(
            backend["spec"]["sources"][0]["path"], "helm-templates/nucleus"
        )
        self.assertEqual(frontend["spec"]["source"]["path"], "helm-templates/nucleus")
        self.assertEqual(
            backend["spec"]["sources"][1]["directory"], {"include": "controls.yaml"}
        )
        self.assertEqual(
            frontend["spec"]["source"]["helm"]["valueFiles"],
            ["../../helm-overides/idea-fe/custom-values.yaml"],
        )
        for app in apps.values():
            self.assertEqual(app["metadata"]["namespace"], "argocd")
            self.assertEqual(app["spec"]["project"], "idea-board-test")
            self.assertEqual(app["spec"]["destination"]["namespace"], "idea-board-test")
            self.assertNotIn("ignoreDifferences", app["spec"])
            self.assertNotIn("finalizers", app["metadata"])
            self.assertIn(
                "FailOnSharedResource=true", app["spec"]["syncPolicy"]["syncOptions"]
            )

    def test_disabled_entries_and_empty_defaults_create_nothing(self):
        self.assertEqual(self.render({}), [])
        self.values["applications"]["idea-board-backend"]["enabled"] = False
        self.values["applications"]["idea-board-frontend"]["enabled"] = False
        self.assertEqual(self.render(self.values), [])

    def test_reusable_overrides_preserve_explicit_false(self):
        values = copy.deepcopy(self.values)
        values.update(
            namePrefix="qa-", controllerNamespace="platform-argo", cascadeDeletion=True
        )
        app = values["applications"]["idea-board-frontend"]
        values["applications"] = {"web": app}
        app.update(
            namespace="another-target",
            project="another-project",
            repoURL="https://example.test/charts.git",
            targetRevision="release-1",
            sourcePath="charts/web",
            cascadeDeletion=False,
            helmValues={"replicas": 2},
            helmParameters=[{"name": "feature", "value": "on"}],
            syncPolicy={"automated": {"prune": False, "selfHeal": False}},
        )
        rendered = self.render(values)[0]
        self.assertEqual(rendered["metadata"]["name"], "qa-web")
        self.assertEqual(rendered["metadata"]["namespace"], "platform-argo")
        self.assertNotIn("finalizers", rendered["metadata"])
        self.assertEqual(rendered["spec"]["project"], "another-project")
        self.assertFalse(rendered["spec"]["syncPolicy"]["automated"]["prune"])
        self.assertFalse(rendered["spec"]["syncPolicy"]["automated"]["selfHeal"])
        source = rendered["spec"]["source"]
        self.assertEqual(source["repoURL"], app["repoURL"])
        self.assertEqual(source["path"], "charts/web")
        self.assertEqual(source["helm"]["valuesObject"], {"replicas": 2})

    def test_directory_and_kustomize_omit_empty_options(self):
        values = copy.deepcopy(self.values)
        values["applications"] = {
            "plain": {
                "enabled": True,
                "namespace": "test",
                "sourceType": "directory",
                "sourcePath": "manifests",
            },
            "overlay": {
                "enabled": True,
                "namespace": "test",
                "sourceType": "kustomize",
                "sourcePath": "overlays/test",
            },
        }
        for app in self.render(values):
            source = app["spec"]["source"]
            self.assertNotIn("helm", source)
            self.assertNotIn("directory", source)
            self.assertNotIn("kustomize", source)

    def test_invalid_or_incomplete_enabled_applications_fail(self):
        for changes in (
            {"enabled": "true"},
            {"namespace": ""},
            {"sourceType": "unknown"},
        ):
            values = copy.deepcopy(self.values)
            values["applications"]["idea-board-backend"].update(changes)
            with self.subTest(changes=changes):
                self.render(values, success=False)
        values = {
            "applications": {
                "web": {"enabled": True, "namespace": "test", "sourcePath": "chart"}
            }
        }
        self.render(values, success=False)


if __name__ == "__main__":
    unittest.main()
