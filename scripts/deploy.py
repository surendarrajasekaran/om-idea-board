"""Deploy two releases of the supplied nucleus chart; verify and recover on failure."""

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time
import urllib.request

import yaml

try:
    from .ai_ops import PROFILE_SCHEMA, assess, validate_schema
    from .probe import collect
    from .smoke import smoke
except ImportError:
    from ai_ops import PROFILE_SCHEMA, assess, validate_schema
    from probe import collect
    from smoke import smoke

ROOT = Path(__file__).resolve().parents[1]
CHART = ROOT / "deploy/charts/nucleus"
RELEASES = ["idea-board-backend", "idea-board-frontend"]


def run(args, *, data=None, check=True):
    # Capture tool output: rendered Secrets and provider diagnostics must not leak.
    result = subprocess.run(args, input=data, text=True, capture_output=True)
    if check and result.returncode:
        raise RuntimeError(
            f"{args[0]} {args[1]} failed (exit {result.returncode}); inspect the cluster with your own credentials"
        )
    return result


def image_values(reference):
    if not re.fullmatch(
        r"[a-z0-9][a-z0-9./_-]*(?::[a-zA-Z0-9_.-]+)?(?:@sha256:[0-9a-f]{64})?",
        reference,
    ):
        raise ValueError("Invalid container image reference")
    if ":" not in reference.rsplit("/", 1)[-1] and "@" not in reference:
        raise ValueError("An explicit image tag or digest is required")
    repository, _, digest = reference.partition("@")
    tag = "pinned"
    if ":" in repository.rsplit("/", 1)[-1]:
        repository, tag = repository.rsplit(":", 1)
    if tag == "latest" and not digest:
        raise ValueError("Mutable latest images are not accepted for deployment")
    # nucleus concatenates repository:tag; Docker accepts tag@sha256:digest.
    return {
        "repository": repository,
        "tag": tag + ("@" + digest if digest else ""),
        "pullPolicy": "IfNotPresent",
    }


def resource_values(profile, environment, cloud):
    if not isinstance(profile, dict) or profile.get("environment") != environment:
        raise ValueError("Profile environment does not match deployment target")
    values = validate_schema(profile.get("profile"), PROFILE_SCHEMA)
    if environment == "production" and values["replicas"] < 2:
        raise ValueError("Production requires at least two replicas")
    cpu, memory = values["cpu_request"], values["memory_request"]
    # Portable minimums accommodate GKE Autopilot general-purpose pods.
    if cloud == "gcp":
        cpu = "250m" if cpu == "100m" else cpu
        memory = "256Mi" if memory == "128Mi" else memory
    return {
        "workload": {"replicaCount": values["replicas"]},
        "resources": {
            "requests": {"cpu": cpu, "memory": memory},
            "limits": {"cpu": "1", "memory": "512Mi"},
        },
    }


def overrides(
    component, reference, profile, environment, cloud, pull_secret="", db_hash=""
):
    result = resource_values(profile, environment, cloud)
    result["image"] = image_values(reference)
    if pull_secret:
        result["image"]["pullSecrets"] = [{"name": pull_secret}]
    result["podAnnotations"] = {"idea-board/release-image": reference}
    if component == "backend":
        result["podAnnotations"]["idea-board/database-version"] = db_hash
    return result


class Deployment:
    def __init__(self, namespace, context, timeout=600):
        if not re.fullmatch(r"[a-z][a-z0-9-]{0,61}[a-z0-9]", namespace):
            raise ValueError("Invalid namespace")
        self.namespace, self.context, self.timeout = namespace, context, timeout
        self.previous, self.attempted = {}, []

    def kube(self, *args, data=None, check=True):
        return run(
            ["kubectl", "--context", self.context, "-n", self.namespace, *args],
            data=data,
            check=check,
        )

    def helm(self, *args, check=True):
        return run(
            [
                "helm",
                *args,
                "--namespace",
                self.namespace,
                "--kube-context",
                self.context,
            ],
            check=check,
        )

    def snapshot(self):
        # A failed list is an access/configuration error, never an empty release list.
        existing = json.loads(self.helm("list", "--all", "-o", "json").stdout)
        for release in RELEASES:
            present = next((item for item in existing if item["name"] == release), None)
            if present and present["status"] != "deployed":
                raise RuntimeError(
                    f"{release} is {present['status']}; recover it before starting another deployment"
                )
            if present:
                history = json.loads(self.helm("history", release, "-o", "json").stdout)
                self.previous[release] = max(
                    int(item["revision"])
                    for item in history
                    if item["status"] == "deployed"
                )
            else:
                self.previous[release] = None

    def apply_secret(self, name, values, secret_type="Opaque"):
        secret = {
            "apiVersion": "v1",
            "kind": "Secret",
            "metadata": {"name": name, "namespace": self.namespace},
            "type": secret_type,
            "data": {
                key: base64.b64encode(value.encode()).decode()
                for key, value in values.items()
            },
        }
        self.kube("apply", "-f", "-", data=json.dumps(secret))

    def upgrade(self, release, component, override_file, cloud):
        # Both Helm 3 and Helm 4 are supported; their rollback flags differ.
        help_text = run(["helm", "upgrade", "--help"]).stdout
        atomic = (
            "--rollback-on-failure"
            if "--rollback-on-failure" in help_text
            else "--atomic"
        )
        self.attempted.append(release)
        args = [
            "upgrade",
            "--install",
            release,
            str(CHART),
            "--reset-values",
            atomic,
            "--wait",
            "--timeout",
            f"{self.timeout}s",
            "--history-max",
            "20",
            "-f",
            str(ROOT / f"deploy/{component}/custom-values.yaml"),
        ]
        if component == "frontend":
            args.extend(["-f", str(ROOT / f"deploy/clouds/{cloud}.yaml")])
        args.extend(["-f", str(override_file)])
        self.helm(*args)
        self.kube(
            "rollout", "status", f"deployment/{release}", f"--timeout={self.timeout}s"
        )

    def recover(self):
        results = {}
        for release in reversed(self.attempted):
            revision = self.previous[release]
            try:
                if revision is None:
                    exists = any(
                        item["name"] == release
                        for item in json.loads(
                            self.helm("list", "--all", "-o", "json").stdout
                        )
                    )
                    if exists:
                        self.helm(
                            "uninstall",
                            release,
                            "--wait",
                            "--timeout",
                            f"{self.timeout}s",
                        )
                    results[release] = "removed failed first installation"
                else:
                    self.helm(
                        "rollback",
                        release,
                        str(revision),
                        "--wait",
                        "--timeout",
                        f"{self.timeout}s",
                    )
                    self.kube(
                        "rollout",
                        "status",
                        f"deployment/{release}",
                        f"--timeout={self.timeout}s",
                    )
                    results[release] = f"restored revision {revision}"
            except (RuntimeError, ValueError):
                results[release] = "RECOVERY FAILED: operator action required"
        return results

    def restart_counts(self):
        pods = json.loads(
            self.kube(
                "get", "pods", "-l", "app.kubernetes.io/name=nucleus", "-o", "json"
            ).stdout
        )
        return {
            f"{pod['metadata']['uid']}/{container['name']}": container["restartCount"]
            for pod in pods["items"]
            if pod["metadata"]["labels"].get("app.kubernetes.io/instance") in RELEASES
            for container in pod.get("status", {}).get("containerStatuses", [])
        }

    def public_url(self):
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            service = json.loads(
                self.kube("get", "service", "idea-board-frontend", "-o", "json").stdout
            )
            for address in (
                service.get("status", {}).get("loadBalancer", {}).get("ingress", [])
            ):
                host = address.get("hostname") or address.get("ip")
                if host:
                    if ":" in host:
                        host = f"[{host}]"
                    return f"http://{host}"
            time.sleep(5)
        raise RuntimeError("Timed out waiting for the public load balancer")


def deploy(args):
    args.output.mkdir(parents=True, exist_ok=True)
    for filename in ("deployment.json", "health.json"):
        (args.output / filename).unlink(missing_ok=True)
    profile = json.loads(args.profile.read_text())
    # Validate everything before touching the cluster.
    settings = {
        component: overrides(
            component,
            getattr(args, f"{component}_image"),
            profile,
            args.environment,
            args.cloud,
            args.pull_secret,
        )
        for component in ("backend", "frontend")
    }
    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    if args.render_only:
        for component, values in settings.items():
            file = output / f"{component}-values.json"
            file.write_text(json.dumps(values, indent=2) + "\n")
            command = [
                "helm",
                "template",
                f"idea-board-{component}",
                str(CHART),
                "-f",
                str(ROOT / f"deploy/{component}/custom-values.yaml"),
            ]
            if component == "frontend":
                command += ["-f", str(ROOT / f"deploy/clouds/{args.cloud}.yaml")]
            rendered = run(command + ["-f", str(file)]).stdout
            list(yaml.safe_load_all(rendered))
            (output / f"{component}-rendered.yaml").write_text(rendered)
        print(f"Rendered and parsed both common-chart releases in {output}")
        return
    if not args.context:
        raise ValueError(
            "--context is required; an implicit current cluster is never used"
        )
    platform = Deployment(
        args.namespace or f"idea-board-{args.environment}", args.context, args.timeout
    )
    # Verify the output belongs to the requested cloud/environment, not another initialized state.
    outputs = json.loads(
        run(["terraform", f"-chdir={ROOT / 'infra'}", "output", "-json"]).stdout
    )
    for key, expected in [("cloud", args.cloud), ("environment", args.environment)]:
        if outputs[key]["value"] != expected:
            raise ValueError(f"Terraform {key} does not match requested target")
    db_url = outputs["database_url"]["value"]
    if not db_url.startswith("postgresql+psycopg://"):
        raise ValueError("Invalid Terraform database URL")
    namespace = {
        "apiVersion": "v1",
        "kind": "Namespace",
        "metadata": {"name": platform.namespace},
    }
    run(
        ["kubectl", "--context", args.context, "apply", "-f", "-"],
        data=json.dumps(namespace),
    )
    platform.snapshot()
    report = {
        "cloud": args.cloud,
        "environment": args.environment,
        "namespace": platform.namespace,
        "images": {"frontend": args.frontend_image, "backend": args.backend_image},
        "previous_revisions": platform.previous,
        "profile": profile,
        "status": "failed",
    }
    try:
        platform.apply_secret("idea-board-database", {"DATABASE_URL": db_url})
        settings["backend"]["podAnnotations"]["idea-board/database-version"] = (
            hashlib.sha256(db_url.encode()).hexdigest()
        )
        token = os.environ.get("GHCR_TOKEN")
        if token:
            username = os.environ.get("GHCR_USERNAME")
            if not username:
                raise ValueError("GHCR_USERNAME is required with GHCR_TOKEN")
            auth = base64.b64encode(f"{username}:{token}".encode()).decode()
            config = json.dumps({"auths": {"ghcr.io": {"auth": auth}}})
            platform.apply_secret(
                args.pull_secret or "idea-board-registry",
                {".dockerconfigjson": config},
                "kubernetes.io/dockerconfigjson",
            )
            for component in settings:
                settings[component]["image"]["pullSecrets"] = [
                    {"name": args.pull_secret or "idea-board-registry"}
                ]
        baseline = platform.restart_counts()
        with tempfile.TemporaryDirectory(prefix="idea-board-values-") as directory:
            for component in ("backend", "frontend"):
                values_file = Path(directory) / f"{component}.json"
                values_file.write_text(json.dumps(settings[component]))
                platform.upgrade(
                    f"idea-board-{component}", component, values_file, args.cloud
                )
        url = platform.public_url()
        report["url"] = url
        # AWS DNS/LB propagation can lag Service allocation; wait for readiness before measuring.
        deadline = time.monotonic() + args.timeout
        while True:
            try:
                with urllib.request.urlopen(
                    url + "/health/ready", timeout=5
                ) as response:
                    if response.status == 200 and json.load(response) == {
                        "status": "ready"
                    }:
                        break
            except (OSError, ValueError):
                pass
            if time.monotonic() >= deadline:
                raise RuntimeError("Public endpoint did not become ready")
            time.sleep(5)
        current = platform.restart_counts()
        new_restarts = sum(
            max(0, count - baseline.get(key, 0)) for key, count in current.items()
        )
        samples = collect(url, 20, new_restarts)
        after_probes = platform.restart_counts()
        samples["restarts"] = max(
            new_restarts,
            sum(
                max(0, count - baseline.get(key, 0))
                for key, count in after_probes.items()
            ),
        )
        health = assess(samples, args.require_ai)
        (output / "health.json").write_text(json.dumps(health, indent=2) + "\n")
        report.update({"url": url, "health": health})
        if health["decision"] != "keep":
            raise RuntimeError("Post-deployment health gates requested rollback")
        smoke(url)
        report["status"] = "healthy"
        print(f"Deployed and verified: {url}")
    except Exception as exc:
        report["failure_type"] = type(exc).__name__
        report["recovery"] = platform.recover()
        if platform.previous.get("idea-board-frontend") and platform.previous.get(
            "idea-board-backend"
        ):
            try:
                recovered = collect(platform.public_url(), 10, 0)
                report["recovery_health"] = recovered
                report["recovery_verified"] = recovered["failures"] == 0 and all(
                    "FAILED" not in result for result in report["recovery"].values()
                )
            except Exception:
                report["recovery_verified"] = False
        raise RuntimeError(
            f"Deployment failed ({type(exc).__name__}); recovery result saved in {output / 'deployment.json'}"
        ) from None
    finally:
        (output / "deployment.json").write_text(json.dumps(report, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cloud", choices=["aws", "gcp"], required=True)
    parser.add_argument(
        "--environment", choices=["staging", "production"], required=True
    )
    parser.add_argument("--frontend-image", required=True)
    parser.add_argument("--backend-image", required=True)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--context")
    parser.add_argument("--namespace")
    parser.add_argument("--pull-secret", default="")
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--require-ai", action="store_true")
    parser.add_argument("--render-only", action="store_true")
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/deployment")
    args = parser.parse_args()
    try:
        deploy(args)
    except (RuntimeError, ValueError, KeyError, OSError) as exc:
        parser.exit(1, f"{exc}\n")


if __name__ == "__main__":
    main()
