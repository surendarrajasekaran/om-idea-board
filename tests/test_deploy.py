import hashlib
import tempfile
import json
from pathlib import Path
import shutil
import subprocess
import unittest
from unittest.mock import Mock, patch

import yaml

from scripts.deploy import (
    CHART,
    Deployment,
    ROOT,
    image_values,
    overrides,
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

    def test_gcp_minimum_and_secret_reference(self):
        result = overrides(
            "backend",
            "repo:abc",
            self.profile,
            "production",
            "gcp",
            "pull-secret",
            "hash",
        )
        self.assertEqual(
            result["resources"]["requests"], {"cpu": "250m", "memory": "256Mi"}
        )
        self.assertEqual(result["image"]["pullSecrets"], [{"name": "pull-secret"}])
        self.assertNotIn("DATABASE_URL", json.dumps(result))

    def test_gcp_profile_respects_cpu_memory_ratio(self):
        self.profile["profile"].update(cpu_request="500m", memory_request="128Mi")
        result = resource_values(self.profile, "production", "gcp")
        self.assertEqual(
            result["resources"]["requests"], {"cpu": "500m", "memory": "512Mi"}
        )

    def test_failed_release_state_is_not_treated_as_fresh_install(self):
        deployment = Deployment("idea-board-staging", "explicit-context")
        deployment.helm = Mock(
            return_value=Mock(
                stdout='[{"name":"idea-board-backend","status":"failed"}]'
            )
        )
        with self.assertRaises(RuntimeError):
            deployment.snapshot()

    def test_recovery_url_uses_restored_service_protocol(self):
        deployment = Deployment(
            "idea-board-staging", "context", tls=True, public_host="new.example.com"
        )
        deployment.kube = Mock(
            return_value=Mock(
                stdout=json.dumps(
                    {
                        "spec": {"ports": [{"port": 80}]},
                        "status": {
                            "loadBalancer": {
                                "ingress": [{"hostname": "previous.example.com"}]
                            }
                        },
                    }
                )
            )
        )
        self.assertEqual(deployment.public_url(), "http://previous.example.com")

    def test_history_uses_known_deployed_revision(self):
        deployment = Deployment("idea-board-staging", "explicit-context")
        deployment.helm = Mock(
            side_effect=[
                Mock(stdout='[{"name":"idea-board-backend","status":"deployed"}]'),
                Mock(
                    stdout='[{"revision":1,"status":"superseded"},{"revision":2,"status":"failed"},{"revision":3,"status":"deployed"}]'
                ),
            ]
        )
        deployment.snapshot()
        self.assertEqual(
            deployment.previous, {"idea-board-backend": 3, "idea-board-frontend": None}
        )

    def test_pair_recovery_runs_in_reverse_and_checks_rollout(self):
        deployment = Deployment("idea-board-staging", "explicit-context")
        deployment.previous = {"idea-board-backend": 4, "idea-board-frontend": 7}
        deployment.attempted = ["idea-board-backend", "idea-board-frontend"]
        deployment.helm, deployment.kube = Mock(), Mock()
        result = deployment.recover()
        self.assertEqual(
            deployment.helm.call_args_list[0].args[:3],
            ("rollback", "idea-board-frontend", "7"),
        )
        self.assertEqual(
            deployment.helm.call_args_list[1].args[:3],
            ("rollback", "idea-board-backend", "4"),
        )
        self.assertEqual(deployment.kube.call_count, 2)
        self.assertEqual(result["idea-board-backend"], "restored revision 4")

    def test_first_install_cleanup_and_recovery_error_report(self):
        deployment = Deployment("idea-board-staging", "explicit-context")
        deployment.previous = {"idea-board-backend": None}
        deployment.attempted = ["idea-board-backend"]
        deployment.helm = Mock(
            side_effect=[Mock(stdout='[{"name":"idea-board-backend"}]'), Mock()]
        )
        self.assertIn("removed", deployment.recover()["idea-board-backend"])
        deployment.previous["idea-board-backend"] = 1
        deployment.helm = Mock(side_effect=RuntimeError("failed"))
        self.assertIn("RECOVERY FAILED", deployment.recover()["idea-board-backend"])


@unittest.skipUnless(shutil.which("helm"), "Helm is required for chart contract tests")
class CommonChartTests(unittest.TestCase):
    def test_supplied_chart_is_unchanged(self):
        manifest = json.loads((ROOT / "deploy/charts/nucleus-source.json").read_text())
        for relative, digest in manifest["sha256"].items():
            self.assertEqual(
                hashlib.sha256((CHART / relative).read_bytes()).hexdigest(),
                digest,
                relative,
            )

    def test_rendered_releases(self):
        for cloud in ("aws", "gcp"):
            for component in ("frontend", "backend"):
                with self.subTest(cloud=cloud, component=component):
                    args = [
                        "helm",
                        "template",
                        f"idea-board-{component}",
                        str(CHART),
                        "-f",
                        str(ROOT / f"deploy/{component}/custom-values.yaml"),
                    ]
                    if component == "frontend":
                        args += ["-f", str(ROOT / f"deploy/clouds/{cloud}.yaml")]
                    documents = list(
                        yaml.safe_load_all(subprocess.check_output(args, text=True))
                    )
                    deployment = next(
                        item
                        for item in documents
                        if item and item["kind"] == "Deployment"
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


class DeploymentTransactionTests(unittest.TestCase):
    def exercise(self, smoke_failure=False):
        import argparse
        import io
        from scripts.deploy import deploy

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            profile = output / "profile.json"
            profile.write_text(
                json.dumps(
                    {
                        "environment": "staging",
                        "source": "policy-fallback",
                        "profile": {
                            "replicas": 1,
                            "cpu_request": "250m",
                            "memory_request": "256Mi",
                            "rationale": "Test",
                        },
                    }
                )
            )
            args = argparse.Namespace(
                profile=profile,
                cloud="aws",
                environment="staging",
                frontend_image="repo/frontend:abc",
                backend_image="repo/backend:abc",
                output=output,
                render_only=False,
                context="explicit-test-context",
                namespace=None,
                timeout=5,
                pull_secret="",
                require_ai=False,
            )
            state = {
                key: {"value": value}
                for key, value in {
                    "cloud": "aws",
                    "environment": "staging",
                    "name": "idea-board",
                    "database_url": "postgresql+psycopg://ideas_app:never-leak-this@db/ideas",
                    "migration_database_url": "postgresql+psycopg://ideas:migration-never-leak-this@db/ideas",
                    "application_password": "a" * 32,
                    "database_egress_cidrs": ["10.40.21.0/24", "10.40.22.0/24"],
                }.items()
            }
            platform = Mock()
            platform.namespace = "idea-board-staging"
            platform.previous = {"idea-board-backend": 2, "idea-board-frontend": 3}
            platform.restart_counts.return_value = {}
            platform.public_url.return_value = "http://example.test"
            platform.recover.return_value = {
                "idea-board-backend": "restored revision 2",
                "idea-board-frontend": "restored revision 3",
            }
            evidence = {
                "requests": 20,
                "failures": 0,
                "p95_latency_ms": 20,
                "restarts": 0,
            }
            ready_response = io.BytesIO(b'{"status":"ready"}')
            ready_response.status = 200
            with (
                patch("scripts.deploy.Deployment", return_value=platform),
                patch(
                    "scripts.deploy.run", return_value=Mock(stdout=json.dumps(state))
                ),
                patch(
                    "scripts.deploy.database_certificate", return_value="test-public-ca"
                ),
                patch("scripts.deploy.collect", return_value=evidence),
                patch(
                    "scripts.deploy.assess",
                    return_value={"decision": "keep", "source": "policy-fallback"},
                ),
                patch(
                    "scripts.deploy.urllib.request.urlopen",
                    return_value=ready_response,
                ),
                patch(
                    "scripts.deploy.smoke",
                    side_effect=RuntimeError("smoke failed") if smoke_failure else None,
                ),
                patch.dict("os.environ", {"GHCR_TOKEN": ""}),
            ):
                if smoke_failure:
                    with self.assertRaises(RuntimeError):
                        deploy(args)
                else:
                    deploy(args)
            report = (output / "deployment.json").read_text()
            self.assertNotIn("never-leak-this", report)
            self.assertEqual(platform.upgrade.call_count, 2)
            return json.loads(report), platform

    def test_success_is_recorded_only_after_smoke(self):
        report, platform = self.exercise()
        self.assertEqual(report["status"], "healthy")
        platform.recover.assert_not_called()

    def test_post_rollout_failure_recovers_both_and_still_fails(self):
        report, platform = self.exercise(smoke_failure=True)
        self.assertEqual(report["status"], "failed")
        self.assertEqual(report["failure_type"], "RuntimeError")
        self.assertTrue(report["recovery_verified"])
        platform.recover.assert_called_once()


if __name__ == "__main__":
    unittest.main()
