"""Collect aggregate HTTP health evidence without transmitting content or logs."""

import argparse
import json
import math
from pathlib import Path
import time
import urllib.error
import urllib.parse
import urllib.request


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def collect(url, count, restarts):
    parsed = urllib.parse.urlparse(url)
    if (
        parsed.scheme not in ("http", "https")
        or not parsed.netloc
        or parsed.username
        or parsed.password
    ):
        raise ValueError("Supply an HTTP(S) base URL without credentials")
    if count < 10 or restarts < 0:
        raise ValueError("Need at least ten samples and nonnegative new restarts")
    durations, failures = [], 0
    opener = urllib.request.build_opener(NoRedirect())
    for _ in range(count):
        start = time.monotonic()
        try:
            with opener.open(url.rstrip("/") + "/health/ready", timeout=5) as response:
                healthy = response.status == 200 and json.load(response) == {
                    "status": "ready"
                }
            if not healthy:
                failures += 1
        except (urllib.error.URLError, TimeoutError, ValueError):
            failures += 1
        durations.append((time.monotonic() - start) * 1000)
        time.sleep(0.2)
    return {
        "requests": count,
        "failures": failures,
        "p95_latency_ms": round(sorted(durations)[math.ceil(count * 0.95) - 1], 2),
        "restarts": restarts,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--count", type=int, default=20)
    parser.add_argument(
        "--new-restarts",
        type=int,
        required=True,
        help="Restart delta measured across this release, not lifetime count",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(collect(args.url, args.count, args.new_restarts), indent=2) + "\n"
    )
