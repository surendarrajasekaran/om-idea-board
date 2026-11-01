"""One-time private-cluster bootstrap: Secrets and Argo CD, never a Helm app rollout."""

import argparse
import json
from pathlib import Path
import subprocess

try:
    from .deploy import Deployment, ROOT, database_certificate, run
    from .workload_policy import namespace_resources
except ImportError:
    from deploy import Deployment, ROOT, database_certificate, run
    from workload_policy import namespace_resources


def bootstrap(args):
    outputs = json.loads(
        run(["terraform", f"-chdir={ROOT / 'infra'}", "output", "-json"]).stdout
    )
    for key, expected in [
        ("cloud", "aws"),
        ("name", args.name),
        ("environment", args.environment),
        ("region", args.region),
    ]:
        if outputs[key]["value"] != expected:
            raise ValueError("Terraform target differs from requested bootstrap")
    identity = json.loads(run(["aws", "sts", "get-caller-identity"]).stdout)
    if identity["Account"] != args.account_id:
        raise ValueError("Wrong AWS account")
    cluster = json.loads(
        run(
            [
                "aws",
                "eks",
                "describe-cluster",
                "--region",
                args.region,
                "--name",
                outputs["cluster_name"]["value"],
            ]
        ).stdout
    )["cluster"]
    config = json.loads(
        run(
            [
                "kubectl",
                "--context",
                args.context,
                "config",
                "view",
                "--raw",
                "--minify",
                "-o",
                "json",
            ]
        ).stdout
    )
    if (
        config["clusters"][0]["cluster"].get("certificate-authority-data")
        != cluster["certificateAuthority"]["data"]
    ):
        raise ValueError("Kubernetes context does not match the Terraform cluster CA")
    namespace = f"{args.name}-{args.environment}"
    platform = Deployment(namespace, args.context, name=args.name)
    controls = namespace_resources(
        namespace, args.name, outputs["database_egress_cidrs"]["value"]
    )
    run(
        ["kubectl", "--context", args.context, "apply", "-f", "-"],
        data=json.dumps(controls),
    )
    platform.apply_secret(
        f"{args.name}-database-ca", {"ca.crt": database_certificate("aws", outputs)}
    )
    platform.apply_secret(
        f"{args.name}-database", {"DATABASE_URL": outputs["database_url"]["value"]}
    )
    platform.apply_secret(
        f"{args.name}-migration",
        {
            "DATABASE_URL": outputs["migration_database_url"]["value"],
            "APP_DATABASE_USER": "ideas_app",
            "APP_DATABASE_PASSWORD": outputs["application_password"]["value"],
        },
    )
    run(
        [
            "helm",
            "upgrade",
            "--install",
            "argocd",
            str(args.chart),
            "--namespace",
            "argocd",
            "--create-namespace",
            "--kube-context",
            args.context,
            "--atomic",
            "--wait",
            "--timeout",
            "900s",
            "-f",
            str(ROOT / "deploy/argocd/test-values.yaml"),
        ]
    )
    run(
        [
            "kubectl",
            "--context",
            args.context,
            "apply",
            "-f",
            str(args.argocd_manifests),
        ]
    )
    print(f"Argo CD bootstrapped; Git owns application desired state in {namespace}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--context", required=True)
    parser.add_argument("--account-id", required=True)
    parser.add_argument("--region", required=True)
    parser.add_argument("--name", default="idea-board")
    parser.add_argument("--environment", choices=["test", "staging"], default="test")
    parser.add_argument("--chart", type=Path, required=True)
    parser.add_argument("--argocd-manifests", type=Path, required=True)
    args = parser.parse_args()
    try:
        bootstrap(args)
    except (
        RuntimeError,
        ValueError,
        KeyError,
        OSError,
        subprocess.CalledProcessError,
    ) as exc:
        reason = (
            str(exc)
            if isinstance(exc, (RuntimeError, ValueError))
            else type(exc).__name__
        )
        parser.exit(1, f"GitOps bootstrap failed: {reason}; no success claimed\n")


if __name__ == "__main__":
    main()
