"""Validated GitOps release history and runtime-profile, compare-and-swap recovery."""

import hashlib
import json
from pathlib import Path
import re
import time

import yaml

FILES = ("backend.yaml", "frontend.yaml", "controls.yaml")


def identifier(value):
    if (
        not isinstance(value, str)
        or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,119}", value)
        or ".." in value
    ):
        raise ValueError("Invalid release/target identifier")
    return value


def read_json(path, default=None):
    return json.loads(path.read_text()) if path.exists() else default


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def current(root, target):
    return read_json(Path(root) / "environments" / identifier(target) / "release.json")


def save_release(root, target, metadata, manifests, expected=None):
    root, target = Path(root), identifier(target)
    release_id = identifier(metadata["id"])
    if set(manifests) != set(FILES):
        raise ValueError("Expected exactly the approved manifest files")
    for value in metadata["images"].values():
        if not re.fullmatch(r"[a-z0-9][a-z0-9./_:-]*@sha256:[0-9a-f]{64}", value):
            raise ValueError("GitOps requires immutable image digests")
    before = current(root, target)
    if expected is not None and (before or {}).get("id") != expected:
        raise ValueError("Stale release: a newer deployment was published")
    archive = root / "releases" / target / release_id
    if archive.exists():
        raise ValueError("Release snapshots are immutable; use a new release ID")
    metadata = {
        **metadata,
        "target": target,
        "hashes": {
            file: hashlib.sha256(content.encode()).hexdigest()
            for file, content in manifests.items()
        },
    }
    for content in manifests.values():
        for document in yaml.safe_load_all(content):
            pending = [document] if document else []
            while pending:
                item = pending.pop()
                if item.get("kind") == "Secret":
                    raise ValueError("Secrets must never be committed to GitOps")
                if item.get("kind") == "List":
                    pending.extend(item.get("items", []))
    destination = root / "environments" / target
    managed = destination / "manifests"
    if managed.exists() and any(file.name not in FILES for file in managed.iterdir()):
        raise ValueError("Refuse to replace unmanaged files in the manifests directory")
    archive.mkdir(parents=True)
    for file, content in manifests.items():
        (archive / file).write_text(content)
    write_json(archive / "release.json", metadata)
    managed.mkdir(parents=True, exist_ok=True)
    for file, content in manifests.items():
        (managed / file).write_text(content)
    write_json(destination / "release.json", metadata)
    return metadata


def verified_snapshot(root, target, release_id):
    archive = Path(root) / "releases" / identifier(target) / identifier(release_id)
    metadata = read_json(archive / "release.json")
    if not metadata or metadata["id"] != release_id or metadata["target"] != target:
        raise ValueError("Missing or mismatched recovery snapshot")
    for file in FILES:
        if (
            hashlib.sha256((archive / file).read_bytes()).hexdigest()
            != metadata["hashes"][file]
        ):
            raise ValueError("Recovery snapshot checksum mismatch")
    return metadata


def mark_healthy(root, target, expected):
    metadata = current(root, target)
    if not metadata or metadata["id"] != expected:
        raise ValueError("Stale health report")
    status_path = Path(root) / "environments" / target / "status.json"
    status = read_json(status_path, {"healthy_releases": []})
    if (
        status["healthy_releases"]
        and status["healthy_releases"][0] == expected
        and not status.get("rollback_pending")
    ):
        return False
    verified_snapshot(root, target, expected)
    status["healthy_releases"] = [
        expected,
        *[item for item in status["healthy_releases"] if item != expected],
    ][:5]
    status["rollback_pending"] = False
    write_json(status_path, status)
    return True


def recover_images(root, target, expected):
    metadata = current(root, target)
    if not metadata or metadata["id"] != expected:
        raise ValueError("Stale rollback: release has changed")
    destination = Path(root) / "environments" / target
    status = read_json(destination / "status.json", {"healthy_releases": []})
    if status.get("rollback_pending"):
        raise ValueError("Recovery is already pending; operator action is required")
    candidates = [item for item in status["healthy_releases"] if item != expected]
    if not candidates:
        raise ValueError("No previously verified healthy release is available")
    previous = verified_snapshot(root, target, candidates[0])
    replacement_id = f"recovery-{time.time_ns()}"
    manifests = {file: (destination / "manifests" / file).read_text() for file in FILES}
    for component in ("backend", "frontend"):
        archive = Path(root) / "releases" / target / previous["id"]
        prior_documents = [
            item
            for item in yaml.safe_load_all((archive / f"{component}.yaml").read_text())
            if item
        ]
        prior_deployments = [
            item for item in prior_documents if item.get("kind") == "Deployment"
        ]
        if len(prior_deployments) != 1:
            raise ValueError(
                "Recovery snapshot needs exactly one Deployment per component"
            )
        prior_deployment = prior_deployments[0]
        prior_containers = [
            item
            for item in prior_deployment["spec"]["template"]["spec"]["containers"]
            if item["name"] == component
        ]
        if len(prior_containers) != 1:
            raise ValueError("Missing application container in recovery snapshot")
        documents = [
            item for item in yaml.safe_load_all(manifests[f"{component}.yaml"]) if item
        ]
        updated = 0
        for document in documents:
            if document.get("kind") != "Deployment":
                continue
            if "replicas" in prior_deployment["spec"]:
                document["spec"]["replicas"] = prior_deployment["spec"]["replicas"]
            pod = document["spec"]["template"]
            for container in pod["spec"]["containers"]:
                if container["name"] == component:
                    container["image"] = previous["images"][component]
                    if "resources" in prior_containers[0]:
                        container["resources"] = prior_containers[0]["resources"]
                    container["env"] = [
                        item
                        for item in container.get("env", [])
                        if item["name"] != "RELEASE_ID"
                    ] + [{"name": "RELEASE_ID", "value": replacement_id}]
                    updated += 1
            for container in pod["spec"].get("initContainers", []):
                if component == "backend" and container["name"] == "migrate":
                    container["image"] = previous["images"][component]
            pod["metadata"].setdefault("annotations", {})[
                "idea-board/release-image"
            ] = previous["images"][component]
            pod["metadata"]["annotations"]["idea-board/gitops-release"] = replacement_id
        if updated != 1:
            raise ValueError(
                "Expected exactly one application Deployment per component"
            )
        manifests[f"{component}.yaml"] = yaml.safe_dump_all(documents, sort_keys=False)
    # Preserve current security controls, credentials and CA references. Restore
    # application images/replicas/resources so a bad AI profile can recover too.
    replacement = {key: value for key, value in metadata.items() if key != "hashes"}
    replacement.update(
        id=replacement_id,
        images=previous["images"],
        source_commit=previous["source_commit"],
        rolled_back_from=expected,
        recovered_image_release=previous["id"],
    )
    if "profile" in previous:
        replacement["profile"] = previous["profile"]
    result = save_release(root, target, replacement, manifests, expected=expected)
    status["rollback_pending"] = True
    status["last_failed_release"] = expected
    write_json(destination / "status.json", status)
    return result
