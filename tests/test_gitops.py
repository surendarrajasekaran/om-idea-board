import argparse
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

import yaml

from scripts.ai_ops import (
    HEALTH_SCHEMA,
    PROFILE_SCHEMA,
    AIUnavailable,
    ask_model,
    assess,
)
from scripts.gitops_monitor import wait_for_release
from scripts.gitops_release import publish
from scripts.gitops_state import current, mark_healthy, recover_images, save_release


def images(letter):
    return {
        component: f"example.com/board/{component}:release@sha256:{letter * 64}"
        for component in ("backend", "frontend")
    }


def manifests(selected):
    result = {
        "controls.yaml": "apiVersion: v1\nkind: ResourceQuota\nmetadata: {name: preserve-me}\nspec: {hard: {pods: '20'}}\n"
    }
    for component in ("backend", "frontend"):
        pod = {
            "metadata": {
                "annotations": {"idea-board/release-image": selected[component]}
            },
            "spec": {
                "containers": [
                    {
                        "name": component,
                        "image": selected[component],
                        "resources": {"requests": {"cpu": "100m", "memory": "128Mi"}},
                        "securityContext": {"readOnlyRootFilesystem": True},
                        "envFrom": [{"secretRef": {"name": "current-secret"}}],
                    }
                ]
            },
        }
        if component == "backend":
            pod["spec"]["initContainers"] = [
                {"name": "migrate", "image": selected[component]}
            ]
        result[f"{component}.yaml"] = yaml.safe_dump(
            {
                "apiVersion": "apps/v1",
                "kind": "Deployment",
                "metadata": {"name": component},
                "spec": {"replicas": 1, "template": pod},
            }
        )
    return result


class GitOpsRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root, self.target = Path(self.directory.name), "idea-board-aws-test"

    def publish(self, release_id, letter):
        return save_release(
            self.root,
            self.target,
            {
                "id": release_id,
                "images": images(letter),
                "source_commit": letter * 40,
                "public_url": "http://example.test",
            },
            manifests(images(letter)),
        )

    def test_recovery_changes_images_and_identity_but_preserves_security(self):
        self.publish("healthy", "a")
        mark_healthy(self.root, self.target, "healthy")
        self.publish("failed", "b")
        path = self.root / "environments" / self.target / "manifests/backend.yaml"
        failed_backend = yaml.safe_load(path.read_text())
        failed_backend["spec"]["replicas"] = 3
        failed_backend["spec"]["template"]["spec"]["containers"][0]["resources"] = {
            "requests": {"cpu": "500m", "memory": "512Mi"}
        }
        path.write_text(yaml.safe_dump(failed_backend))
        before = (
            self.root / "environments" / self.target / "manifests/controls.yaml"
        ).read_text()
        recovered = recover_images(self.root, self.target, "failed")
        self.assertEqual(recovered["images"], images("a"))
        self.assertEqual(current(self.root, self.target)["id"], recovered["id"])
        self.assertEqual(
            (
                self.root / "environments" / self.target / "manifests/controls.yaml"
            ).read_text(),
            before,
        )
        backend = yaml.safe_load(
            (
                self.root / "environments" / self.target / "manifests/backend.yaml"
            ).read_text()
        )["spec"]["template"]["spec"]
        self.assertEqual(yaml.safe_load(path.read_text())["spec"]["replicas"], 1)
        self.assertEqual(
            backend["containers"][0]["resources"]["requests"]["cpu"], "100m"
        )
        self.assertTrue(
            backend["containers"][0]["securityContext"]["readOnlyRootFilesystem"]
        )
        self.assertEqual(
            backend["containers"][0]["envFrom"][0]["secretRef"]["name"],
            "current-secret",
        )
        self.assertEqual(backend["initContainers"][0]["image"], images("a")["backend"])
        with self.assertRaisesRegex(ValueError, "already pending"):
            recover_images(self.root, self.target, recovered["id"])

    def test_no_rollback_without_known_good_and_no_stale_observations(self):
        self.publish("first", "a")
        with self.assertRaisesRegex(ValueError, "No previously"):
            recover_images(self.root, self.target, "first")
        self.publish("newer", "b")
        with self.assertRaisesRegex(ValueError, "Stale"):
            recover_images(self.root, self.target, "first")
        with self.assertRaisesRegex(ValueError, "Stale"):
            mark_healthy(self.root, self.target, "first")

    def test_recovery_checks_snapshot_integrity(self):
        self.publish("healthy", "a")
        mark_healthy(self.root, self.target, "healthy")
        (self.root / "releases" / self.target / "healthy/backend.yaml").write_text(
            "tampered"
        )
        self.publish("failed", "b")
        with self.assertRaisesRegex(ValueError, "checksum"):
            recover_images(self.root, self.target, "failed")

    def test_immutable_release_and_no_secret_manifests(self):
        self.publish("first", "a")
        with self.assertRaisesRegex(ValueError, "immutable"):
            self.publish("first", "b")
        unsafe = manifests(images("a"))
        unsafe["controls.yaml"] = (
            "apiVersion: v1\nkind: Secret\nmetadata: {name: unsafe}\n"
        )
        with self.assertRaisesRegex(ValueError, "Secrets"):
            save_release(
                self.root, self.target, {"id": "unsafe", "images": images("a")}, unsafe
            )
        self.assertFalse((self.root / "releases" / self.target / "unsafe").exists())
        unsafe["controls.yaml"] = yaml.safe_dump(
            {"apiVersion": "v1", "kind": "List", "items": [{"kind": "Secret"}]}
        )
        with self.assertRaisesRegex(ValueError, "Secrets"):
            save_release(
                self.root,
                self.target,
                {"id": "unsafe-list", "images": images("a")},
                unsafe,
            )

    def test_healthy_checkpoint_does_not_churn_git(self):
        self.publish("healthy", "a")
        self.assertTrue(mark_healthy(self.root, self.target, "healthy"))
        self.assertFalse(mark_healthy(self.root, self.target, "healthy"))


@unittest.skipUnless(shutil.which("helm"), "Helm is required for GitOps rendering")
class GitOpsPublishingTests(unittest.TestCase):
    def test_publish_into_repository_without_chart_copies(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            profile = root / "profile.json"
            profile.write_text(
                json.dumps(
                    {
                        "environment": "test",
                        "source": "policy-fallback",
                        "profile": {
                            "replicas": 1,
                            "cpu_request": "250m",
                            "memory_request": "128Mi",
                            "rationale": "Test canonical chart publishing",
                        },
                    }
                )
            )
            selected = images("a")
            publish(
                argparse.Namespace(
                    gitops_dir=root / "gitops",
                    target="idea-board-aws-test",
                    release_id="canonical-chart",
                    source_commit="a" * 40,
                    name="idea-board",
                    cloud="aws",
                    environment="test",
                    profile=profile,
                    frontend_image=selected["frontend"],
                    backend_image=selected["backend"],
                    tls_secret="",
                    public_host="",
                    public_url="http://example.test",
                    require_ai=False,
                    database_egress_cidr=["10.40.32.0/20"],
                )
            )
            metadata = current(root / "gitops", "idea-board-aws-test")
            self.assertEqual(metadata["images"], selected)
            self.assertEqual(metadata["source_commit"], "a" * 40)
            self.assertFalse((root / "gitops/charts").exists())
            for component in ("frontend", "backend"):
                path = (
                    root
                    / f"gitops/environments/idea-board-aws-test/manifests/{component}.yaml"
                )
                documents = list(yaml.safe_load_all(path.read_text()))
                self.assertFalse(
                    any(
                        "helm.sh/hook" in doc["metadata"].get("annotations", {})
                        for doc in documents
                    )
                )
                deployment = next(
                    doc for doc in documents if doc["kind"] == "Deployment"
                )
                container = deployment["spec"]["template"]["spec"]["containers"][0]
                self.assertEqual(container["image"], selected[component])
                self.assertIn(
                    {"name": "RELEASE_ID", "value": "canonical-chart"}, container["env"]
                )
                self.assertEqual(container["resources"]["requests"]["memory"], "128Mi")


class ProviderAndObservationTests(unittest.TestCase):
    def response(self, value, headers=None):
        result = io.BytesIO(json.dumps(value).encode())
        result.headers = headers or {}
        return result

    def test_nvidia_chat_response_has_local_schema_validation(self):
        proposal = {
            "replicas": 1,
            "cpu_request": "250m",
            "memory_request": "256Mi",
            "rationale": "Test",
        }
        envelope = {
            "choices": [
                {"finish_reason": "stop", "message": {"content": json.dumps(proposal)}}
            ]
        }
        with (
            patch.dict(
                "os.environ",
                {
                    "AI_PROVIDER": "nvidia",
                    "AI_API_KEY": "test-only",
                    "AI_MODEL": "test-model",
                },
                clear=True,
            ),
            patch(
                "scripts.ai_ops.urllib.request.urlopen",
                return_value=self.response(envelope),
            ) as request,
        ):
            self.assertEqual(
                ask_model("Propose", {"environment": "test"}, PROFILE_SCHEMA), proposal
            )
        self.assertEqual(
            request.call_args.args[0].full_url,
            "https://integrate.api.nvidia.com/v1/chat/completions",
        )
        body = json.loads(request.call_args.args[0].data)
        self.assertEqual(body["response_format"]["type"], "json_object")

    def test_unsupported_provider_and_truncated_output_fail_closed(self):
        with (
            patch.dict("os.environ", {"AI_PROVIDER": "arbitrary-host"}, clear=True),
            self.assertRaises(AIUnavailable),
        ):
            ask_model("Test", {}, HEALTH_SCHEMA)
        with (
            patch.dict(
                "os.environ",
                {"AI_PROVIDER": "groq", "AI_API_KEY": "test-only", "AI_MODEL": "test"},
                clear=True,
            ),
            patch(
                "scripts.ai_ops.urllib.request.urlopen",
                return_value=self.response({"choices": [{"finish_reason": "length"}]}),
            ),
            self.assertRaises(AIUnavailable),
        ):
            ask_model("Test", {}, HEALTH_SCHEMA)

    def test_http_monitor_does_not_invent_restart_telemetry(self):
        with patch(
            "scripts.ai_ops.ask_model",
            return_value={"recommendation": "keep", "summary": "Healthy"},
        ) as model:
            result = assess(
                {"requests": 20, "failures": 0, "p95_latency_ms": 50}, http_only=True
            )
        self.assertNotIn("restarts", model.call_args.args[1])
        self.assertNotIn("restarts", result["evidence"])
        self.assertEqual(result["telemetry_coverage"], "http-only")

    def test_release_check_requires_matching_frontend_and_backend(self):
        with (
            patch("scripts.gitops_monitor.time.sleep"),
            patch(
                "scripts.gitops_monitor.urllib.request.urlopen",
                side_effect=lambda *args, **kwargs: self.response(
                    {"release_id": "new"}, {"X-Idea-Board-Release": "new"}
                ),
            ) as request,
        ):
            self.assertTrue(wait_for_release("http://example.test", "new", timeout=5))
        self.assertEqual(request.call_count, 3)
        with (
            patch("scripts.gitops_monitor.time.sleep"),
            patch("scripts.gitops_monitor.time.monotonic", side_effect=[0, 1, 11]),
            patch(
                "scripts.gitops_monitor.urllib.request.urlopen",
                return_value=self.response(
                    {"release_id": "new"}, {"X-Idea-Board-Release": "old"}
                ),
            ),
        ):
            self.assertFalse(wait_for_release("http://example.test", "new", timeout=10))
