#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


SCHEMA_VERSION = "1.0"
COMMAND = "bootstrap-plugin"

EXIT_SUCCESS = 0
EXIT_FAILURE = 1
EXIT_USAGE = 2
EXIT_DEPENDENCY = 4
EXIT_TIMEOUT = 5


def utc_timestamp() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def meta(request_id: str, started_at: float) -> dict[str, Any]:
    return {
        "request_id": request_id,
        "duration_ms": int((time.time() - started_at) * 1000),
        "timestamp_utc": utc_timestamp(),
    }


def emit_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2))


def emit_plain(payload: dict[str, Any]) -> None:
    if payload["status"] == "ok":
        data = payload["data"]
        print(
            f"ok plugin_id={data['plugin_id']} scope={data['scope']} "
            f"registry_changed={str(data['registry_changed']).lower()}"
        )
        for action in data["actions"]:
            print(action)
        return

    error = payload["error"]
    print(f"error {error['code']}: {error['message']}", file=sys.stderr)
    if error.get("hint"):
        print(error["hint"], file=sys.stderr)


def finish_ok(
    request_id: str,
    started_at: float,
    data: dict[str, Any],
    *,
    plain: bool,
) -> int:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "command": COMMAND,
        "status": "ok",
        "data": data,
        "error": None,
        "meta": meta(request_id, started_at),
    }
    if plain:
        emit_plain(payload)
    else:
        emit_json(payload)
    return EXIT_SUCCESS


def finish_error(
    request_id: str,
    started_at: float,
    *,
    code: str,
    message: str,
    hint: str,
    exit_code: int,
    plain: bool,
) -> int:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "command": COMMAND,
        "status": "error",
        "data": {},
        "error": {
            "code": code,
            "message": message,
            "retryable": False,
            "hint": hint,
        },
        "meta": meta(request_id, started_at),
    }
    if plain:
        emit_plain(payload)
    else:
        emit_json(payload)
    return exit_code


def expand_path(raw: str, home: Path) -> Path:
    if raw.startswith("~/"):
        return home / raw[2:]
    return Path(raw)


def resolve_repo_root(repo: str, github_root: Path, home: Path) -> Path:
    if repo.startswith("~/") or repo.startswith("/"):
        return expand_path(repo, home).resolve()
    return (github_root / repo).resolve()


def parse_plugin_ref(raw: str) -> tuple[str, str]:
    raw = raw.strip()
    if not raw:
        raise ValueError("plugin reference must not be empty")

    parsed = urlparse(raw)
    if parsed.scheme and parsed.netloc:
        if parsed.netloc != "github.com":
            raise ValueError(f"unsupported plugin URL host: {parsed.netloc}")
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) < 5 or parts[0] != "openai" or parts[1] != "plugins" or parts[2] != "tree":
            raise ValueError(
                "GitHub plugin URLs must look like https://github.com/openai/plugins/tree/<branch>/plugins/<name>"
            )
        plugin_path = "/".join(parts[4:]).strip("/")
        if not plugin_path.startswith("plugins/"):
            raise ValueError("only official openai/plugins plugin URLs are supported")
        plugin_name = plugin_path.split("/")[-1]
        if not plugin_name:
            raise ValueError(f"invalid plugin path in URL: {raw}")
        return plugin_name, f"{plugin_name}@openai-curated"

    if "@" in raw:
        plugin_name, marketplace = raw.rsplit("@", 1)
        plugin_name = plugin_name.strip()
        marketplace = marketplace.strip()
        if not plugin_name or not marketplace:
            raise ValueError(f"invalid plugin id: {raw}")
        return plugin_name, f"{plugin_name}@{marketplace}"

    if not re.fullmatch(r"[A-Za-z0-9._-]+", raw):
        raise ValueError(
            "plugin reference must be a plugin name, a plugin id like name@marketplace, or an official GitHub tree URL"
        )
    return raw, f"{raw}@openai-curated"


def unique_repos(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        repo = value.strip()
        if not repo or repo in seen:
            continue
        seen.add(repo)
        out.append(repo)
    return out


def run(
    cmd: list[str],
    *,
    cwd: Path,
    timeout_sec: int,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout_sec,
        check=False,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Bootstrap an official Codex plugin into ~/.agents canonical registry and "
            "optionally apply the managed Codex state."
        )
    )
    parser.add_argument(
        "plugin_ref",
        help="Plugin name, plugin id (name@marketplace), or official openai/plugins GitHub tree URL.",
    )
    parser.add_argument(
        "--repo",
        action="append",
        default=[],
        help="Repo target under ~/GitHub or an explicit path. Repeat for multiple repos.",
    )
    parser.add_argument(
        "--scope",
        choices=["repo", "global"],
        default="global",
        help="Enablement scope for the managed plugin entry (default: global).",
    )
    parser.add_argument(
        "--category",
        default="Coding",
        help="Category shown in the Obsidian registry view (default: Coding).",
    )
    parser.add_argument(
        "--enabled",
        dest="enabled",
        action="store_true",
        default=True,
        help="Enable the plugin in its managed scope (default).",
    )
    parser.add_argument(
        "--disabled",
        dest="enabled",
        action="store_false",
        help="Track the plugin but render it disabled in config.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply changes. Default is dry-run.",
    )
    parser.add_argument(
        "--registry-file",
        default=str(Path.home() / ".agents" / "plugins" / "registry.json"),
        help="Path to plugins registry JSON.",
    )
    parser.add_argument(
        "--timeout-sec",
        type=int,
        default=240,
        help="Timeout for each child command.",
    )
    parser.add_argument(
        "--plain",
        action="store_true",
        help="Emit stable plain-text inspection output instead of JSON.",
    )
    parser.add_argument(
        "--no-input",
        action="store_true",
        help="Accepted for agent-safe non-interactive operation; prompts are never used.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    request_id = f"bootstrap-plugin-{uuid.uuid4()}"
    started_at = time.time()

    try:
        plugin_name, plugin_id = parse_plugin_ref(args.plugin_ref)
    except ValueError as exc:
        return finish_error(
            request_id,
            started_at,
            code="E_INVALID_PLUGIN_REF",
            message=str(exc),
            hint="Pass a plugin name, a plugin id like build-ios-apps@openai-curated, or an official GitHub tree URL.",
            exit_code=EXIT_USAGE,
            plain=args.plain,
        )

    registry_file = Path(args.registry_file).expanduser().resolve()
    if not registry_file.is_file():
        return finish_error(
            request_id,
            started_at,
            code="E_REGISTRY_NOT_FOUND",
            message=f"Registry not found: {registry_file}",
            hint="Run this inside the ~/.agents control-plane repo or pass --registry-file.",
            exit_code=EXIT_USAGE,
            plain=args.plain,
        )

    home = Path.home()
    root_dir = registry_file.parent.parent.resolve()

    try:
        registry = json.loads(registry_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return finish_error(
            request_id,
            started_at,
            code="E_INVALID_REGISTRY_JSON",
            message=f"Invalid JSON in {registry_file}: {exc}",
            hint="Repair plugins/registry.json before bootstrapping a plugin.",
            exit_code=EXIT_USAGE,
            plain=args.plain,
        )

    paths = registry.get("paths", {})
    github_root_raw = str(paths.get("github_root", "~/GitHub"))
    github_root = expand_path(github_root_raw, home).resolve()

    repos = unique_repos(args.repo)
    if args.scope == "repo" and not repos:
        return finish_error(
            request_id,
            started_at,
            code="E_REPO_REQUIRED",
            message="repo scope requires at least one --repo target",
            hint="Pass --repo <name> for repo scope, or use --scope global.",
            exit_code=EXIT_USAGE,
            plain=args.plain,
        )

    missing_repos = []
    resolved_repo_roots: dict[str, str] = {}
    for repo in repos:
        repo_root = resolve_repo_root(repo, github_root, home)
        resolved_repo_roots[repo] = str(repo_root)
        if not repo_root.exists():
            missing_repos.append(f"{repo} -> {repo_root}")
    if missing_repos:
        return finish_error(
            request_id,
            started_at,
            code="E_REPO_NOT_FOUND",
            message="One or more repo targets do not exist",
            hint="Fix the repo names or paths: " + "; ".join(missing_repos),
            exit_code=EXIT_USAGE,
            plain=args.plain,
        )

    managed = registry.get("managed_plugins")
    if not isinstance(managed, list):
        return finish_error(
            request_id,
            started_at,
            code="E_INVALID_REGISTRY_SHAPE",
            message="managed_plugins must be an array",
            hint="Repair plugins/registry.json before bootstrapping a plugin.",
            exit_code=EXIT_USAGE,
            plain=args.plain,
        )

    existing_entry: dict[str, Any] | None = None
    for entry in managed:
        if isinstance(entry, dict) and entry.get("plugin_id") == plugin_id:
            existing_entry = entry
            break

    registry_changed = False
    actions: list[str] = []
    effective_scope = args.scope
    effective_repos = repos

    if existing_entry is None:
        managed.append(
            {
                "plugin_id": plugin_id,
                "scope": args.scope,
                "repos": repos if args.scope == "repo" else [],
                "enabled": args.enabled,
                "category": args.category,
            }
        )
        registry_changed = True
        actions.append(f"Registry add: managed plugin {plugin_id}.")
    else:
        existing_scope = str(existing_entry.get("scope", "")).strip()
        existing_repos = existing_entry.get("repos", [])
        if not isinstance(existing_repos, list):
            existing_repos = []

        updated_repos = repos if args.scope == "repo" else []
        if existing_scope != args.scope:
            existing_entry["scope"] = args.scope
            existing_entry["repos"] = updated_repos
            registry_changed = True
            actions.append(f"Registry update: scope for {plugin_id} -> {args.scope}.")
        elif args.scope == "repo":
            merged_repos = unique_repos([*existing_repos, *repos])
            if merged_repos != existing_repos:
                existing_entry["repos"] = merged_repos
                registry_changed = True
                actions.append(
                    f"Registry update: added repo targets to {plugin_id}: " + ", ".join(repos)
                )
            updated_repos = merged_repos
        else:
            existing_entry["repos"] = []

        if existing_entry.get("enabled", True) != args.enabled:
            existing_entry["enabled"] = args.enabled
            registry_changed = True
            actions.append(
                f"Registry update: enabled={str(args.enabled).lower()} for {plugin_id}."
            )
        if str(existing_entry.get("category", "")).strip() != args.category:
            existing_entry["category"] = args.category
            registry_changed = True
            actions.append(f"Registry update: category={args.category} for {plugin_id}.")

        effective_scope = str(existing_entry.get("scope", args.scope))
        effective_repos = (
            unique_repos([str(repo).strip() for repo in existing_entry.get("repos", [])])
            if effective_scope == "repo"
            else []
        )
        if not actions:
            actions.append(f"Registry unchanged: managed plugin already exists for {plugin_id}.")

    commands_run: list[dict[str, Any]] = []
    if args.apply:
        if registry_changed:
            registry_file.write_text(json.dumps(registry, indent=2) + "\n", encoding="utf-8")

        child_commands = [
            [sys.executable, "scripts/sync-plugins-registry.py", "--apply"],
            [str(root_dir / "codex/scripts/bootstrap-machine-codex.sh"), "--apply"],
        ]

        for cmd in child_commands:
            try:
                proc = run(cmd, cwd=root_dir, timeout_sec=args.timeout_sec)
            except subprocess.TimeoutExpired:
                return finish_error(
                    request_id,
                    started_at,
                    code="E_TIMEOUT",
                    message=f"Timed out running: {' '.join(cmd)}",
                    hint="Re-run with a larger --timeout-sec if the dependency is just slow.",
                    exit_code=EXIT_TIMEOUT,
                    plain=args.plain,
                )
            commands_run.append(
                {
                    "argv": cmd,
                    "exit_code": proc.returncode,
                    "stdout": proc.stdout.strip(),
                    "stderr": proc.stderr.strip(),
                }
            )
            if proc.returncode != 0:
                return finish_error(
                    request_id,
                    started_at,
                    code="E_CHILD_COMMAND_FAILED",
                    message=f"Command failed: {' '.join(cmd)}",
                    hint=proc.stderr.strip() or proc.stdout.strip() or "Inspect command output.",
                    exit_code=EXIT_DEPENDENCY,
                    plain=args.plain,
                )
        actions.append("Regenerated plugin registry views.")
        actions.append("Applied managed Codex plugin install/config state.")
    else:
        actions.append("Would regenerate plugin registry views.")
        actions.append("Would apply managed Codex plugin install/config state.")

    data = {
        "plugin_name": plugin_name,
        "plugin_id": plugin_id,
        "scope": effective_scope,
        "repos": effective_repos,
        "enabled": args.enabled,
        "registry_file": str(registry_file),
        "registry_changed": registry_changed,
        "apply": bool(args.apply),
        "repo_roots": resolved_repo_roots,
        "actions": actions,
        "commands_run": commands_run,
    }
    return finish_ok(request_id, started_at, data, plain=args.plain)


if __name__ == "__main__":
    raise SystemExit(main())
