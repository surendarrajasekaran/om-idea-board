import hashlib
import json
import shutil
import subprocess
import unittest

import yaml

from scripts.release_config import (
    CHART,
    GITOPS_ROOT,
    VALUES,
    image_values,
    resource_values,
)


class DeploymentPolicyTests(unittest.TestCase):
    def setUp(self):
        self.profile = {
            "environment": "production",
            "source": "policy-fallback",
            "profile": {
                "replicas": 2,
                "cpu_request": "100m",
                "memory_request": "128Mi",
                "rationale": "Bounded test",
            },
        }

    def test_digest_compatible_with_original_chart(self):
        digest = "a" * 64
        values = image_values(f"ghcr.io/owner/app:abc123@sha256:{digest}")
        self.assertEqual(
            values["repository"] + ":" + values["tag"],
            f"ghcr.io/owner/app:abc123@sha256:{digest}",
        )
        self.assertEqual(
            image_values(f"ghcr.io/owner/app@sha256:{digest}")["tag"],
            f"pinned@sha256:{digest}",
        )

    def test_reject_mutable_and_command_inputs(self):
        for image in [
            "nginx",
            "ghcr.io/owner/app:latest",
            "$(touch /tmp/pwn)",
            "repo:tag;bad",
            "repo@sha256:bad",
        ]:
            with self.subTest(image=image), self.assertRaises(ValueError):
                image_values(image)

    def test_environment_and_production_policy(self):
        with self.assertRaises(ValueError):
            resource_values(self.profile, "staging", "aws")
        self.profile["profile"]["replicas"] = 1
        with self.assertRaises(ValueError):
            resource_values(self.profile, "production", "aws")

    def test_gcp_profile_respects_cpu_memory_ratio(self):
        self.profile["profile"].update(cpu_request="500m", memory_request="128Mi")
        result = resource_values(self.profile, "production", "gcp")
        self.assertEqual(
            result["resources"]["requests"], {"cpu": "500m", "memory": "512Mi"}
        )


@unittest.skipUnless(shutil.which("helm"), "Helm is required for chart contract tests")
class CommonChartTests(unittest.TestCase):
    def test_supplied_chart_is_unchanged(self):
        manifest = json.loads(
            (GITOPS_ROOT / "helm-templates/nucleus-source.json").read_text()
        )
        for relative, digest in manifest["sha256"].items():
            self.assertEqual(
                hashlib.sha256((CHART / relative).read_bytes()).hexdigest(),
                digest,
                relative,
            )

    def test_rendered_releases(self):
        for component in ("frontend", "backend"):
            with self.subTest(component=component):
                args = [
                    "helm",
                    "template",
                    f"idea-board-{component}",
                    str(CHART),
                    "-f",
                    str(VALUES[component]),
                ]
                documents = list(
                    yaml.safe_load_all(subprocess.check_output(args, text=True))
                )
                deployment = next(
                    item for item in documents if item and item["kind"] == "Deployment"
                )
                service = next(
                    item for item in documents if item and item["kind"] == "Service"
                )
                pod = deployment["spec"]["template"]["spec"]
                self.assertFalse(pod["automountServiceAccountToken"])
                self.assertEqual(
                    service["spec"]["type"],
                    "LoadBalancer" if component == "frontend" else "ClusterIP",
                )
                container = pod["containers"][0]
                self.assertEqual(
                    container["readinessProbe"]["httpGet"]["path"], "/health/ready"
                )
                self.assertTrue(container["securityContext"]["runAsNonRoot"])
                if component == "backend":
                    self.assertEqual(
                        pod["initContainers"][0]["command"],
                        ["python", "-m", "app.migrate"],
                    )
                    self.assertEqual(
                        pod["initContainers"][0]["image"], container["image"]
                    )
                    self.assertEqual(
                        container["envFrom"][0]["secretRef"]["name"],
                        "idea-board-database",
                    )
                else:
                    self.assertEqual(
                        next(
                            x["value"]
                            for x in container["env"]
                            if x["name"] == "BACKEND_HOST"
                        ),
                        "idea-board-backend",
                    )
