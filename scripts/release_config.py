"""Validated image/resource values and the reviewed external GitOps chart paths."""

import os
from pathlib import Path
import re

try:
    from .ai_ops import PROFILE_SCHEMA, validate_schema
except ImportError:
    from ai_ops import PROFILE_SCHEMA, validate_schema

ROOT = Path(__file__).resolve().parents[1]
GITOPS_ROOT = Path(
    os.environ.get("GITOPS_DIR", ROOT.parent / "infra-helm-charts")
).resolve()
CHART = GITOPS_ROOT / "helm-templates/nucleus"
VALUES = {
    "frontend": GITOPS_ROOT / "helm-overides/idea-fe/custom-values.yaml",
    "backend": GITOPS_ROOT / "helm-overides/idea-be/custom-values.yaml",
}


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
