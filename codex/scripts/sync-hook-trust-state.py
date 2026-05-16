#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    tomllib = None  # type: ignore[assignment]


EVENT_LABELS = {
    "PreToolUse": "pre_tool_use",
    "PermissionRequest": "permission_request",
    "PostToolUse": "post_tool_use",
    "PreCompact": "pre_compact",
    "SessionStart": "session_start",
    "UserPromptSubmit": "user_prompt_submit",
    "SessionEnd": "session_end",
    "Stop": "stop",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Trust Codex hooks rendered by the managed ~/.agents control plane."
    )
    parser.add_argument("--apply", action="store_true", help="write config.toml")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="show what would change without writing; this is the default",
    )
    parser.add_argument(
        "--global-config",
        default="~/.codex/config.toml",
        help="Codex config.toml to update",
    )
    parser.add_argument(
        "--global-hooks",
        default="~/.codex/hooks.json",
        help="managed global hooks.json",
    )
    parser.add_argument(
        "--registry",
        default="~/.agents/codex/config/repo-bootstrap.json",
        help="managed repo bootstrap registry",
    )
    parser.add_argument(
        "--repo",
        action="append",
        default=[],
        help="limit managed repo hook trust to this repo root; repeatable",
    )
    return parser.parse_args()


def expand(path: str) -> Path:
    return Path(path).expanduser().resolve()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_toml(path: Path) -> dict:
    if not path.is_file():
        return {}
    if tomllib is None:
        return {"hooks": {"state": parse_hook_state_toml_fallback(path)}}
    return tomllib.loads(path.read_text(encoding="utf-8"))


def unescape_toml_basic_string(value: str) -> str:
    result: list[str] = []
    idx = 0
    while idx < len(value):
        char = value[idx]
        if char != "\\":
            result.append(char)
            idx += 1
            continue
        idx += 1
        if idx >= len(value):
            result.append("\\")
            break
        escaped = value[idx]
        replacements = {
            "b": "\b",
            "t": "\t",
            "n": "\n",
            "f": "\f",
            "r": "\r",
            '"': '"',
            "\\": "\\",
        }
        result.append(replacements.get(escaped, escaped))
        idx += 1
    return "".join(result)


def parse_hook_state_table(line: str) -> str | None:
    prefix = '[hooks.state."'
    suffix = '"]'
    if not line.startswith(prefix) or not line.endswith(suffix):
        return None
    return unescape_toml_basic_string(line[len(prefix) : -len(suffix)])


def strip_inline_comment(value: str) -> str:
    in_string = False
    escaped = False
    for idx, char in enumerate(value):
        if escaped:
            escaped = False
            continue
        if char == "\\" and in_string:
            escaped = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if char == "#" and not in_string:
            return value[:idx].rstrip()
    return value.strip()


def parse_hook_state_toml_fallback(path: Path) -> dict[str, dict[str, object]]:
    """Parse the narrow TOML subset this script renders for hooks.state.

    Angie’s laptop can have an older Python without tomllib/tomli. The bootstrap
    should still be able to preserve existing hook trust state without requiring
    a local package install.
    """

    if not path.is_file():
        return {}

    state: dict[str, dict[str, object]] = {}
    current_key: str | None = None

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("["):
            current_key = parse_hook_state_table(line)
            if current_key is not None:
                state.setdefault(current_key, {})
            continue
        if current_key is None or "=" not in line:
            continue

        name, raw_value = line.split("=", 1)
        name = name.strip()
        value = strip_inline_comment(raw_value.strip())
        if name == "enabled":
            lowered = value.lower()
            if lowered in {"true", "false"}:
                state[current_key]["enabled"] = lowered == "true"
        elif name == "trusted_hash" and len(value) >= 2 and value[0] == '"' and value[-1] == '"':
            state[current_key]["trusted_hash"] = unescape_toml_basic_string(value[1:-1])

    return state


def hook_hash(event_label: str, group: dict, handler: dict) -> str:
    timeout = max(int(handler.get("timeout", 600)), 1)
    normalized_handler: dict[str, object] = {
        "type": "command",
        "command": handler["command"],
        "timeout": timeout,
        "async": bool(handler.get("async", False)),
    }
    if "statusMessage" in handler and handler["statusMessage"] is not None:
        normalized_handler["statusMessage"] = handler["statusMessage"]

    identity: dict[str, object] = {
        "event_name": event_label,
        "hooks": [normalized_handler],
    }
    matcher = group.get("matcher")
    if matcher is not None:
        identity["matcher"] = str(matcher)

    serialized = json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(serialized).hexdigest()


def hook_state_entries(hooks_path: Path) -> dict[str, str]:
    if not hooks_path.is_file():
        return {}
    data = load_json(hooks_path)
    hooks = data.get("hooks", {})
    if not isinstance(hooks, dict):
        raise SystemExit(f"ERROR: hooks root must be an object in {hooks_path}")

    entries: dict[str, str] = {}
    for event_name, groups in hooks.items():
        event_label = EVENT_LABELS.get(event_name)
        if event_label is None:
            continue
        if not isinstance(groups, list):
            raise SystemExit(f"ERROR: hooks.{event_name} must be a list in {hooks_path}")
        for group_index, group in enumerate(groups):
            if not isinstance(group, dict):
                raise SystemExit(f"ERROR: hooks.{event_name}[{group_index}] must be an object")
            handlers = group.get("hooks", [])
            if not isinstance(handlers, list):
                raise SystemExit(
                    f"ERROR: hooks.{event_name}[{group_index}].hooks must be a list"
                )
            for handler_index, handler in enumerate(handlers):
                if not isinstance(handler, dict):
                    raise SystemExit(
                        f"ERROR: hooks.{event_name}[{group_index}].hooks[{handler_index}] must be an object"
                    )
                if handler.get("type") != "command":
                    continue
                command = handler.get("command")
                if not isinstance(command, str) or not command.strip():
                    continue
                key = f"{hooks_path}:{event_label}:{group_index}:{handler_index}"
                entries[key] = hook_hash(event_label, group, handler)
    return entries


def registry_repo_paths(registry_path: Path, repo_filters: set[Path]) -> list[Path]:
    data = load_json(registry_path)
    repos = data.get("repos", [])
    if not isinstance(repos, list):
        raise SystemExit(f"ERROR: repos must be a list in {registry_path}")

    paths: list[Path] = []
    for item in repos:
        if not isinstance(item, dict):
            raise SystemExit(f"ERROR: repo entries must be objects in {registry_path}")
        raw_path = item.get("path")
        if not isinstance(raw_path, str) or not raw_path.strip():
            raise SystemExit(f"ERROR: repo.path must be a non-empty string in {registry_path}")
        repo_path = expand(raw_path)
        if repo_filters and repo_path not in repo_filters:
            continue
        paths.append(repo_path)
    return paths


def rendered_config_without_hook_state(config_path: Path) -> list[str]:
    if not config_path.is_file():
        return []
    lines = config_path.read_text(encoding="utf-8").splitlines()
    kept: list[str] = []
    idx = 0
    while idx < len(lines):
        line = lines[idx]
        if line == "[hooks.state]" or line.startswith("[hooks.state."):
            idx += 1
            while idx < len(lines):
                next_line = lines[idx]
                if next_line.startswith("[") and not next_line.startswith("[hooks.state"):
                    break
                idx += 1
            continue
        kept.append(line)
        idx += 1
    while kept and kept[-1] == "":
        kept.pop()
    return kept


def render_hook_state_block(
    existing_state: dict,
    managed_entries: dict[str, str],
    managed_prefixes: set[str],
) -> list[str]:
    merged: dict[str, dict[str, object]] = {}
    for key, value in sorted(existing_state.items()):
        if isinstance(value, dict):
            entry = dict(value)
        else:
            entry = {}
        if key not in managed_entries and not any(key.startswith(prefix) for prefix in managed_prefixes):
            merged[key] = entry
    for key, trusted_hash in sorted(managed_entries.items()):
        merged[key] = {"trusted_hash": trusted_hash}

    if not merged:
        return []
    lines = ["", "[hooks.state]"]
    for key, entry in sorted(merged.items()):
        lines.append("")
        escaped_key = key.replace("\\", "\\\\").replace('"', '\\"')
        lines.append(f'[hooks.state."{escaped_key}"]')
        if "enabled" in entry:
            lines.append(f"enabled = {'true' if bool(entry['enabled']) else 'false'}")
        trusted_hash = entry.get("trusted_hash")
        if isinstance(trusted_hash, str) and trusted_hash:
            lines.append(f'trusted_hash = "{trusted_hash}"')
    return lines


def main() -> int:
    args = parse_args()
    global_config = expand(args.global_config)
    global_hooks = expand(args.global_hooks)
    registry_path = expand(args.registry)
    repo_filters = {expand(path) for path in args.repo}

    managed_hook_paths = [global_hooks]
    managed_entries = hook_state_entries(global_hooks)
    for repo_path in registry_repo_paths(registry_path, repo_filters):
        hooks_path = repo_path / ".codex" / "hooks.json"
        managed_hook_paths.append(hooks_path)
        managed_entries.update(hook_state_entries(hooks_path))
    managed_prefixes = {f"{path}:" for path in managed_hook_paths}

    config = load_toml(global_config)
    existing_state = ((config.get("hooks") or {}).get("state") or {})
    if not isinstance(existing_state, dict):
        raise SystemExit(f"ERROR: hooks.state must be a table in {global_config}")

    base_lines = rendered_config_without_hook_state(global_config)
    next_lines = base_lines + render_hook_state_block(
        existing_state,
        managed_entries,
        managed_prefixes,
    )
    rendered = "\n".join(next_lines).rstrip() + "\n"
    current = global_config.read_text(encoding="utf-8") if global_config.is_file() else ""

    changed = current != rendered
    if args.apply:
        if changed:
            global_config.parent.mkdir(parents=True, exist_ok=True)
            global_config.write_text(rendered, encoding="utf-8")
            print(f"Updated hook trust state: {global_config}")
        else:
            print(f"No change: {global_config}")
    else:
        action = "would update" if changed else "no change"
        print(f"{action}: {global_config}")
    print(f"Trusted managed hooks: {len(managed_entries)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
