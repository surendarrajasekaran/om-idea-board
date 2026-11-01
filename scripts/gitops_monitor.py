"""HTTP health assessment and a guarded Git commit for GitOps recovery."""

import argparse
import json
from pathlib import Path
import subprocess
import time
import urllib.request

try:
    from .ai_ops import assess, show_report
    from .gitops_state import current, mark_healthy, read_json, recover_images
    from .probe import collect
    from .smoke import smoke
except ImportError:
    from ai_ops import assess, show_report
    from gitops_state import current, mark_healthy, read_json, recover_images
    from probe import collect
    from smoke import smoke


def wait_for_release(url, release_id, timeout=600):
    deadline = time.monotonic() + timeout
    consecutive = 0
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(
                url.rstrip("/") + "/health/release", timeout=5
            ) as response:
                if (
                    response.headers.get("X-Idea-Board-Release") == release_id
                    and json.load(response).get("release_id") == release_id
                ):
                    consecutive += 1
                    if consecutive >= 3:
                        return True
                else:
                    consecutive = 0
        except (OSError, ValueError, AttributeError, TypeError):
            consecutive = 0
        time.sleep(10)
    return False


def monitor(root, target, output, convergence_timeout=600, *, display=False):
    metadata = current(root, target)
    if not metadata or not metadata.get("public_url"):
        raise ValueError("A verified deployment URL must be configured first")
    converged = wait_for_release(
        metadata["public_url"], metadata["id"], timeout=convergence_timeout
    )
    measured = collect(metadata["public_url"], 20, 0)
    samples = {key: value for key, value in measured.items() if key != "restarts"}
    status = read_json(
        root / "environments" / target / "status.json", {"healthy_releases": []}
    )
    already_healthy = bool(
        status["healthy_releases"] and status["healthy_releases"][0] == metadata["id"]
    )
    violation = (
        measured["failures"] / measured["requests"] > 0.05
        or measured["p95_latency_ms"] > 1500
    )
    if already_healthy and not violation and converged:
        # Avoid spending trial requests repeatedly on an unchanged healthy release.
        report = {
            "decision": "keep",
            "source": "steady-state-policy",
            "telemetry_coverage": "http-only",
            "evidence": samples,
        }
    else:
        report = assess(samples, http_only=True)
    report["release_converged"] = converged
    report["convergence_timeout_seconds"] = convergence_timeout
    if not converged:
        report["decision"] = "rollback"
        report.setdefault("policy_violations", []).append(
            "Frontend/backend release did not converge before the deadline"
        )
    if converged and not already_healthy:
        try:
            smoke(metadata["public_url"])
            report["functional_smoke"] = "passed"
        except (OSError, ValueError, AssertionError, KeyError, TypeError):
            report["functional_smoke"] = "failed"
            report["decision"] = "rollback"
            report.setdefault("policy_violations", []).append(
                "New-release write/read smoke failed"
            )
    report["release_id"] = metadata["id"]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n")
    changed = False
    if report["decision"] == "rollback":
        if report.get("policy_violations"):
            report["summary"] = "; ".join(report["policy_violations"])
        try:
            recovery = recover_images(root, target, metadata["id"])
            report["recovery_release_id"] = recovery["id"]
            report["recovery_status"] = "pending-reconciliation"
            changed = True
        except ValueError as exc:
            report["recovery_status"] = "operator-action-required"
            report["recovery_reason"] = str(exc)
            output.write_text(json.dumps(report, indent=2) + "\n")
            if display:
                show_report(report)
            raise
        output.write_text(json.dumps(report, indent=2) + "\n")
    elif not already_healthy:
        changed = mark_healthy(root, target, metadata["id"])
    if display:
        show_report(report)
    if changed:
        subprocess.run(["git", "add", "environments", "releases"], cwd=root, check=True)
        subprocess.run(
            [
                "git",
                "commit",
                "-m",
                f"health({target}): {report['decision']} release {metadata['id']}",
            ],
            cwd=root,
            check=True,
        )
        # A normal fast-forward push rejects stale observations if a concurrent
        # release/health job changed main. Never force push or silently reset.
        subprocess.run(
            [
                "git",
                "-c",
                "credential.helper=",
                "-c",
                "credential.helper=!gh auth git-credential",
                "push",
                "origin",
                "HEAD:main",
            ],
            cwd=root,
            check=True,
        )
    print(
        f"Release {metadata['id']}: {report['decision']}, source={report['source']}, coverage=http-only"
    )
    return 1 if report["decision"] == "rollback" else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--target", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--convergence-timeout", type=int, default=600)
    parser.add_argument("--show-report", action="store_true")
    args = parser.parse_args()
    if not 30 <= args.convergence_timeout <= 1800:
        parser.error("Convergence timeout must be 30-1800 seconds")
    try:
        parser.exit(
            monitor(
                args.root,
                args.target,
                args.output,
                args.convergence_timeout,
                display=args.show_report,
            )
        )
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        parser.exit(
            1,
            f"GitOps health check failed ({type(exc).__name__}); inspect the saved report and release history\n",
        )


if __name__ == "__main__":
    main()
