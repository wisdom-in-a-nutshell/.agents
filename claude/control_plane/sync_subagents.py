from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

from agents.registry import load_agent_registry

from .common import (
    ControlPlaneError,
    RenderAction,
    git_repo_root,
    install_rendered_file,
    main_guard,
    normalize_path,
    remove_managed_file,
    repo_root,
    show_diff,
)


def yaml_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "null"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        if "\n" in value:
            escaped = value.rstrip("\n")
            indented = "\n".join(f"  {line}" for line in escaped.splitlines())
            return f"|\n{indented}"
        return json.dumps(value)
    raise TypeError(f"Unsupported YAML scalar: {value!r}")


def emit_yaml_lines(lines: list[str], key: str, value: Any, indent: int = 0) -> None:
    prefix = "  " * indent
    if isinstance(value, dict):
        if not value:
            lines.append(f"{prefix}{key}: {{}}")
            return
        lines.append(f"{prefix}{key}:")
        for subkey, subvalue in value.items():
            emit_yaml_lines(lines, str(subkey), subvalue, indent + 1)
        return
    if isinstance(value, list):
        if not value:
            lines.append(f"{prefix}{key}: []")
            return
        lines.append(f"{prefix}{key}:")
        for item in value:
            if isinstance(item, (dict, list)):
                lines.append(f"{prefix}  -")
                if isinstance(item, dict):
                    for subkey, subvalue in item.items():
                        emit_yaml_lines(lines, str(subkey), subvalue, indent + 2)
                else:
                    emit_yaml_lines(lines, "value", item, indent + 2)
                continue
            lines.append(f"{prefix}  - {yaml_scalar(item)}")
        return
    scalar = yaml_scalar(value)
    if scalar.startswith("|\n"):
        lines.append(f"{prefix}{key}: {scalar.splitlines()[0]}")
        lines.extend(f"{prefix}{line}" for line in scalar.splitlines()[1:])
        return
    lines.append(f"{prefix}{key}: {scalar}")


def render_frontmatter(frontmatter: dict[str, Any]) -> str:
    lines = ["---"]
    for key, value in frontmatter.items():
        emit_yaml_lines(lines, key, value)
    lines.append("---")
    return "\n".join(lines) + "\n"


def render_subagent(frontmatter: dict[str, Any], prompt_body: str) -> str:
    prompt = prompt_body.strip()
    body = f"{prompt}\n" if prompt else ""
    return render_frontmatter(frontmatter) + "\n" + body


def read_manifest(path: Path) -> list[str]:
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    if isinstance(data, dict):
        files = data.get("files", [])
    else:
        files = data
    if not isinstance(files, list):
        return []
    ordered: list[str] = []
    for value in files:
        if isinstance(value, str) and value.strip() and value not in ordered:
            ordered.append(value)
    return ordered


def render_manifest(files: list[str]) -> str:
    payload = {
        "generated_by": "~/.agents/claude/scripts/sync-subagents.sh",
        "files": sorted(dict.fromkeys(files)),
    }
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def claude_permission_mode(agent: dict[str, Any], claude: dict[str, Any]) -> str | None:
    if "permission_mode" in claude:
        return str(claude["permission_mode"])
    if agent.get("access_profile") == "full_access":
        return "bypassPermissions"
    return None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render managed Claude subagents from the shared agent registry."
    )
    parser.add_argument("--apply", dest="apply", action="store_true", help="Apply changes in place")
    parser.add_argument(
        "--dry-run",
        dest="apply",
        action="store_false",
        help="Show diffs only (default)",
    )
    parser.set_defaults(apply=False)
    parser.add_argument(
        "--registry",
        default=str(repo_root() / "codex" / "config" / "repo-bootstrap.json"),
        help="Override shared repo bootstrap registry",
    )
    parser.add_argument(
        "--agent-registry",
        default=str(repo_root() / "agents" / "registry.json"),
        help="Override shared agent registry",
    )
    parser.add_argument(
        "--global-agents-dir",
        default=str(Path.home() / ".claude" / "agents"),
        help="Override runtime ~/.claude/agents target",
    )
    parser.add_argument(
        "--repo",
        action="append",
        default=[],
        help="Limit repo-local sync to an exact repo path (repeatable)",
    )
    return parser.parse_args()


def build_actions(
    *,
    repo_registry_path: Path,
    agent_registry_path: Path,
    global_agents_dir: Path,
    repo_filters: list[str],
    temp_dir: Path,
) -> list[RenderAction]:
    repo_data = json.loads(repo_registry_path.read_text(encoding="utf-8"))
    repos_raw = repo_data.get("repos", [])
    if not isinstance(repos_raw, list):
        raise ControlPlaneError("repos must be an array")

    filters = {normalize_path(path) for path in repo_filters if path}
    repo_roots_by_name: dict[str, str] = {}
    selected_repo_roots: dict[str, str] = {}
    for item in repos_raw:
        if not isinstance(item, dict):
            raise ControlPlaneError("each repo entry must be an object")
        raw_path = item.get("path")
        if not isinstance(raw_path, str) or not raw_path.strip():
            raise ControlPlaneError("repo.path must be a non-empty string")

        repo_path = Path(normalize_path(raw_path))
        actual_repo = git_repo_root(repo_path)
        if actual_repo is None:
            print(f"WARNING: skipping non-git path: {repo_path}", file=sys.stderr)
            continue

        actual_repo_str = str(actual_repo)
        repo_name = Path(actual_repo_str).name or actual_repo_str
        repo_roots_by_name[repo_name] = actual_repo_str
        if not filters or actual_repo_str in filters:
            selected_repo_roots[repo_name] = actual_repo_str

    managed_agents = load_agent_registry(
        agent_registry_path,
        root_dir=agent_registry_path.parent.parent.resolve(),
        valid_repo_names=set(repo_roots_by_name),
    )

    desired_files_by_dir: dict[Path, dict[str, Path]] = {global_agents_dir: {}}
    actions: list[RenderAction] = []

    for agent in managed_agents:
        claude = agent.get("claude")
        if not isinstance(claude, dict) or not claude.get("materialize"):
            continue

        source_path = Path(claude["source_path"])
        if not source_path.is_file():
            raise ControlPlaneError(
                f"Missing Claude prompt source for `{agent['agent']}`: {source_path}"
            )
        prompt_body = source_path.read_text(encoding="utf-8")

        frontmatter: dict[str, Any] = {
            "name": str(claude["name"]),
            "description": str(claude["description"]),
        }
        key_mapping = [
            ("tools", "tools"),
            ("disallowed_tools", "disallowedTools"),
            ("model", "model"),
            ("max_turns", "maxTurns"),
            ("skills", "skills"),
            ("mcp_servers", "mcpServers"),
            ("hooks", "hooks"),
            ("memory", "memory"),
            ("background", "background"),
            ("effort", "effort"),
            ("isolation", "isolation"),
            ("color", "color"),
            ("initial_prompt", "initialPrompt"),
        ]
        for source_key, output_key in key_mapping:
            if source_key in claude:
                frontmatter[output_key] = claude[source_key]
        permission_mode = claude_permission_mode(agent, claude)
        if permission_mode is not None:
            frontmatter["permissionMode"] = permission_mode

        rendered = render_subagent(frontmatter, prompt_body)
        filename = f"{agent['agent']}.md"

        target_dirs: list[Path] = []
        if agent["scope"] == "global":
            target_dirs.append(global_agents_dir)
        else:
            for repo_name in agent["repos"]:
                repo_root_path = selected_repo_roots.get(str(repo_name))
                if repo_root_path:
                    target_dirs.append(Path(repo_root_path) / ".claude" / "agents")

        for target_dir in target_dirs:
            desired_files_by_dir.setdefault(target_dir, {})
            target_path = target_dir / filename
            rendered_path = temp_dir / (
                f"{hashlib.sha256((str(target_path) + ':subagent').encode()).hexdigest()}-{filename}"
            )
            rendered_path.write_text(rendered, encoding="utf-8")
            desired_files_by_dir[target_dir][filename] = target_path
            actions.append(
                RenderAction(
                    scope=str(target_dir),
                    kind="FILE",
                    target=target_path,
                    data=rendered_path,
                )
            )

    candidate_dirs = [global_agents_dir]
    for repo_root_path in selected_repo_roots.values():
        candidate_dirs.append(Path(repo_root_path) / ".claude" / "agents")

    for target_dir in candidate_dirs:
        desired_names = sorted(desired_files_by_dir.get(target_dir, {}).keys())
        manifest_path = target_dir / ".managed-subagents.json"
        previous_names = read_manifest(manifest_path)
        stale_names = sorted(set(previous_names) - set(desired_names))
        for stale_name in stale_names:
            actions.append(
                RenderAction(
                    scope=str(target_dir),
                    kind="CLEAN_FILE",
                    target=target_dir / stale_name,
                )
            )

        if desired_names:
            rendered_manifest_path = temp_dir / (
                f"{hashlib.sha256((str(manifest_path) + ':manifest').encode()).hexdigest()}-managed-subagents.json"
            )
            rendered_manifest_path.write_text(
                render_manifest(desired_names),
                encoding="utf-8",
            )
            actions.append(
                RenderAction(
                    scope=str(target_dir),
                    kind="FILE",
                    target=manifest_path,
                    data=rendered_manifest_path,
                )
            )
        elif previous_names:
            actions.append(
                RenderAction(
                    scope=str(target_dir),
                    kind="CLEAN_FILE",
                    target=manifest_path,
                )
            )

    return actions


def main() -> int:
    args = parse_args()
    repo_registry_path = Path(args.registry).expanduser().resolve()
    agent_registry_path = Path(args.agent_registry).expanduser().resolve()
    global_agents_dir = Path(args.global_agents_dir).expanduser().resolve()

    if not repo_registry_path.is_file():
        raise ControlPlaneError(f"Missing repo registry file: {repo_registry_path}")
    if not agent_registry_path.is_file():
        raise ControlPlaneError(f"Missing agent registry file: {agent_registry_path}")

    with tempfile.TemporaryDirectory() as temp_dir_raw:
        actions = build_actions(
            repo_registry_path=repo_registry_path,
            agent_registry_path=agent_registry_path,
            global_agents_dir=global_agents_dir,
            repo_filters=args.repo,
            temp_dir=Path(temp_dir_raw),
        )
        if not actions:
            raise ControlPlaneError("No managed Claude subagent operations were rendered.")

        print(
            f"Rendered {len(actions)} managed Claude subagent operations from {agent_registry_path}."
        )

        for action in actions:
            print("")
            print(f"=== Claude Subagent Item ({action.scope}) ===")
            if action.kind == "FILE":
                assert isinstance(action.data, Path)
                show_diff(action.target, action.data)
                if args.apply:
                    install_rendered_file(action.data, action.target, log=print)
            elif action.kind == "CLEAN_FILE":
                remove_managed_file(action.target, apply=args.apply, log=print)
            else:
                raise ControlPlaneError(f"Unknown manifest kind: {action.kind}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main_guard(main))
