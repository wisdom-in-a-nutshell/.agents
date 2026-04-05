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
from urllib.parse import parse_qs, urlparse


SCHEMA_VERSION = "1.0"
COMMAND = "bootstrap-skill"

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
            f"ok skill={data['skill']} scope={data['scope']} "
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


def parse_skill_ref(raw: str) -> tuple[str, str]:
    parsed = urlparse(raw)
    if parsed.scheme and parsed.netloc:
        if parsed.netloc not in {"skills.sh", "www.skills.sh"}:
            raise ValueError(f"unsupported skill URL host: {parsed.netloc}")

        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) != 3 or parts[1] != "skills":
            raise ValueError(
                "skills.sh URLs must look like https://skills.sh/<owner>/skills/<skill>"
            )

        owner, repo_name, skill = parts
        branch = parse_qs(parsed.query).get("ref", ["main"])[0].strip() or "main"
        upstream_path = ".github/skills/" + skill if repo_name == "skills" else f"{repo_name}/{skill}"
        upstream_ref = f"{owner}/{repo_name}:{upstream_path}@{branch}"
        return skill, upstream_ref

    if ":" in raw and "@" in raw:
        try:
            repo_and_path, branch = raw.rsplit("@", 1)
            _repo, path = repo_and_path.split(":", 1)
        except ValueError as exc:
            raise ValueError(f"invalid upstream_ref: {raw}") from exc
        skill = path.rstrip("/").split("/")[-1]
        if not skill or not branch.strip():
            raise ValueError(f"invalid upstream_ref: {raw}")
        return skill, raw

    raise ValueError(
        "skill reference must be a skills.sh URL or an upstream_ref like owner/repo:path@branch"
    )


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
            "Bootstrap an external skill into ~/.agents canonical registry and "
            "optionally sync it into one or more repos."
        )
    )
    parser.add_argument(
        "skill_ref",
        help="skills.sh URL or upstream_ref (owner/repo:path@branch)",
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
        help="Install scope for the managed skill entry (default: repo).",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply changes. Default is dry-run.",
    )
    parser.add_argument(
        "--registry-file",
        default=str(Path.home() / ".agents" / "skills" / "registry.json"),
        help="Path to skills registry JSON.",
    )
    parser.add_argument(
        "--timeout-sec",
        type=int,
        default=180,
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
    request_id = f"bootstrap-skill-{uuid.uuid4()}"
    started_at = time.time()

    try:
        skill, upstream_ref = parse_skill_ref(args.skill_ref)
    except ValueError as exc:
        return finish_error(
            request_id,
            started_at,
            code="E_INVALID_SKILL_REF",
            message=str(exc),
            hint="Pass a skills.sh URL or an upstream_ref like owner/repo:path@branch.",
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
            hint="Repair skills/registry.json before bootstrapping a new skill.",
            exit_code=EXIT_USAGE,
            plain=args.plain,
        )

    github_root_raw = registry.get("paths", {}).get("github_root", "~/GitHub")
    github_root = expand_path(str(github_root_raw), home).resolve()

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

    managed = registry.get("managed_skills")
    if not isinstance(managed, list):
        return finish_error(
            request_id,
            started_at,
            code="E_INVALID_REGISTRY_SHAPE",
            message="managed_skills must be an array",
            hint="Repair skills/registry.json before bootstrapping a new skill.",
            exit_code=EXIT_USAGE,
            plain=args.plain,
        )

    global_entry: dict[str, Any] | None = None
    repo_entry: dict[str, Any] | None = None
    for entry in managed:
        if not isinstance(entry, dict) or entry.get("skill") != skill:
            continue
        if entry.get("scope") == "global":
            global_entry = entry
        elif entry.get("scope") == "repo":
            repo_entry = entry

    source_path = f"skills-source/external/{skill}"
    registry_changed = False
    actions: list[str] = []
    effective_scope = args.scope
    effective_repos = repos

    def ensure_external_entry_shape(entry: dict[str, Any]) -> None:
        if entry.get("origin") != "external":
            raise ValueError(f"skill {skill} already exists with origin={entry.get('origin')}")
        if entry.get("source_path") != source_path:
            raise ValueError(
                f"skill {skill} already exists with source_path={entry.get('source_path')}"
            )
        if entry.get("upstream_ref") != upstream_ref:
            raise ValueError(
                f"skill {skill} already exists with upstream_ref={entry.get('upstream_ref')}"
            )

    try:
        if global_entry is not None:
            ensure_external_entry_shape(global_entry)
            effective_scope = "global"
            effective_repos = []
            actions.append(f"Registry unchanged: global managed skill already exists for {skill}.")
        elif args.scope == "global":
            if repo_entry is not None:
                ensure_external_entry_shape(repo_entry)
            managed.append(
                {
                    "skill": skill,
                    "origin": "external",
                    "scope": "global",
                    "repos": [],
                    "source_path": source_path,
                    "upstream_ref": upstream_ref,
                }
            )
            registry_changed = True
            effective_repos = []
            actions.append(f"Registry add: managed global external skill {skill}.")
        elif repo_entry is not None:
            ensure_external_entry_shape(repo_entry)
            existing = unique_repos([*repo_entry.get("repos", []), *repos])
            if existing != repo_entry.get("repos", []):
                repo_entry["repos"] = existing
                registry_changed = True
                actions.append(
                    f"Registry update: added repo targets to managed repo skill {skill}: "
                    + ", ".join(repo for repo in existing if repo in repos)
                )
            else:
                actions.append(f"Registry unchanged: repo managed skill already covers {skill}.")
            effective_repos = existing
        else:
            managed.append(
                {
                    "skill": skill,
                    "origin": "external",
                    "scope": "repo",
                    "repos": repos,
                    "source_path": source_path,
                    "upstream_ref": upstream_ref,
                }
            )
            registry_changed = True
            actions.append(
                f"Registry add: managed repo external skill {skill} for " + ", ".join(repos) + "."
            )
    except ValueError as exc:
        return finish_error(
            request_id,
            started_at,
            code="E_CONFLICTING_SKILL_ENTRY",
            message=str(exc),
            hint="Resolve the existing registry entry manually before re-running bootstrap.",
            exit_code=EXIT_USAGE,
            plain=args.plain,
        )

    commands_run: list[dict[str, Any]] = []
    if args.apply:
        if registry_changed:
            registry_file.write_text(json.dumps(registry, indent=2) + "\n", encoding="utf-8")

        child_commands = [
            [sys.executable, "scripts/refresh-external-skills.py", "--apply", "--skill", skill],
            [sys.executable, "scripts/sync-skills-registry.py", "--apply"],
            [sys.executable, "codex/scripts/sync-repo-bootstrap-registry.py"],
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
        actions.append(f"Imported upstream skill into {source_path}.")
        actions.append("Synced managed skill links and regenerated derived registry artifacts.")
    else:
        actions.append(f"Would import upstream skill into {source_path}.")
        actions.append(
            "Would run refresh-external-skills, sync-skills-registry, "
            "and sync-repo-bootstrap-registry."
        )

    repo_links = []
    if effective_scope == "repo":
        for repo in effective_repos:
            repo_root = resolve_repo_root(repo, github_root, home)
            repo_links.append(str(repo_root / ".agents" / "skills" / skill))
    elif effective_scope == "global":
        repo_links.append(str(root_dir / "skills" / skill))

    data = {
        "skill": skill,
        "upstream_ref": upstream_ref,
        "scope": effective_scope,
        "repos": effective_repos,
        "source_path": source_path,
        "registry_file": str(registry_file),
        "registry_changed": registry_changed,
        "apply": bool(args.apply),
        "repo_roots": resolved_repo_roots,
        "expected_links": repo_links,
        "actions": actions,
        "commands_run": commands_run,
    }
    return finish_ok(request_id, started_at, data, plain=args.plain)


if __name__ == "__main__":
    raise SystemExit(main())
