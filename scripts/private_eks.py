"""Reach a private EKS API through an SSM-managed worker; no public API or SSH."""

import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import time
from urllib.parse import urlparse

import yaml


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--region", required=True)
    parser.add_argument("--cluster", required=True)
    parser.add_argument("--kubeconfig", type=Path, required=True)
    parser.add_argument("--port", type=int, default=9443)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("Use an unprivileged local port")
    env = {**os.environ, "AWS_PROFILE": args.profile, "AWS_REGION": args.region}
    aws = ["aws", "--profile", args.profile, "--region", args.region]

    def query(command):
        return json.loads(
            subprocess.check_output(
                aws + command + ["--output", "json"], env=env, text=True
            )
        )

    cluster = query(["eks", "describe-cluster", "--name", args.cluster])["cluster"]
    instances = query(
        [
            "ec2",
            "describe-instances",
            "--filters",
            f"Name=tag:eks:cluster-name,Values={args.cluster}",
            "Name=instance-state-name,Values=running",
        ]
    )
    candidates = [
        item["InstanceId"]
        for reservation in instances["Reservations"]
        for item in reservation["Instances"]
    ]
    if not candidates:
        parser.error("No running worker is available for private API access")
    managed = query(
        [
            "ssm",
            "describe-instance-information",
            "--filters",
            "Key=InstanceIds,Values=" + ",".join(candidates),
        ]
    )["InstanceInformationList"]
    target = next(
        (item["InstanceId"] for item in managed if item["PingStatus"] == "Online"), None
    )
    if not target:
        parser.error(
            "Workers are not online in SSM; check the optional SSM role and private egress"
        )
    args.kubeconfig.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        aws
        + [
            "eks",
            "update-kubeconfig",
            "--name",
            args.cluster,
            "--alias",
            args.cluster,
            "--kubeconfig",
            str(args.kubeconfig),
        ],
        env=env,
        check=True,
        stdout=subprocess.DEVNULL,
    )
    config = yaml.safe_load(args.kubeconfig.read_text())
    hostname = urlparse(cluster["endpoint"]).hostname
    for item in config["clusters"]:
        if item["cluster"]["server"] == cluster["endpoint"]:
            item["cluster"]["server"] = f"https://127.0.0.1:{args.port}"
            item["cluster"]["tls-server-name"] = hostname
    args.kubeconfig.write_text(yaml.safe_dump(config))
    args.kubeconfig.chmod(0o600)
    parameters = json.dumps(
        {"host": [hostname], "portNumber": ["443"], "localPortNumber": [str(args.port)]}
    )
    process = subprocess.Popen(
        aws
        + [
            "ssm",
            "start-session",
            "--target",
            target,
            "--document-name",
            "AWS-StartPortForwardingSessionToRemoteHost",
            "--parameters",
            parameters,
        ],
        env=env,
    )
    try:
        for _ in range(60):
            if process.poll() is not None:
                raise RuntimeError("SSM tunnel exited before becoming ready")
            try:
                with socket.create_connection(("127.0.0.1", args.port), timeout=1):
                    print(
                        f"Private API ready. KUBECONFIG={args.kubeconfig}; context={args.cluster}",
                        flush=True,
                    )
                    break
            except OSError:
                time.sleep(1)
        else:
            raise RuntimeError("Timed out waiting for SSM forwarding")
        raise SystemExit(process.wait())
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=10)


if __name__ == "__main__":
    main()
