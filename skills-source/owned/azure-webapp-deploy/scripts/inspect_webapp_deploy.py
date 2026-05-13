#!/usr/bin/env python3
"""Inspect a repo for Azure Web App container deploy readiness."""

from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "1.0"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class ToolError(Exception):
    def __init__(self, code: str, message: str, hint: str, exit_code: int = 1):
        super().__init__(message)
        self.code = code
        self.message = message
        self.hint = hint
        self.exit_code = exit_code


def _result(command: str, status: str, data: dict[str, Any] | None, error: dict[str, Any] | None, start: float) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "command": command,
        "status": status,
        "data": data or {},
        "error": error,
        "meta": {
            "request_id": str(uuid.uuid4()),
            "timestamp_utc": _now(),
            "duration_ms": int((time.monotonic() - start) * 1000),
        },
    }


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _contains(path: Path, needle: str) -> bool:
    return path.exists() and needle in path.read_text(encoding="utf-8", errors="replace")


def inspect_repo(repo_dir: Path) -> dict[str, Any]:
    if not repo_dir.exists():
        raise ToolError(
            "E_REPO_NOT_FOUND",
            f"Repo directory not found: {repo_dir}",
            "Pass --repo-dir with an existing project directory.",
            2,
        )

    package = _read_json(repo_dir / "package.json")
    scripts = package.get("scripts", {}) if package else {}

    lockfiles = {
        "package_lock": (repo_dir / "package-lock.json").exists(),
        "pnpm_lock": (repo_dir / "pnpm-lock.yaml").exists(),
        "yarn_lock": (repo_dir / "yarn.lock").exists(),
    }
    package_manager = "unknown"
    if lockfiles["pnpm_lock"]:
        package_manager = "pnpm"
    elif lockfiles["package_lock"]:
        package_manager = "npm"
    elif lockfiles["yarn_lock"]:
        package_manager = "yarn"

    next_config = next(repo_dir.glob("next.config.*"), None)
    workflow = repo_dir / ".github" / "workflows" / "deploy.yml"
    dockerfile = repo_dir / "Dockerfile"
    env_example = repo_dir / ".env.example"

    findings = []
    if package is None:
        findings.append({"severity": "high", "code": "NO_PACKAGE_JSON", "message": "No package.json found."})
    if package and "build" not in scripts:
        findings.append({"severity": "high", "code": "NO_BUILD_SCRIPT", "message": "package.json has no build script."})
    if package and "test" not in scripts:
        findings.append({"severity": "medium", "code": "NO_TEST_SCRIPT", "message": "package.json has no test script."})
    if package and "lint" not in scripts:
        findings.append({"severity": "medium", "code": "NO_LINT_SCRIPT", "message": "package.json has no lint script."})
    if package_manager == "unknown" and package:
        findings.append({"severity": "medium", "code": "NO_LOCKFILE", "message": "No recognized package lockfile found."})
    if next_config and not _contains(next_config, "standalone"):
        findings.append({"severity": "medium", "code": "NEXT_NOT_STANDALONE", "message": "Next config does not mention standalone output."})
    if not dockerfile.exists():
        findings.append({"severity": "medium", "code": "NO_DOCKERFILE", "message": "No Dockerfile found."})
    if not workflow.exists():
        findings.append({"severity": "medium", "code": "NO_DEPLOY_WORKFLOW", "message": "No .github/workflows/deploy.yml found."})

    return {
        "repo_dir": str(repo_dir),
        "package_manager": package_manager,
        "is_next_app": bool(package and "next" in {**package.get("dependencies", {}), **package.get("devDependencies", {})}),
        "has_next_standalone": bool(next_config and _contains(next_config, "standalone")),
        "has_dockerfile": dockerfile.exists(),
        "has_deploy_workflow": workflow.exists(),
        "has_env_example": env_example.exists(),
        "scripts": sorted(scripts.keys()) if package else [],
        "lockfiles": lockfiles,
        "llm_env_documented": bool(env_example.exists() and ("LLM_API_KEY" in env_example.read_text(encoding="utf-8", errors="replace"))),
        "findings": findings,
        "ready_level": "ready" if not [f for f in findings if f["severity"] == "high"] else "blocked",
    }


def main() -> int:
    start = time.monotonic()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-dir", default=".", help="Repository directory to inspect.")
    parser.add_argument("--json", action="store_true", help="Emit JSON. This is the default.")
    parser.add_argument("--plain", action="store_true", help="Emit concise plain text.")
    parser.add_argument("--no-input", action="store_true", help="Do not prompt. This script never prompts.")
    args = parser.parse_args()

    try:
        data = inspect_repo(Path(args.repo_dir).expanduser().resolve())
        result = _result("inspect_webapp_deploy", "ok", data, None, start)
        exit_code = 0
    except ToolError as exc:
        result = _result(
            "inspect_webapp_deploy",
            "error",
            None,
            {"code": exc.code, "message": exc.message, "retryable": False, "hint": exc.hint},
            start,
        )
        exit_code = exc.exit_code
    except Exception as exc:  # noqa: BLE001
        result = _result(
            "inspect_webapp_deploy",
            "error",
            None,
            {"code": "E_UNEXPECTED", "message": str(exc), "retryable": False, "hint": "Run with a valid repo and inspect the error."},
            start,
        )
        exit_code = 1

    if args.plain:
        if result["status"] == "ok":
            data = result["data"]
            print(f"{data['ready_level']}: {data['repo_dir']}")
            for finding in data["findings"]:
                print(f"{finding['severity']} {finding['code']}: {finding['message']}")
        else:
            print(f"{result['error']['code']}: {result['error']['message']}", file=sys.stderr)
    else:
        print(json.dumps(result, indent=2, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
