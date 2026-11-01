"""Render the existing chart into a single atomic Argo CD GitOps release."""

import argparse
import json
from pathlib import Path
import tempfile

import yaml

try:
    from .deploy import deploy
    from .gitops_state import (
        VALUE_FILES,
        current,
        helm_manifests,
        identifier,
        merge_values,
        save_release,
    )
except ImportError:
    from deploy import deploy
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
    with tempfile.TemporaryDirectory(prefix="idea-board-gitops-") as directory:
        rendered = Path(directory)
        config = argparse.Namespace(
            name=args.name,
            cloud=args.cloud,
            environment=args.environment,
            profile=args.profile,
            frontend_image=args.frontend_image,
            backend_image=args.backend_image,
            tls_secret=args.tls_secret,
            public_host=args.public_host,
            output=rendered,
            require_ai=args.require_ai,
            pull_secret="",
            namespace=None,
            render_only=True,
            database_egress_cidr=args.database_egress_cidr,
        )
        deploy(config, gitops_dir=args.gitops_dir)
        values = {}
        for component in ("backend", "frontend"):
            data = merge_values(
                yaml.safe_load((args.gitops_dir / VALUE_FILES[component]).read_text()),
                json.loads((rendered / f"{component}-values.json").read_text()),
            )
            if component == "frontend":
                data = merge_values(
                    data,
                    yaml.safe_load(
                        (
                            Path(__file__).resolve().parents[1]
                            / f"deploy/clouds/{args.cloud}.yaml"
                        ).read_text()
                    ),
                )
            data.setdefault("commonAnnotations", {})["argocd.argoproj.io/sync-wave"] = (
                "0" if component == "backend" else "10"
            )
            data.setdefault("podAnnotations", {})["idea-board/gitops-release"] = (
                args.release_id
            )
            data.setdefault("env", {})["RELEASE_ID"] = args.release_id
            values[component] = data
        manifests = helm_manifests(
            args.gitops_dir, values, args.name, f"{args.name}-{args.environment}"
        )
        controls = yaml.safe_load((rendered / "namespace-rendered.yaml").read_text())[
            "items"
        ]
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
            "profile": json.loads(args.profile.read_text()),
            "public_url": args.public_url
            or (current(args.gitops_dir, args.target) or {}).get("public_url", ""),
        }
        save_release(
            args.gitops_dir, args.target, metadata, manifests, helm_values=values
        )
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
