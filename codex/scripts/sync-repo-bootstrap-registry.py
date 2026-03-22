#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any


ALLOWED_SCALAR_KEYS = {
    "model",
    "model_reasoning_effort",
    "service_tier",
    "profile",
    "model_reasoning_summary",
    "model_verbosity",
    "model_instructions_file",
    "project_root_markers",
    "web_search",
    "approval_policy",
    "sandbox_mode",
    "personality",
}
ALLOWED_DEFAULT_TABLE_KEYS = {
    "features",
}


def expand_path(raw: str, home: Path) -> Path:
    if raw.startswith("~/"):
        return home / raw[2:]
    return Path(raw)


def _yaml_str(value: str) -> str:
    return json.dumps(value)


def _display_path(path: Path, home: Path) -> str:
    try:
        rel = path.relative_to(home)
    except ValueError:
        return str(path)
    if not rel.parts:
        return "~"
    return f"~/{rel.as_posix()}"


def _write_if_changed(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    old = path.read_text(encoding="utf-8") if path.exists() else None
    if old != content:
        path.write_text(content, encoding="utf-8")


def generated_views_dir(root_dir: Path) -> Path:
    return root_dir / "docs" / "references" / "registry"


def _sanitize_file_name(name: str) -> str:
    safe = []
    for ch in name:
        if ch.isalnum() or ch in {"-", "_", "."}:
            safe.append(ch)
        else:
            safe.append("-")
    return "".join(safe).strip("-")


def _repo_name(path: str) -> str:
    return Path(path).name or path


def _effective_value(defaults: dict[str, Any], item: dict[str, Any], key: str) -> str:
    value = item.get(key, defaults.get(key))
    if value is None:
        return "-"
    return str(value)


def _effective_fast_mode(defaults: dict[str, Any], item: dict[str, Any]) -> str:
    default_features = defaults.get("features", {})
    item_features = item.get("features", {})
    if default_features and not isinstance(default_features, dict):
        return "-"
    if item_features and not isinstance(item_features, dict):
        return "-"
    merged = dict(default_features)
    merged.update(item_features)
    if "fast_mode" not in merged:
        return "-"
    return str(merged["fast_mode"]).lower()


def generate_registry_base(views_dir: Path) -> None:
    content = """filters:
  and:
    - 'file.inFolder("docs/references/registry/repo-bootstrap-items")'
properties:
  repo_name:
    displayName: Repo
  path:
    displayName: Path
  mcp_presets_csv:
    displayName: MCP Presets
  effective_model:
    displayName: Model
  effective_reasoning:
    displayName: Reasoning
  effective_fast_mode:
    displayName: Fast Mode
  effective_service_tier:
    displayName: Service Tier
views:
  - type: table
    name: Repo Bootstrap
    order:
      - repo_name
      - mcp_presets_csv
      - effective_model
      - effective_reasoning
      - effective_fast_mode
      - effective_service_tier
  - type: table
    name: MCP Enabled
    filters: 'mcp_presets_csv != "-"'
    order:
      - repo_name
      - mcp_presets_csv
      - effective_model
      - effective_reasoning
      - effective_fast_mode
      - effective_service_tier
"""
    _write_if_changed(views_dir / "repo-bootstrap.base", content)


def generate_registry_items(
    views_dir: Path, defaults: dict[str, Any], repos: list[dict[str, Any]]
) -> None:
    root = views_dir / "repo-bootstrap-items"
    shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True, exist_ok=True)

    for item in repos:
        file_name = f"{_sanitize_file_name(item['repo_name'])}.md"
        lines = [
            "---",
            f"repo_name: {_yaml_str(item['repo_name'])}",
            f"path: {_yaml_str(item['path'])}",
            f"mcp_presets_csv: {_yaml_str(item['mcp_presets_csv'])}",
            f"effective_model: {_yaml_str(_effective_value(defaults, item, 'model'))}",
            f"effective_reasoning: {_yaml_str(_effective_value(defaults, item, 'model_reasoning_effort'))}",
            f"effective_fast_mode: {_yaml_str(_effective_fast_mode(defaults, item))}",
            f"effective_service_tier: {_yaml_str(_effective_value(defaults, item, 'service_tier'))}",
            "mcp_presets:",
        ]
        if item["mcp_presets"]:
            lines.extend([f"  - {_yaml_str(name)}" for name in item["mcp_presets"]])
        else:
            lines.append('  - "-"')
        lines.extend(
            [
                "---",
                "",
                "Generated from `codex/config/repo-bootstrap.json`. Do not edit manually.",
                "",
            ]
        )
        _write_if_changed(root / file_name, "\n".join(lines))


def _load_global_mcp_names(config_path: Path) -> set[str]:
    if not config_path.is_file():
        return set()
    with config_path.open("rb") as handle:
        data = tomllib.load(handle)
    mcp_servers = data.get("mcp_servers", {})
    if not isinstance(mcp_servers, dict):
        return set()
    return {str(name) for name in mcp_servers.keys()}


def _mcp_transport(preset: dict[str, Any]) -> str:
    if "url" in preset:
        return "url"
    if "command" in preset:
        return "command"
    return "-"


def _mcp_target(preset: dict[str, Any]) -> str:
    if "url" in preset:
        return str(preset["url"])
    if "command" in preset:
        args = preset.get("args", [])
        if isinstance(args, list) and args:
            return " ".join([str(preset["command"]), *[str(arg) for arg in args]])
        return str(preset["command"])
    return "-"


def _mcp_scope(global_terminal: bool, global_xcode: bool, repos: list[str]) -> str:
    has_global = global_terminal or global_xcode
    has_repos = bool(repos)
    if has_global and has_repos:
        return "mixed"
    if has_global:
        return "global"
    if has_repos:
        return "repo"
    return "-"


def generate_mcp_registry_base(views_dir: Path) -> None:
    content = """filters:
  and:
    - 'file.inFolder("docs/references/registry/mcp-registry-items")'
properties:
  mcp_name:
    displayName: MCP
  effective_scope:
    displayName: Scope
  global_terminal:
    displayName: Global Terminal
  global_xcode:
    displayName: Global Xcode
  repos_csv:
    displayName: Repos
  transport:
    displayName: Transport
  target:
    displayName: Target
views:
  - type: table
    name: MCP Registry
    order:
      - mcp_name
      - effective_scope
      - global_terminal
      - global_xcode
      - repos_csv
      - transport
      - target
  - type: table
    name: Global MCPs
    filters: 'global_terminal == "true" || global_xcode == "true"'
    order:
      - mcp_name
      - effective_scope
      - global_terminal
      - global_xcode
      - repos_csv
      - transport
      - target
  - type: table
    name: Repo MCPs
    filters: 'repos_csv != "-"'
    order:
      - mcp_name
      - effective_scope
      - repos_csv
      - transport
      - target
"""
    _write_if_changed(views_dir / "mcp-registry.base", content)


def generate_mcp_registry_items(
    views_dir: Path,
    presets: dict[str, Any],
    repos: list[dict[str, Any]],
    global_terminal_mcp: set[str],
    global_xcode_mcp: set[str],
) -> None:
    root = views_dir / "mcp-registry-items"
    shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True, exist_ok=True)

    repo_usage: dict[str, list[str]] = {name: [] for name in presets}
    for item in repos:
        for preset_name in item["mcp_presets"]:
            repo_usage.setdefault(preset_name, []).append(item["repo_name"])

    for preset_name in sorted(presets):
        preset = presets[preset_name]
        repos_for_preset = sorted(repo_usage.get(preset_name, []))
        global_terminal = preset_name in global_terminal_mcp
        global_xcode = preset_name in global_xcode_mcp
        lines = [
            "---",
            f"mcp_name: {_yaml_str(preset_name)}",
            f"effective_scope: {_yaml_str(_mcp_scope(global_terminal, global_xcode, repos_for_preset))}",
            f"global_terminal: {_yaml_str(str(global_terminal).lower())}",
            f"global_xcode: {_yaml_str(str(global_xcode).lower())}",
            f"repos_csv: {_yaml_str(','.join(repos_for_preset) if repos_for_preset else '-')}",
            f"transport: {_yaml_str(_mcp_transport(preset))}",
            f"target: {_yaml_str(_mcp_target(preset))}",
            "repos:",
        ]
        if repos_for_preset:
            lines.extend([f"  - {_yaml_str(repo_name)}" for repo_name in repos_for_preset])
        else:
            lines.append('  - "-"')
        lines.extend(
            [
                "---",
                "",
                "Generated from `codex/config/repo-bootstrap.json` plus the managed global Codex config templates. Do not edit manually.",
                "",
            ]
        )
        _write_if_changed(root / f"{_sanitize_file_name(preset_name)}.md", "\n".join(lines))


def validate_registry(
    data: dict[str, Any], config_dir: Path, home: Path
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    defaults = data.get("defaults", {})
    if not isinstance(defaults, dict):
      raise ValueError("defaults must be an object")

    for key in defaults:
        if key not in ALLOWED_SCALAR_KEYS and key not in ALLOWED_DEFAULT_TABLE_KEYS:
            raise ValueError(f"unsupported default key: {key}")
    if "features" in defaults and not isinstance(defaults["features"], dict):
        raise ValueError("defaults.features must be an object")

    presets = data.get("mcp_presets", {})
    if not isinstance(presets, dict):
        raise ValueError("mcp_presets must be an object")

    repos_raw = data.get("repos")
    if not isinstance(repos_raw, list) or not repos_raw:
        raise ValueError("repos must be a non-empty array")

    seen: set[str] = set()
    repos: list[dict[str, Any]] = []
    for idx, item in enumerate(repos_raw):
        if not isinstance(item, dict):
            raise ValueError(f"repos[{idx}] must be an object")
        raw_path = item.get("path")
        if not isinstance(raw_path, str) or not raw_path.strip():
            raise ValueError(f"repos[{idx}].path must be a non-empty string")
        path_str = raw_path.strip()
        repo_path = expand_path(path_str, home).resolve()
        if str(repo_path) in seen:
            raise ValueError(f"duplicate repo path: {path_str}")
        seen.add(str(repo_path))

        repo_root = repo_path
        try:
            repo_root_out = subprocess.run(
                ["git", "-C", str(repo_path), "rev-parse", "--show-toplevel"],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            repo_root = Path(repo_root_out).resolve()
        except subprocess.CalledProcessError:
            print(f"WARNING: skipping non-git path: {path_str}", file=sys.stderr)
            continue

        mcp_presets = item.get("mcp_presets", [])
        if not isinstance(mcp_presets, list):
            raise ValueError(f"repos[{idx}].mcp_presets must be an array")
        for preset_name in mcp_presets:
            if preset_name not in presets:
                raise ValueError(
                    f"repos[{idx}] references unknown MCP preset: {preset_name}"
                )

        validated = {
            "path": _display_path(repo_root, home),
            "repo_name": _repo_name(str(repo_root)),
            "mcp_presets": [str(name) for name in mcp_presets],
            "mcp_presets_csv": ",".join(mcp_presets) if mcp_presets else "-",
        }
        for key in ALLOWED_SCALAR_KEYS:
            if key in item:
                validated[key] = item[key]
        if "features" in item:
            if not isinstance(item["features"], dict):
                raise ValueError(f"repos[{idx}].features must be an object")
            validated["features"] = item["features"]
        repos.append(validated)

    repos.sort(key=lambda item: item["path"])
    return defaults, presets, repos


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate Obsidian Base artifacts for the Codex repo bootstrap registry."
    )
    parser.add_argument(
        "registry_file",
        nargs="?",
        default=str(Path.home() / ".agents" / "codex" / "config" / "repo-bootstrap.json"),
        help="Path to repo bootstrap registry JSON file.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    registry_file = Path(args.registry_file).expanduser().resolve()
    if not registry_file.is_file():
        print(f"Registry not found: {registry_file}", file=sys.stderr)
        return 1

    try:
        data = json.loads(registry_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"Invalid JSON in {registry_file}: {exc}", file=sys.stderr)
        return 1

    config_dir = registry_file.parent
    root_dir = config_dir.parent.parent
    home = Path.home()
    try:
        defaults, presets, repos = validate_registry(data, config_dir, home)
    except ValueError as exc:
        print(f"Registry validation failed: {exc}", file=sys.stderr)
        return 1

    views_dir = generated_views_dir(root_dir)
    generate_registry_base(views_dir)
    generate_registry_items(views_dir, defaults, repos)
    global_terminal_mcp = _load_global_mcp_names(config_dir / "global.config.toml")
    global_xcode_mcp = _load_global_mcp_names(config_dir / "xcode.config.toml")
    generate_mcp_registry_base(views_dir)
    generate_mcp_registry_items(
        views_dir, presets, repos, global_terminal_mcp, global_xcode_mcp
    )
    print(f"Generated repo bootstrap Base artifacts in {views_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
