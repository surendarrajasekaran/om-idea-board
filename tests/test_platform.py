import argparse
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from scripts import infra_init, run_platform
from scripts.deploy import deploy
from scripts.workload_policy import namespace_resources, network_policies


def profile():
    return {
        "environment": "staging",
        "source": "policy-fallback",
        "profile": {
            "replicas": 1,
            "cpu_request": "250m",
            "memory_request": "256Mi",
            "rationale": "Test",
        },
    }


class PreflightTests(unittest.TestCase):
    def exercise(self, extra, prepared=None):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            file = root / "profile.json"
            file.write_text(json.dumps(prepared if prepared is not None else profile()))
            argv = [
                "run_platform.py",
                "--cloud",
                "aws",
                "--region",
                "ap-south-1",
                "--state-bucket",
                "test-state",
                "--tag",
                "test",
                "--skip-infra",
                "--profile",
                str(file),
                *extra,
            ]
            with (
                patch.object(run_platform, "ROOT", root),
                patch("sys.argv", argv),
                patch.object(run_platform.shutil, "which", return_value="/mock/tool"),
                patch.object(run_platform, "execute") as execution,
                patch.dict("os.environ", {"GHCR_TOKEN": ""}),
            ):
                with self.assertRaises((SystemExit, ValueError)):
                    run_platform.main()
                execution.assert_not_called()

    def test_invalid_image_mode_fails_before_cloud_commands(self):
        self.exercise(["--frontend-image", "repo/frontend:test"])

    def test_invalid_profile_fails_before_cloud_commands(self):
        self.exercise(["--skip-build"], {**profile(), "profile": {"replicas": 999}})

    def test_profile_target_mismatch_fails_before_cloud_commands(self):
        self.exercise(["--skip-build"], {**profile(), "environment": "production"})

    def test_production_requires_https_before_cloud_commands(self):
        self.exercise(["--environment", "production", "--skip-build"])

    def test_image_injection_fails_before_cloud_commands(self):
        self.exercise(["--skip-build", "--frontend-image", "repo:test;touch /tmp/bad"])

    def test_state_is_isolated_by_stack_name(self):
        for cloud, expected in [
            ("aws", '"workboard/staging/terraform.tfstate"'),
            ("gcp", '"workboard/staging"'),
        ]:
            with self.subTest(cloud=cloud), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / "infra").mkdir()
                argv = [
                    "infra_init.py",
                    "--cloud",
                    cloud,
                    "--environment",
                    "staging",
                    "--bucket",
                    "test-state",
                    "--region",
                    "region-1",
                    "--name",
                    "workboard",
                ]
                with (
                    patch.object(infra_init, "ROOT", root),
                    patch("sys.argv", argv),
                    patch.object(infra_init.subprocess, "run"),
                ):
                    infra_init.main()
                self.assertIn(expected, (root / "infra/backend.tf").read_text())


class WorkloadSecurityTests(unittest.TestCase):
    def test_namespace_enforces_restricted_and_bounded_resources(self):
        resources = namespace_resources("workboard-staging")["items"]
        self.assertEqual(
            resources[0]["metadata"]["labels"]["pod-security.kubernetes.io/enforce"],
            "restricted",
        )
        self.assertEqual(resources[1]["spec"]["hard"]["services.loadbalancers"], "1")
        self.assertEqual(resources[2]["spec"]["egress"], [])

    def test_backend_accepts_only_frontend_and_egresses_to_database_and_dns(self):
        policy = network_policies("workboard", "backend", ["10.90.21.0/24"])[0]["spec"]
        self.assertEqual(
            policy["ingress"][0]["from"][0]["podSelector"]["matchLabels"][
                "app.kubernetes.io/instance"
            ],
            "workboard-frontend",
        )
        self.assertEqual(
            policy["egress"][1]["to"], [{"ipBlock": {"cidr": "10.90.21.0/24"}}]
        )
        self.assertEqual(policy["egress"][1]["ports"][0]["port"], 5432)
        self.assertNotIn(
            80, [p["port"] for rule in policy["egress"] for p in rule["ports"]]
        )

    def test_public_or_unbounded_database_network_is_rejected(self):
        for cidrs in [
            [],
            ["0.0.0.0/0"],
            ["8.8.8.8/32"],
            ["10.0.0.0/8"],
            ["10.0.0.1/24"],
        ]:
            with self.subTest(cidrs=cidrs), self.assertRaises(ValueError):
                network_policies("test", "backend", cidrs)

    @unittest.skipUnless(shutil.which("helm"), "Requires Helm")
    def test_custom_stack_https_and_migration_secret_render(self):
        import yaml

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            file = output / "profile.json"
            prepared = profile()
            prepared["environment"] = "production"
            prepared["profile"]["replicas"] = 2
            file.write_text(json.dumps(prepared))
            args = argparse.Namespace(
                name="workboard",
                tls_secret="board-tls",
                public_host="board.example.com",
                profile=file,
                cloud="gcp",
                environment="production",
                frontend_image="repo/frontend:review",
                backend_image="repo/backend:review",
                output=output,
                render_only=True,
                context=None,
                namespace=None,
                timeout=5,
                pull_secret="",
                require_ai=False,
                database_egress_cidr=["10.93.0.0/16"],
            )
            deploy(args)
            web = [
                x
                for x in yaml.safe_load_all(
                    (output / "frontend-rendered.yaml").read_text()
                )
                if x
            ]
            api = [
                x
                for x in yaml.safe_load_all(
                    (output / "backend-rendered.yaml").read_text()
                )
                if x
            ]
            service = next(x for x in web if x["kind"] == "Service")
            self.assertEqual(service["metadata"]["name"], "workboard-frontend")
            self.assertEqual(service["spec"]["ports"][0]["port"], 443)
            self.assertEqual(service["spec"]["ports"][0]["targetPort"], 8443)
            for documents in [web, api]:
                pod = next(x for x in documents if x["kind"] == "Deployment")["spec"][
                    "template"
                ]["spec"]
                self.assertEqual(
                    pod["securityContext"]["seccompProfile"]["type"], "RuntimeDefault"
                )
                self.assertTrue(
                    pod["containers"][0]["securityContext"]["readOnlyRootFilesystem"]
                )
            controls = yaml.safe_load((output / "namespace-rendered.yaml").read_text())[
                "items"
            ]
            policies = [x for x in controls if x["kind"] == "NetworkPolicy"]
            self.assertEqual(len(policies), 3)
            self.assertEqual(policies[-1]["spec"]["policyTypes"], ["Ingress", "Egress"])

            pod = next(x for x in api if x["kind"] == "Deployment")["spec"]["template"][
                "spec"
            ]
            self.assertEqual(
                pod["containers"][0]["envFrom"][0]["secretRef"]["name"],
                "workboard-database",
            )
            self.assertEqual(
                pod["initContainers"][0]["envFrom"][0]["secretRef"]["name"],
                "workboard-migration",
            )
