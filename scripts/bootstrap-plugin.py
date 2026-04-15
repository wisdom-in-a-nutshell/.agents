#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
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
            f"ok plugin={data['plugin']} scope={data['scope']} "
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
        branch = parts[3].strip()
        plugin_path = "/".join(parts[4:]).strip("/")
        if not plugin_path.startswith("plugins/"):
            raise ValueError("only official openai/plugins plugin URLs are supported")
        plugin_name = plugin_path.split("/")[-1]
        if not plugin_name:
            raise ValueError(f"invalid plugin path in URL: {raw}")
        return plugin_name, f"openai/plugins:plugins/{plugin_name}@{branch or 'main'}"

    if "@" in raw:
        plugin_name, marketplace = raw.rsplit("@", 1)
        plugin_name = plugin_name.strip()
        marketplace = marketplace.strip()
        if marketplace != "openai-curated":
            raise ValueError(
                "only official openai-curated plugin ids are supported by bootstrap-plugin"
            )
        if not plugin_name:
            raise ValueError(f"invalid plugin id: {raw}")
        return plugin_name, f"openai/plugins:plugins/{plugin_name}@main"

    return raw, f"openai/plugins:plugins/{raw}@main"


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
            "Bootstrap an official plugin into ~/.agents as external plugin source and "
            "derive repo/global skills plus MCP from it."
        )
    )
    parser.add_argument(
        "plugin_ref",
        help="Plugin name, official plugin id (name@openai-curated), or official openai/plugins GitHub tree URL.",
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
        default="repo",
        help="Skill extraction scope for the plugin (default: repo).",
    )
    parser.add_argument(
        "--mcp-scope",
        choices=["inherit", "repo", "global"],
        default="inherit",
        help="MCP extraction scope (default: inherit plugin scope).",
    )
    parser.add_argument(
        "--mcp-repo",
        action="append",
        default=[],
        help="Override MCP repo targets when --mcp-scope repo. Repeat for multiple repos.",
    )
    parser.add_argument(
        "--no-skills",
        action="store_true",
        help="Do not extract bundled skills from the plugin.",
    )
    parser.add_argument(
        "--no-mcp",
        action="store_true",
        help="Do not extract bundled MCP config from the plugin.",
    )
    parser.add_argument(
        "--category",
        default="Coding",
        help="Category shown in the Obsidian registry view (default: Coding).",
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
        default=300,
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
        plugin_name, upstream_ref = parse_plugin_ref(args.plugin_ref)
    except ValueError as exc:
        return finish_error(
            request_id,
            started_at,
            code="E_INVALID_PLUGIN_REF",
            message=str(exc),
            hint="Pass a plugin name, name@openai-curated, or an official openai/plugins tree URL.",
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

    mcp_scope = args.scope if args.mcp_scope == "inherit" else args.mcp_scope
    mcp_repos = unique_repos(args.mcp_repo) if args.mcp_repo else list(repos)
    if not args.no_mcp and mcp_scope == "repo" and not mcp_repos:
        return finish_error(
            request_id,
            started_at,
            code="E_MCP_REPO_REQUIRED",
            message="repo MCP scope requires at least one repo target",
            hint="Pass --mcp-repo <name> or use --mcp-scope global.",
            exit_code=EXIT_USAGE,
            plain=args.plain,
        )

    missing_repos = []
    resolved_repo_roots: dict[str, str] = {}
    for repo in unique_repos([*repos, *mcp_repos]):
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

    source_path = f"plugins-source/external/{plugin_name}"
    existing_entry: dict[str, Any] | None = None
    for entry in managed:
        if isinstance(entry, dict) and str(entry.get("plugin", "")).strip() == plugin_name:
            existing_entry = entry
            break

    registry_changed = False
    actions: list[str] = []
    effective_scope = args.scope
    effective_repos = repos

    desired_entry = {
        "plugin": plugin_name,
        "origin": "external",
        "scope": args.scope,
        "repos": repos if args.scope == "repo" else [],
        "mcp_scope": mcp_scope,
        "mcp_repos": mcp_repos if mcp_scope == "repo" else [],
        "source_path": source_path,
        "upstream_ref": upstream_ref,
        "category": args.category,
        "extract_skills": not args.no_skills,
        "extract_mcp": not args.no_mcp,
    }

    if existing_entry is None:
        managed.append(desired_entry)
        registry_changed = True
        actions.append(f"Registry add: managed plugin source {plugin_name}.")
    else:
        for key, value in desired_entry.items():
            if existing_entry.get(key) != value:
                existing_entry[key] = value
                registry_changed = True
        if registry_changed:
            actions.append(f"Registry update: refreshed source config for {plugin_name}.")
        else:
            actions.append(f"Registry unchanged: managed plugin source already exists for {plugin_name}.")
        effective_scope = str(existing_entry.get("scope", args.scope))
        effective_repos = (
            unique_repos([str(repo).strip() for repo in existing_entry.get("repos", [])])
            if effective_scope == "repo"
            else []
        )

    commands_run: list[dict[str, Any]] = []
    if args.apply:
        if registry_changed:
            registry_file.write_text(json.dumps(registry, indent=2) + "\n", encoding="utf-8")

        child_commands = [
            [sys.executable, "scripts/refresh-external-plugins.py", "--apply", "--plugin", plugin_name],
            [sys.executable, "scripts/sync-plugins-registry.py", "--apply"],
            [str(root_dir / "scripts/bootstrap-machine-agent-control-planes.sh"), "--apply"],
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
        actions.append("Refreshed external plugin source from upstream.")
        actions.append("Regenerated plugin-derived skills and MCP state.")
        actions.append("Applied shared skills plus Codex and Claude bootstraps.")
    else:
        actions.append("Would refresh the external plugin source from upstream.")
        actions.append("Would regenerate plugin-derived skills and MCP state.")
        actions.append("Would apply shared skills plus Codex and Claude bootstraps.")

    data = {
        "plugin": plugin_name,
        "upstream_ref": upstream_ref,
        "source_path": source_path,
        "scope": effective_scope,
        "repos": effective_repos,
        "mcp_scope": mcp_scope,
        "mcp_repos": mcp_repos if mcp_scope == "repo" else [],
        "extract_skills": not args.no_skills,
        "extract_mcp": not args.no_mcp,
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
