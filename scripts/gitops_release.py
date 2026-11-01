"""Render the existing chart into a single atomic Argo CD GitOps release."""

import argparse
import json
from pathlib import Path

import yaml

try:
    from .release_config import image_values, resource_values
    from .workload_policy import namespace_resources
    from .gitops_state import (
        VALUE_FILES,
        current,
        helm_manifests,
        identifier,
        merge_values,
        save_release,
    )
except ImportError:
    from release_config import image_values, resource_values
    from workload_policy import namespace_resources
    from gitops_state import (
        VALUE_FILES,
        current,
        helm_manifests,
        identifier,
        merge_values,
        save_release,
    )


def publish(args):
    identifier(args.target)
    identifier(args.release_id)
    profile = json.loads(args.profile.read_text())
    if args.require_ai and profile.get("source") != "live-ai":
        raise ValueError("A live AI resource profile is required")
    if args.tls_secret or args.public_host:
        raise ValueError("Configure TLS and public host in the GitOps component values")
    resources = resource_values(profile, args.environment, args.cloud)
    values = {}
    for component, file in VALUE_FILES.items():
        data = yaml.safe_load((args.gitops_dir / file).read_text())
        if data.get("fullnameOverride") != f"{args.name}-{component}":
            raise ValueError("GitOps component names do not match the requested target")
        image = image_values(getattr(args, f"{component}_image"))
        # Image coordinates, bounded resources and release identity are CI-owned.
        # Preserve all other current GitOps settings, including rotated Secret/CA refs.
        data = merge_values(
            data,
            {
                **resources,
                "image": {
                    "repository": image["repository"],
                    "tag": image["tag"],
                },
            },
        )
        data.setdefault("commonAnnotations", {})["argocd.argoproj.io/sync-wave"] = (
            "0" if component == "backend" else "10"
        )
        data.setdefault("podAnnotations", {}).update(
            {
                "idea-board/release-image": getattr(args, f"{component}_image"),
                "idea-board/gitops-release": args.release_id,
            }
        )
        data.setdefault("env", {})["RELEASE_ID"] = args.release_id
        values[component] = data
    manifests = helm_manifests(
        args.gitops_dir, values, args.name, f"{args.name}-{args.environment}"
    )
    controls = namespace_resources(
        f"{args.name}-{args.environment}", args.name, args.database_egress_cidr
    )["items"]
    controls = [item for item in controls if item["kind"] != "Namespace"]
    for item in controls:
        item["metadata"].setdefault("annotations", {})[
            "argocd.argoproj.io/sync-wave"
        ] = "-10"
    manifests["controls.yaml"] = yaml.safe_dump_all(controls, sort_keys=False)
    metadata = {
        "id": args.release_id,
        "name": args.name,
        "cloud": args.cloud,
        "environment": args.environment,
        "source_commit": args.source_commit,
        "images": {"frontend": args.frontend_image, "backend": args.backend_image},
        "profile": profile,
        "public_url": args.public_url
        or (current(args.gitops_dir, args.target) or {}).get("public_url", ""),
    }
    save_release(args.gitops_dir, args.target, metadata, manifests, helm_values=values)
    print(f"Prepared immutable GitOps release {args.release_id} for {args.target}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gitops-dir", type=Path, required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--release-id", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--name", default="idea-board")
    parser.add_argument("--cloud", choices=["aws", "gcp"], default="aws")
    parser.add_argument(
        "--environment", choices=["test", "staging", "production"], required=True
    )
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--frontend-image", required=True)
    parser.add_argument("--backend-image", required=True)
    parser.add_argument("--database-egress-cidr", action="append", default=[])
    parser.add_argument("--tls-secret", default="")
    parser.add_argument("--public-host", default="")
    parser.add_argument("--public-url", default="")
    parser.add_argument("--require-ai", action="store_true")
    publish(parser.parse_args())


if __name__ == "__main__":
    main()
