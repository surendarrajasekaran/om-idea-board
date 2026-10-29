"""Verify the public frontend and the write/read path. Creates one identifiable idea."""

import argparse
import json
import urllib.request
import uuid


def smoke(url):
    base = url.rstrip("/")
    with urllib.request.urlopen(base + "/", timeout=10) as response:
        assert response.status == 200 and b"<html" in response.read().lower(), (
            "Frontend failed"
        )
    with urllib.request.urlopen(base + "/health/ready", timeout=10) as response:
        assert json.load(response) == {"status": "ready"}, "Readiness failed"
    content = f"Deployment verification {uuid.uuid4()}"
    request = urllib.request.Request(
        base + "/api/ideas",
        data=json.dumps({"content": content}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        assert response.status == 201, "Create failed"
        created = json.load(response)
        assert created["content"] == content and created["created_at"], (
            "Invalid create response"
        )
    with urllib.request.urlopen(base + "/api/ideas", timeout=10) as response:
        assert any(
            idea["id"] == created["id"] and idea["content"] == content
            for idea in json.load(response)
        ), "Read-after-write failed"
    print(
        f"PASS: frontend, readiness, create, read; verification idea id={created['id']}"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    smoke(parser.parse_args().url)
