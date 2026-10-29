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
        "--environment", choices=["staging", "production"], required=True
    )
    parser.add_argument("--bucket", required=True)
    parser.add_argument("--region", required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{1,220}[a-z0-9]", args.bucket):
        parser.error("Invalid state bucket name")
    if not re.fullmatch(r"[a-z0-9-]+", args.region):
        parser.error("Invalid region")
    if args.cloud == "aws":
        config = {
            "bucket": args.bucket,
            "key": f"idea-board/{args.environment}/terraform.tfstate",
            "region": args.region,
            "encrypt": True,
            "use_lockfile": True,
        }
        backend = "s3"
    else:
        config = {"bucket": args.bucket, "prefix": f"idea-board/{args.environment}"}
        backend = "gcs"
    # JSON syntax is also valid inside HCL expressions, avoiding interpolation of code.
    fields = "\n".join(
        f"    {key} = {json.dumps(value)}" for key, value in config.items()
    )
    (ROOT / "infra/backend.tf").write_text(
        f'terraform {{\n  backend "{backend}" {{\n{fields}\n  }}\n}}\n'
    )
    subprocess.run(
        ["terraform", f"-chdir={ROOT / 'infra'}", "init", "-reconfigure"], check=True
    )


if __name__ == "__main__":
    main()
