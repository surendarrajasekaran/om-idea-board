"""Deploy two releases of the supplied nucleus chart; verify and recover on failure."""

import argparse
import copy
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import ssl
import subprocess
import tempfile
import time
import urllib.request

import yaml

try:
    from .ai_ops import PROFILE_SCHEMA, assess, validate_schema
    from .probe import collect
    from .smoke import smoke
    from .workload_policy import namespace_resources
except ImportError:
    from ai_ops import PROFILE_SCHEMA, assess, validate_schema
    from probe import collect
    from smoke import smoke
    from workload_policy import namespace_resources

ROOT = Path(__file__).resolve().parents[1]
CHART = ROOT / "helm-common/nucleus"
VALUES = {
    "frontend": ROOT / "helm-overides/idea-fe/custom-values.yaml",
    "backend": ROOT / "helm-overides/idea-be/custom-values.yaml",
}
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
    if environment == "test" and (
        values["replicas"] != 1 or values["cpu_request"] == "500m"
    ):
        raise ValueError(
            "Single-worker test policy requires one replica and at most 250m CPU per component"
        )
    cpu, memory = values["cpu_request"], values["memory_request"]
    # Portable minimums accommodate GKE Autopilot general-purpose pods.
    if cloud == "gcp":
        cpu = "250m" if cpu == "100m" else cpu
        memory = "256Mi" if memory == "128Mi" else memory
        if cpu == "500m" and memory == "256Mi":
            memory = "512Mi"  # Autopilot requires >=1 GiB requested memory per vCPU.
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


def database_certificate(cloud, outputs):
    if cloud == "aws":
        # Public trust material only: fixed official HTTPS URL, no provider credentials.
        with urllib.request.urlopen(
            "https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem",
            timeout=15,
        ) as response:
            certificate = response.read(262144).decode("ascii")
    else:
        certificate = outputs["database_ca_certificate"]["value"]
    ssl.create_default_context().load_verify_locations(cadata=certificate)
    return certificate


class Deployment:
    def __init__(
        self,
        namespace,
        context,
        timeout=600,
        name="idea-board",
        tls=False,
        public_host="",
    ):
        if not re.fullmatch(r"[a-z][a-z0-9-]{0,61}[a-z0-9]", namespace):
            raise ValueError("Invalid namespace")
        self.namespace, self.context, self.timeout = namespace, context, timeout
        self.name, self.tls, self.public_host = name, tls, public_host
        self.releases = [f"{name}-backend", f"{name}-frontend"]
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
        for release in self.releases:
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
            str(VALUES[component]),
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
            if pod["metadata"]["labels"].get("app.kubernetes.io/instance")
            in self.releases
            for container in pod.get("status", {}).get("containerStatuses", [])
        }

    def public_url(self):
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            service = json.loads(
                self.kube(
                    "get", "service", f"{self.name}-frontend", "-o", "json"
                ).stdout
            )
            for address in (
                service.get("status", {}).get("loadBalancer", {}).get("ingress", [])
            ):
                host = address.get("hostname") or address.get("ip")
                if host:
                    if ":" in host:
                        host = f"[{host}]"
                    # Recovery may restore a different Service protocol/hostname.
                    tls = any(port["port"] == 443 for port in service["spec"]["ports"])
                    public_host = (
                        service.get("metadata", {})
                        .get("annotations", {})
                        .get("idea-board/public-host", self.public_host)
                        if tls
                        else ""
                    )
                    if public_host:
                        print(
                            f"Load balancer: {host}; DNS for {public_host} must point here",
                            flush=True,
                        )
                    return f"{'https' if tls else 'http'}://{public_host or host}"
            time.sleep(5)
        raise RuntimeError("Timed out waiting for the public load balancer")


def deploy(args):
    chart = CHART
    os.umask(0o077)
    name = getattr(args, "name", "idea-board")
    tls_secret = getattr(args, "tls_secret", "")
    public_host = getattr(args, "public_host", "")
    if not re.fullmatch(r"[a-z][a-z0-9-]{2,20}", name):
        raise ValueError("Invalid stack name")
    if args.environment == "production" and (not tls_secret or not public_host):
        raise ValueError(
            "Production requires --tls-secret and --public-host for verified HTTPS"
        )
    if tls_secret and not re.fullmatch(
        r"[a-z0-9][a-z0-9.-]{0,251}[a-z0-9]", tls_secret
    ):
        raise ValueError("Invalid TLS Secret name")
    if public_host and (
        not tls_secret
        or not re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]{0,251}[a-z0-9])?", public_host)
    ):
        raise ValueError("Supply a DNS hostname with TLS, without a URL scheme or path")
    args.output.mkdir(parents=True, exist_ok=True)
    for filename in ("deployment.json", "health.json"):
        (args.output / filename).unlink(missing_ok=True)
    profile = json.loads(args.profile.read_text())
    if args.require_ai and profile.get("source") != "live-ai":
        raise ValueError("A live AI profile is required")
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
    for component, values in settings.items():
        values["fullnameOverride"] = f"{name}-{component}"
        if component == "backend":
            values["volumes"] = [
                {
                    "name": "database-ca",
                    "secret": {"secretName": f"{name}-database-ca", "defaultMode": 292},
                }
            ]
            values["envFrom"] = [{"secretRef": {"name": f"{name}-database"}}]
            # Helm evaluates this existing init container value through tpl.
            values["initContainers"] = copy.deepcopy(
                yaml.safe_load(VALUES["backend"].read_text())["initContainers"]
            )
            values["initContainers"][0]["envFrom"] = [
                {"secretRef": {"name": f"{name}-migration"}}
            ]
        else:
            values["env"] = {"BACKEND_HOST": f"{name}-backend"}
            values["service"] = {"annotations": {"idea-board/public-host": public_host}}
            if tls_secret:
                base = yaml.safe_load(VALUES["frontend"].read_text())
                values["env"]["TLS_LISTEN"] = (
                    "listen 8443 ssl; ssl_certificate /etc/nginx/tls/tls.crt; ssl_certificate_key /etc/nginx/tls/tls.key;"
                )
                values["volumes"] = base["volumes"] + [
                    {
                        "name": "tls",
                        "secret": {"secretName": tls_secret, "defaultMode": 292},
                    }
                ]
                values["volumeMounts"] = base["volumeMounts"] + [
                    {"name": "tls", "mountPath": "/etc/nginx/tls", "readOnly": True}
                ]
                values["service"] = {
                    "annotations": {"idea-board/public-host": public_host},
                    "port": 443,
                    "ports": [
                        {
                            "name": "https",
                            "port": 443,
                            "targetPort": 8443,
                            "protocol": "TCP",
                        }
                    ],
                }
        values["topologySpreadConstraints"] = [
            {
                "maxSkew": 1,
                "topologyKey": "kubernetes.io/hostname",
                "whenUnsatisfiable": "DoNotSchedule"
                if args.environment == "production"
                else "ScheduleAnyway",
                "labelSelector": {
                    "matchLabels": {"app.kubernetes.io/instance": f"{name}-{component}"}
                },
            }
        ]
    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    if args.render_only:
        cidrs = getattr(args, "database_egress_cidr", [])
        for component, values in settings.items():
            file = output / f"{component}-values.json"
            file.write_text(json.dumps(values, indent=2) + "\n")
            command = [
                "helm",
                "template",
                f"{name}-{component}",
                str(chart),
                "-f",
                str(VALUES[component]),
            ]
            if component == "frontend":
                command += ["-f", str(ROOT / f"deploy/clouds/{args.cloud}.yaml")]
            rendered = run(command + ["-f", str(file)]).stdout
            list(yaml.safe_load_all(rendered))
            (output / f"{component}-rendered.yaml").write_text(rendered)
        controls = namespace_resources(
            args.namespace or f"{name}-{args.environment}", name, cidrs
        )
        (output / "namespace-rendered.yaml").write_text(yaml.safe_dump(controls))
        print(
            f"Rendered and parsed both common-chart releases and namespace controls in {output}"
        )
        return
    if not args.context:
        raise ValueError(
            "--context is required; an implicit current cluster is never used"
        )
    platform = Deployment(
        args.namespace or f"{name}-{args.environment}",
        args.context,
        args.timeout,
        name=name,
        tls=bool(tls_secret),
        public_host=public_host,
    )
    # Verify the output belongs to the requested cloud/environment, not another initialized state.
    outputs = json.loads(
        run(["terraform", f"-chdir={ROOT / 'infra'}", "output", "-json"]).stdout
    )
    for key, expected in [
        ("cloud", args.cloud),
        ("environment", args.environment),
        ("name", name),
    ]:
        if outputs[key]["value"] != expected:
            raise ValueError(f"Terraform {key} does not match requested target")
    db_url = outputs["database_url"]["value"]
    if not db_url.startswith("postgresql+psycopg://"):
        raise ValueError("Invalid Terraform database URL")
    migration_url = outputs["migration_database_url"]["value"]
    application_password = outputs["application_password"]["value"]
    if not migration_url.startswith("postgresql+psycopg://") or migration_url == db_url:
        raise ValueError("Separate migration credentials are required")
    certificate = database_certificate(args.cloud, outputs)
    namespace = namespace_resources(
        platform.namespace, name, outputs["database_egress_cidrs"]["value"]
    )
    run(
        ["kubectl", "--context", args.context, "apply", "-f", "-"],
        data=json.dumps(namespace),
    )
    platform.snapshot()
    if tls_secret:
        secret = json.loads(
            platform.kube("get", "secret", tls_secret, "-o", "json").stdout
        )
        if (
            secret.get("type") != "kubernetes.io/tls"
            or not {"tls.crt", "tls.key"} <= secret.get("data", {}).keys()
        ):
            raise ValueError("TLS Secret must contain a certificate and key")
        settings["frontend"]["podAnnotations"]["idea-board/tls-version"] = (
            hashlib.sha256(
                base64.b64decode(secret["data"]["tls.crt"], validate=True)
            ).hexdigest()
        )
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
        platform.apply_secret(f"{name}-database-ca", {"ca.crt": certificate})
        platform.apply_secret(f"{name}-database", {"DATABASE_URL": db_url})
        platform.apply_secret(
            f"{name}-migration",
            {
                "DATABASE_URL": migration_url,
                "APP_DATABASE_USER": "ideas_app",
                "APP_DATABASE_PASSWORD": application_password,
            },
        )
        settings["backend"]["podAnnotations"]["idea-board/database-version"] = (
            hashlib.sha256((db_url + migration_url + certificate).encode()).hexdigest()
        )
        token = os.environ.get("GHCR_TOKEN")
        if token:
            username = os.environ.get("GHCR_USERNAME")
            if not username:
                raise ValueError("GHCR_USERNAME is required with GHCR_TOKEN")
            auth = base64.b64encode(f"{username}:{token}".encode()).decode()
            config = json.dumps({"auths": {"ghcr.io": {"auth": auth}}})
            platform.apply_secret(
                args.pull_secret or f"{name}-registry",
                {".dockerconfigjson": config},
                "kubernetes.io/dockerconfigjson",
            )
            for component in settings:
                settings[component]["image"]["pullSecrets"] = [
                    {"name": args.pull_secret or f"{name}-registry"}
                ]
        baseline = platform.restart_counts()
        with tempfile.TemporaryDirectory(prefix="idea-board-values-") as directory:
            for component in ("backend", "frontend"):
                values_file = Path(directory) / f"{component}.json"
                values_file.write_text(json.dumps(settings[component]))
                platform.upgrade(
                    f"{name}-{component}", component, values_file, args.cloud
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
        if platform.previous.get(f"{name}-frontend") and platform.previous.get(
            f"{name}-backend"
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
        "--environment", choices=["test", "staging", "production"], required=True
    )
    parser.add_argument("--frontend-image", required=True)
    parser.add_argument("--backend-image", required=True)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--context")
    parser.add_argument("--namespace")
    parser.add_argument("--name", default="idea-board")
    parser.add_argument("--tls-secret", default="")
    parser.add_argument("--public-host", default="")
    parser.add_argument("--pull-secret", default="")
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--require-ai", action="store_true")
    parser.add_argument("--render-only", action="store_true")
    parser.add_argument(
        "--database-egress-cidr",
        action="append",
        default=[],
        help="Private DB range for render-only; repeat for multiple subnets",
    )
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/deployment")
    args = parser.parse_args()
    try:
        deploy(args)
    except (RuntimeError, ValueError, KeyError, OSError) as exc:
        parser.exit(1, f"{exc}\n")


if __name__ == "__main__":
    main()
