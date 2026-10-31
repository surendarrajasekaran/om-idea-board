"""Full laptop/CI flow: initialize state, provision, publish images, deploy, verify."""

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

try:
    from .deploy import image_values, resource_values
except ImportError:
    from deploy import image_values, resource_values

ROOT = Path(__file__).resolve().parents[1]


def execute(command, **kwargs):
    subprocess.run(command, check=True, cwd=ROOT, **kwargs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cloud", choices=["aws", "gcp"], required=True)
    parser.add_argument(
        "--environment", choices=["test", "staging", "production"], default="staging"
    )
    parser.add_argument("--region", required=True)
    parser.add_argument("--name", default="idea-board")
    parser.add_argument(
        "--public-host", default="", help="DNS name covered by the TLS certificate"
    )
    parser.add_argument(
        "--tls-secret",
        default="",
        help="Existing TLS Secret for public HTTPS; required in production",
    )
    parser.add_argument("--state-bucket", required=True)
    parser.add_argument("--state-kms-key-id", default="")
    parser.add_argument(
        "--var-file",
        type=Path,
        help="Terraform variable file (required when provisioning)",
    )
    parser.add_argument(
        "--image-prefix", default="ghcr.io/surendarrajasekaran/om-idea-board"
    )
    parser.add_argument("--tag", help="Defaults to the current Git commit")
    parser.add_argument(
        "--goal", default="Cost-sensitive staging with reliable service"
    )
    parser.add_argument("--require-ai", action="store_true")
    parser.add_argument(
        "--skip-infra", action="store_true", help="Read an existing remote-state stack"
    )
    parser.add_argument("--skip-build", action="store_true", help="Use existing images")
    parser.add_argument(
        "--frontend-image", help="Existing full image reference, used with --skip-build"
    )
    parser.add_argument(
        "--backend-image", help="Existing full image reference, used with --skip-build"
    )
    parser.add_argument("--pull-secret", default="")
    parser.add_argument("--profile", type=Path, help="Reuse a prepared release profile")
    args = parser.parse_args()
    os.umask(0o077)
    tools = ["terraform", "helm", "kubectl", "aws" if args.cloud == "aws" else "gcloud"]
    if not args.skip_build:
        tools.append("docker")
    missing = [name for name in tools if not shutil.which(name)]
    if missing:
        parser.error("Install required tools: " + ", ".join(missing))
    if not args.skip_infra and not args.var_file:
        parser.error("--var-file is required when provisioning")
    if args.var_file and not args.var_file.is_file():
        parser.error("--var-file must reference an existing file")
    if not re.fullmatch(r"[a-z][a-z0-9-]{2,20}", args.name):
        parser.error("Invalid stack name")
    if args.environment == "production" and (
        not args.tls_secret or not args.public_host
    ):
        parser.error("Production requires --tls-secret and --public-host for HTTPS")
    if args.public_host and (
        not args.tls_secret
        or not re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]{0,251}[a-z0-9])?", args.public_host)
    ):
        parser.error("Supply a DNS hostname with TLS, without a URL scheme or path")
    if args.tls_secret and not re.fullmatch(
        r"[a-z0-9][a-z0-9.-]{0,251}[a-z0-9]", args.tls_secret
    ):
        parser.error("Invalid TLS Secret name")
    if not args.skip_build and (args.frontend_image or args.backend_image):
        parser.error("Explicit image references require --skip-build")
    if (
        os.environ.get("GHCR_TOKEN") or os.environ.get("GHCR_PUBLISH_TOKEN")
    ) and not os.environ.get("GHCR_USERNAME"):
        parser.error("GHCR_USERNAME is required with registry tokens")
    if not args.skip_build and not os.environ.get("GHCR_PUBLISH_TOKEN"):
        parser.error(
            "Set GHCR_PUBLISH_TOKEN for builds; GHCR_TOKEN is reserved for cluster read access"
        )
    for reference in (args.frontend_image, args.backend_image):
        if reference:
            image_values(reference)
    tag = (
        args.tag
        or subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip()
    )
    if not re.fullmatch(r"[a-zA-Z0-9_][a-zA-Z0-9_.-]{0,127}", tag) or tag == "latest":
        parser.error("Use an explicit release tag, not latest")
    if not re.fullmatch(r"[a-z0-9][a-z0-9./_-]+", args.image_prefix):
        parser.error("Invalid image prefix")
    suffix = (
        f"{args.cloud}-{args.environment}"
        if args.name == "idea-board"
        else f"{args.name}-{args.cloud}-{args.environment}"
    )
    output = ROOT / "artifacts" / suffix
    output.mkdir(parents=True, exist_ok=True)
    for filename in ("deployment.json", "health.json"):
        (output / filename).unlink(missing_ok=True)
    profile = args.profile.resolve() if args.profile else output / "profile.json"
    ai_flags = ["--require-ai"] if args.require_ai else []
    # Fail required AI/policy validation before incurring infrastructure charges.
    if not args.profile:
        execute(
            [
                sys.executable,
                "scripts/ai_ops.py",
                *ai_flags,
                "--output",
                str(profile),
                "plan",
                "--environment",
                args.environment,
                "--goal",
                args.goal,
            ]
        )
    prepared = json.loads(profile.read_text())
    resource_values(prepared, args.environment, args.cloud)
    if args.require_ai and prepared.get("source") != "live-ai":
        parser.error("A live AI profile is required")
    execute(
        [
            sys.executable,
            "scripts/infra_init.py",
            "--kms-key-id",
            args.state_kms_key_id,
            "--cloud",
            args.cloud,
            "--environment",
            args.environment,
            "--bucket",
            args.state_bucket,
            "--region",
            args.region,
            "--name",
            args.name,
        ]
    )
    if not args.skip_infra:
        plan_file = ROOT / "infra/release.tfplan"
        try:
            execute(
                [
                    "terraform",
                    "-chdir=infra",
                    "plan",
                    f"-var-file={args.var_file.resolve()}",
                    f"-var=cloud={args.cloud}",
                    f"-var=environment={args.environment}",
                    f"-var=region={args.region}",
                    f"-var=name={args.name}",
                    "-out=release.tfplan",
                ]
            )
            execute(["terraform", "-chdir=infra", "apply", "release.tfplan"])
        finally:
            plan_file.unlink(missing_ok=True)
    # Capture outputs; database credentials are never printed to the console.
    outputs = json.loads(
        subprocess.check_output(
            ["terraform", "-chdir=infra", "output", "-json"], cwd=ROOT, text=True
        )
    )
    for key, expected in [
        ("cloud", args.cloud),
        ("environment", args.environment),
        ("region", args.region),
        ("name", args.name),
    ]:
        if outputs[key]["value"] != expected:
            raise ValueError(f"Terraform {key} does not match requested target")
    images = {
        component: getattr(args, f"{component}_image")
        or f"{args.image_prefix}/{component}:{tag}"
        for component in ("frontend", "backend")
    }
    if not args.skip_build:
        if os.environ.get("GHCR_PUBLISH_TOKEN"):
            username = os.environ["GHCR_USERNAME"]
            execute(
                [
                    "docker",
                    "login",
                    "ghcr.io",
                    "--username",
                    username,
                    "--password-stdin",
                ],
                input=os.environ["GHCR_PUBLISH_TOKEN"],
                text=True,
                stdout=subprocess.DEVNULL,
            )
        for component, image in images.items():
            metadata = output / f"{component}-build.json"
            execute(
                [
                    "docker",
                    "buildx",
                    "build",
                    "--platform",
                    "linux/amd64",
                    "--push",
                    "--provenance=mode=max",
                    "--sbom=true",
                    "--metadata-file",
                    str(metadata),
                    "--tag",
                    image,
                    str(ROOT / component),
                ]
            )
            digest = json.loads(metadata.read_text())["containerimage.digest"]
            images[component] = image + "@" + digest
            execute(
                [sys.executable, "scripts/security_scan.py", "image", images[component]]
            )
    # Keep kubeconfig scoped to this run; never change the user's default context.
    with tempfile.TemporaryDirectory(prefix="idea-board-kube-") as directory:
        env = {**os.environ, "KUBECONFIG": str(Path(directory) / "config")}
        cluster = outputs["cluster_name"]["value"]
        if args.cloud == "aws":
            execute(
                [
                    "aws",
                    "eks",
                    "update-kubeconfig",
                    "--region",
                    args.region,
                    "--name",
                    cluster,
                    "--alias",
                    f"{args.name}-aws-{args.environment}",
                ],
                env=env,
                stdout=subprocess.DEVNULL,
            )
        else:
            execute(
                [
                    "gcloud",
                    "container",
                    "clusters",
                    "get-credentials",
                    cluster,
                    "--region",
                    args.region,
                    "--project",
                    outputs["gcp_project"]["value"],
                ],
                env=env,
                stdout=subprocess.DEVNULL,
            )
        context = subprocess.check_output(
            ["kubectl", "config", "current-context"], env=env, text=True
        ).strip()
        execute(
            [
                sys.executable,
                "scripts/deploy.py",
                "--cloud",
                args.cloud,
                "--name",
                args.name,
                "--tls-secret",
                args.tls_secret,
                "--public-host",
                args.public_host,
                "--environment",
                args.environment,
                "--context",
                context,
                "--profile",
                str(profile),
                "--frontend-image",
                images["frontend"],
                "--backend-image",
                images["backend"],
                "--pull-secret",
                args.pull_secret,
                "--output",
                str(output),
                *ai_flags,
            ],
            env=env,
        )
    print(f"Full flow completed. Evidence: {output / 'deployment.json'}")


if __name__ == "__main__":
    try:
        with tempfile.TemporaryDirectory(prefix="idea-board-docker-") as docker_config:
            original_config = Path(
                os.environ.get("DOCKER_CONFIG", str(Path.home() / ".docker"))
            )
            # Preserve the selected daemon and builder, but never its credential helpers/auths.
            config_file = original_config / "config.json"
            config = (
                json.loads(config_file.read_text()) if config_file.is_file() else {}
            )
            config = {
                key: value
                for key, value in config.items()
                if key not in {"auths", "credsStore", "credHelpers"}
            }
            (Path(docker_config) / "config.json").write_text(json.dumps(config))
            for folder in ("buildx", "contexts"):
                if (original_config / folder).exists():
                    (Path(docker_config) / folder).symlink_to(
                        original_config / folder, target_is_directory=True
                    )
            os.environ["DOCKER_CONFIG"] = docker_config
            main()
    except (subprocess.CalledProcessError, ValueError, OSError) as exc:
        print(
            f"Platform flow failed ({type(exc).__name__}); no success claimed.",
            file=sys.stderr,
        )
        sys.exit(1)
