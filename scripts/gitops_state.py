"""Validated GitOps release history and runtime-profile, compare-and-swap recovery."""

import hashlib
import json
from pathlib import Path
import re
import subprocess
import time

import yaml

FILES = ("backend.yaml", "frontend.yaml", "controls.yaml")
VALUE_FILES = {
    "backend": "helm-overides/idea-be/custom-values.yaml",
    "frontend": "helm-overides/idea-fe/custom-values.yaml",
}


def merge_values(base, override):
    import copy

    result = copy.deepcopy(base)
    for key, value in override.items():
        result[key] = (
            merge_values(result[key], value)
            if isinstance(value, dict) and isinstance(result.get(key), dict)
            else copy.deepcopy(value)
        )
    return result


def helm_manifests(root, values, name, namespace):
    """Preview the exact chart/values Argo will render; no cluster connection."""
    import tempfile

    identifier(name)
    identifier(namespace)
    if set(values) != set(VALUE_FILES):
        raise ValueError("Expected exactly the approved component values")

    result = {}
    with tempfile.TemporaryDirectory(prefix="gitops-helm-") as directory:
        for component, data in values.items():
            path = Path(directory) / f"{component}.yaml"
            path.write_text(yaml.safe_dump(data, sort_keys=False))
            rendered = subprocess.run(
                [
                    "helm",
                    "template",
                    f"{name}-{component}",
                    str(Path(root) / "helm-templates/nucleus"),
                    "--namespace",
                    namespace,
                    "--skip-tests",
                    "-f",
                    str(path),
                ],
                check=True,
                capture_output=True,
                text=True,
            ).stdout
            documents = [item for item in yaml.safe_load_all(rendered) if item]
            if any(
                "helm.sh/hook" in item.get("metadata", {}).get("annotations", {})
                for item in documents
            ):
                raise ValueError("Unexpected Helm hooks in application chart")
            result[f"{component}.yaml"] = yaml.safe_dump_all(documents, sort_keys=False)
    return result


def image_coordinates(reference):
    repository, digest = reference.split("@", 1)
    if ":" in repository.rsplit("/", 1)[-1]:
        repository, tag = repository.rsplit(":", 1)
    else:
        tag = "pinned"
    return {"repository": repository, "tag": tag + "@" + digest}


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
    return read_json(Path(root) / "releases" / identifier(target) / "release.json")


def save_release(root, target, metadata, manifests, expected=None, *, helm_values=None):
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
    if helm_values is not None and set(helm_values) != set(VALUE_FILES):
        raise ValueError("Expected exactly the approved component values")
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
    destination = root / "releases" / target
    managed = destination / "manifests"
    if managed.exists() and any(file.name not in FILES for file in managed.iterdir()):
        raise ValueError("Refuse to replace unmanaged files in the manifests directory")
    archive.mkdir(parents=True)
    for file, content in manifests.items():
        (archive / file).write_text(content)
    if helm_values is not None:
        metadata["delivery"] = "helm"
        metadata["helm_values_hashes"] = {}
        for component, values in helm_values.items():
            content = yaml.safe_dump(values, sort_keys=False)
            file = f"{component}-values.yaml"
            metadata["helm_values_hashes"][file] = hashlib.sha256(
                content.encode()
            ).hexdigest()
            (archive / file).write_text(content)
            path = root / VALUE_FILES[component]
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
    write_json(archive / "release.json", metadata)
    managed.mkdir(parents=True, exist_ok=True)
    controls = root / "argocd-manifests" / target / "controls.yaml"
    controls.parent.mkdir(parents=True, exist_ok=True)
    controls.write_text(manifests["controls.yaml"])
    if helm_values is None:
        # Compatibility for existing manifest-only targets; Helm targets need no preview copies.
        for file in ("backend.yaml", "frontend.yaml"):
            (managed / file).write_text(manifests[file])
    else:
        for file in FILES:
            (managed / file).unlink(missing_ok=True)
        managed.rmdir()
    write_json(destination / "release.json", metadata)
    return metadata


def verified_snapshot(root, target, release_id):
    archive = Path(root) / "releases" / identifier(target) / identifier(release_id)
    metadata = read_json(archive / "release.json")
    if not metadata or metadata["id"] != release_id or metadata["target"] != target:
        raise ValueError("Missing or mismatched recovery snapshot")
    if metadata.get("delivery") == "helm" and set(
        metadata.get("helm_values_hashes", {})
    ) != {f"{component}-values.yaml" for component in VALUE_FILES}:
        raise ValueError("Missing or unexpected recovery values checksums")
    for file in FILES:
        if (
            hashlib.sha256((archive / file).read_bytes()).hexdigest()
            != metadata["hashes"][file]
        ):
            raise ValueError("Recovery snapshot checksum mismatch")
    for component in VALUE_FILES:
        file = f"{component}-values.yaml"
        if file in metadata.get("helm_values_hashes", {}):
            if (
                hashlib.sha256((archive / file).read_bytes()).hexdigest()
                != metadata["helm_values_hashes"][file]
            ):
                raise ValueError("Recovery values checksum mismatch")
    return metadata


def mark_healthy(root, target, expected):
    metadata = current(root, target)
    if not metadata or metadata["id"] != expected:
        raise ValueError("Stale health report")
    status_path = Path(root) / "releases" / target / "status.json"
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
    destination = Path(root) / "releases" / target
    status = read_json(destination / "status.json", {"healthy_releases": []})
    if status.get("rollback_pending"):
        raise ValueError("Recovery is already pending; operator action is required")
    candidates = [item for item in status["healthy_releases"] if item != expected]
    if not candidates:
        raise ValueError("No previously verified healthy release is available")
    previous = verified_snapshot(root, target, candidates[0])
    replacement_id = f"recovery-{time.time_ns()}"
    if metadata.get("delivery") == "helm":
        values = {}
        for component, file in VALUE_FILES.items():
            data = yaml.safe_load((Path(root) / file).read_text())
            prior = list(
                yaml.safe_load_all(
                    (
                        Path(root)
                        / "releases"
                        / target
                        / previous["id"]
                        / f"{component}.yaml"
                    ).read_text()
                )
            )
            deployments = [
                item for item in prior if item and item.get("kind") == "Deployment"
            ]
            if len(deployments) != 1:
                raise ValueError("Recovery needs one Deployment per component")
            deployment = deployments[0]
            containers = [
                item
                for item in deployment["spec"]["template"]["spec"]["containers"]
                if item["name"] == component
            ]
            if len(containers) != 1:
                raise ValueError("Missing application container in recovery snapshot")
            data["image"].update(image_coordinates(previous["images"][component]))
            data["workload"]["replicaCount"] = deployment["spec"]["replicas"]
            data["resources"] = containers[0]["resources"]
            data.setdefault("env", {})["RELEASE_ID"] = replacement_id
            data.setdefault("podAnnotations", {}).update(
                {
                    "idea-board/release-image": previous["images"][component],
                    "idea-board/gitops-release": replacement_id,
                }
            )
            values[component] = data
        manifests = helm_manifests(
            root,
            values,
            metadata["name"],
            f"{metadata['name']}-{metadata['environment']}",
        )
        manifests["controls.yaml"] = (
            Path(root) / "argocd-manifests" / target / "controls.yaml"
        ).read_text()
        replacement = {
            key: value
            for key, value in metadata.items()
            if key not in ("hashes", "helm_values_hashes")
        }
        replacement.update(
            id=replacement_id,
            images=previous["images"],
            source_commit=previous["source_commit"],
            rolled_back_from=expected,
            recovered_image_release=previous["id"],
        )
        if "profile" in previous:
            replacement["profile"] = previous["profile"]
        result = save_release(
            root, target, replacement, manifests, expected=expected, helm_values=values
        )
        status.update(rollback_pending=True, last_failed_release=expected)
        write_json(destination / "status.json", status)
        return result
    manifests = {
        file: (destination / "manifests" / file).read_text()
        for file in ("backend.yaml", "frontend.yaml")
    }
    manifests["controls.yaml"] = (
        Path(root) / "argocd-manifests" / target / "controls.yaml"
    ).read_text()
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
