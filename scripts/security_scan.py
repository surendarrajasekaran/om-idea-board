"""One digest-pinned, isolated scanner for CI and laptop image/IaC checks."""

import argparse
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SCANNER_IMAGE = "aquasec/trivy:0.76.1@sha256:790fd66d1697395d8693d1acaa1ea702406a20f109b6fc7bac8db623eca6c06c"


def _scan(kind, reference, scratch):
    command = [
        "docker",
        "run",
        "--rm",
        "--read-only",
        "--cap-drop=ALL",
        "--security-opt=no-new-privileges",
        f"--user={os.getuid()}:{os.getgid()}",
        "--tmpfs",
        "/tmp:rw,size=256m,mode=1777",
        "--mount",
        f"type=bind,src={scratch},dst=/work",
        "-e",
        "TMPDIR=/work",
        "-e",
        "HOME=/work",
        "--memory=2g",
        "--cpus=2",
        "--pids-limit=128",
    ]
    gate = ["--exit-code", "1", "--severity", "HIGH,CRITICAL"]
    if kind == "image":
        if not re.fullmatch(r"[a-z0-9][a-z0-9./_:-]*@sha256:[0-9a-f]{64}", reference):
            raise ValueError("Scan an immutable image digest")
        environment = {
            **os.environ,
            "TRIVY_USERNAME": os.environ.get(
                "TRIVY_USERNAME", os.environ.get("GHCR_USERNAME", "")
            ),
            "TRIVY_PASSWORD": os.environ.get(
                "TRIVY_PASSWORD",
                os.environ.get("GHCR_TOKEN")
                or os.environ.get("GHCR_PUBLISH_TOKEN", ""),
            ),
        }
        subprocess.run(
            command
            + [
                "-e",
                "TRIVY_USERNAME",
                "-e",
                "TRIVY_PASSWORD",
                SCANNER_IMAGE,
                "--cache-dir",
                "/work/cache",
                "image",
                "--platform",
                "linux/amd64",
                "--scanners",
                "vuln",
                "--ignore-unfixed",
                *gate,
                reference,
            ],
            env=environment,
            check=True,
            cwd=ROOT,
        )
    elif kind == "archive":
        archive = Path(reference).resolve()
        if not archive.is_file() or archive.suffix != ".tar":
            raise ValueError("Supply a docker-save .tar archive")
        subprocess.run(
            command
            + [
                "--mount",
                f"type=bind,src={archive},dst=/scan/image.tar,readonly",
                SCANNER_IMAGE,
                "--cache-dir",
                "/work/cache",
                "image",
                "--scanners",
                "vuln",
                "--ignore-unfixed",
                *gate,
                "--input",
                "/scan/image.tar",
            ],
            check=True,
            cwd=ROOT,
        )
    else:
        # Mount only reviewable source, excluding state, local variable files, credentials,
        # .git and dependency caches. GitOps charts live in a separate checkout.
        files = (
            subprocess.check_output(
                ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
                cwd=ROOT,
            )
            .decode()
            .split("\0")
        )
        with tempfile.TemporaryDirectory(prefix="platform-iac-scan-") as directory:
            snapshot = Path(directory)
            snapshot.chmod(0o755)
            for relative in files:
                source = ROOT / relative
                if not relative or not source.is_file() or source.is_symlink():
                    continue
                if source.name != "Dockerfile" and source.suffix not in {
                    ".tf",
                    ".yaml",
                    ".yml",
                }:
                    continue
                target = snapshot / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
                target.chmod(0o444)
            for folder in snapshot.rglob("*"):
                if folder.is_dir():
                    folder.chmod(0o755)
            (snapshot / ".trivyignore.yaml").chmod(0o444)
            for cloud, region in [("aws", "us-east-1"), ("gcp", "us-central1")]:
                import json

                variables = snapshot / "infra/scan.auto.tfvars.json"
                if variables.exists():
                    variables.chmod(0o644)
                variables.write_text(
                    json.dumps(
                        {
                            "cloud": cloud,
                            "region": region,
                            "gcp_project": "scan-project",
                            "admin_cidrs": ["203.0.113.10/32"],
                        }
                    )
                )
                variables.chmod(0o444)
                print(f"Scanning {cloud} configuration", flush=True)
                subprocess.run(
                    command
                    + [
                        "--mount",
                        f"type=bind,src={snapshot},dst=/workspace,readonly",
                        SCANNER_IMAGE,
                        "--cache-dir",
                        "/work/cache",
                        "config",
                        "--ignorefile",
                        "/workspace/.trivyignore.yaml",
                        "--tf-vars",
                        "/workspace/infra/scan.auto.tfvars.json",
                        *gate,
                        "/workspace",
                    ],
                    check=True,
                    cwd=ROOT,
                )


def scan(kind, reference=""):
    if os.getuid() == 0:
        raise ValueError("Run the scanner as an unprivileged host user")
    # The current vulnerability DB expands beyond 1 GiB. Keep it on disposable
    # disk rather than charging that footprint to the scanner's memory limit.
    with tempfile.TemporaryDirectory(prefix="platform-scanner-cache-") as scratch:
        # Match host/container ownership so Linux can remove private tool caches.
        Path(scratch).chmod(0o700)
        _scan(kind, reference, scratch)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=["image", "archive", "config"])
    parser.add_argument("reference", nargs="?", default="")
    args = parser.parse_args()
    try:
        scan(args.kind, args.reference)
    except (ValueError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f"Security scan failed ({type(exc).__name__})\n")


if __name__ == "__main__":
    main()
