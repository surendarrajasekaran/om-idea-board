"""Select a cloud-native remote state backend without changing tracked Terraform."""

import argparse
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cloud", choices=["aws", "gcp"], required=True)
    parser.add_argument(
        "--environment", choices=["test", "staging", "production"], required=True
    )
    parser.add_argument("--bucket", required=True)
    parser.add_argument("--region", required=True)
    parser.add_argument(
        "--kms-key-id", default="", help="Optional S3 state KMS key ARN"
    )
    parser.add_argument(
        "--name", default="idea-board", help="Stack name; isolates remote state"
    )
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{1,220}[a-z0-9]", args.bucket):
        parser.error("Invalid state bucket name")
    if not re.fullmatch(r"[a-z0-9-]+", args.region):
        parser.error("Invalid region")
    if not re.fullmatch(r"[a-z][a-z0-9-]{2,20}", args.name):
        parser.error("Invalid stack name")
    if args.cloud == "aws":
        config = {
            "bucket": args.bucket,
            "key": f"{args.name}/{args.environment}/terraform.tfstate",
            "region": args.region,
            "encrypt": True,
            "use_lockfile": True,
        }
        if args.kms_key_id:
            if not re.fullmatch(
                r"arn:aws[a-z-]*:kms:[a-z0-9-]+:[0-9]{12}:(?:key|alias)/[A-Za-z0-9/_-]+",
                args.kms_key_id,
            ):
                parser.error("Supply a KMS key or alias ARN")
            config["kms_key_id"] = args.kms_key_id
        backend = "s3"
    else:
        config = {"bucket": args.bucket, "prefix": f"{args.name}/{args.environment}"}
        backend = "gcs"
    # JSON syntax is also valid inside HCL expressions, avoiding interpolation of code.
    fields = "\n".join(
        f"    {key} = {json.dumps(value)}" for key, value in config.items()
    )
    (ROOT / "infra/backend.tf").write_text(
        f'terraform {{\n  backend "{backend}" {{\n{fields}\n  }}\n}}\n'
    )
    subprocess.run(
        [
            "terraform",
            f"-chdir={ROOT / 'infra'}",
            "init",
            "-reconfigure",
            "-lockfile=readonly",
        ],
        check=True,
    )


if __name__ == "__main__":
    main()
