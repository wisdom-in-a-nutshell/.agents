#!/usr/bin/env python3
"""Verify deployed web app endpoints."""

from __future__ import annotations

import argparse
import json
import subprocess
import time
import uuid
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urljoin


SCHEMA_VERSION = "1.0"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _result(status: str, data: dict[str, Any], error: dict[str, Any] | None, start: float) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "command": "verify_deploy",
        "status": status,
        "data": data,
        "error": error,
        "meta": {
            "request_id": str(uuid.uuid4()),
            "timestamp_utc": _now(),
            "duration_ms": int((time.monotonic() - start) * 1000),
        },
    }


def _curl(url: str, timeout: int, resolve: list[str]) -> dict[str, Any]:
    cmd = ["curl", "-sS", "-o", "-", "-w", "\n%{http_code}", "--max-time", str(timeout)]
    for entry in resolve:
        cmd.extend(["--resolve", entry])
    cmd.append(url)
    proc = subprocess.run(cmd, text=True, capture_output=True)
    stdout = proc.stdout
    body, _, code = stdout.rpartition("\n")
    return {
        "url": url,
        "exit_code": proc.returncode,
        "http_code": int(code) if code.isdigit() else None,
        "ok": proc.returncode == 0 and code.isdigit() and 200 <= int(code) < 400,
        "body_prefix": body[:500],
        "stderr": proc.stderr.strip()[:500],
    }


def main() -> int:
    start = time.monotonic()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--path", action="append", default=[])
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--resolve", action="append", default=[], help="curl --resolve entry, e.g. host:443:ip")
    parser.add_argument("--json", action="store_true", help="Emit JSON. This is the default.")
    parser.add_argument("--plain", action="store_true", help="Emit concise plain text.")
    parser.add_argument("--no-input", action="store_true", help="Do not prompt. This script never prompts.")
    args = parser.parse_args()

    checks = []
    paths = args.path or ["/api/health"]
    for path in paths:
        url = urljoin(args.base_url.rstrip("/") + "/", path.lstrip("/"))
        checks.append(_curl(url, args.timeout, args.resolve))

    failed = [check for check in checks if not check["ok"]]
    data = {
        "base_url": args.base_url,
        "checks": checks,
        "summary": {
            "total": len(checks),
            "passed": len(checks) - len(failed),
            "failed": len(failed),
        },
    }

    if failed:
        result = _result(
            "error",
            data,
            {
                "code": "E_VERIFY_FAILED",
                "message": "One or more endpoint checks failed.",
                "retryable": True,
                "hint": "Inspect failed checks, DNS, TLS, app startup logs, and runtime app settings.",
            },
            start,
        )
        exit_code = 1
    else:
        result = _result("ok", data, None, start)
        exit_code = 0

    if args.plain:
        print(f"{data['summary']['passed']}/{data['summary']['total']} checks passed")
        for check in checks:
            print(f"{check['http_code']} {check['url']}")
    else:
        print(json.dumps(result, indent=2, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
