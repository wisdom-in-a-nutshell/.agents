#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
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


def expand_path(raw: str, home: Path) -> Path:
    if raw.startswith("~/"):
        return home / raw[2:]
    return Path(raw)


def _yaml_str(value: str) -> str:
    return json.dumps(value)


def _write_if_changed(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    old = path.read_text(encoding="utf-8") if path.exists() else None
    if old != content:
        path.write_text(content, encoding="utf-8")


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


def generate_registry_base(config_dir: Path) -> None:
    content = """filters:
  and:
    - 'file.inFolder("codex/config/repo-bootstrap-items")'
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
  effective_service_tier:
    displayName: Service Tier
  notes:
    displayName: Notes
views:
  - type: table
    name: Repo Bootstrap
    order:
      - repo_name
      - mcp_presets_csv
      - effective_model
      - effective_reasoning
      - effective_service_tier
      - notes
  - type: table
    name: MCP Enabled
    filters: 'mcp_presets_csv != "-"'
    order:
      - repo_name
      - mcp_presets_csv
      - effective_model
      - effective_reasoning
      - effective_service_tier
"""
    _write_if_changed(config_dir / "repo-bootstrap.base", content)


def generate_registry_items(
    config_dir: Path, defaults: dict[str, Any], repos: list[dict[str, Any]]
) -> None:
    root = config_dir / "repo-bootstrap-items"
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
            f"effective_service_tier: {_yaml_str(_effective_value(defaults, item, 'service_tier'))}",
            f"notes: {_yaml_str(item.get('notes', '-'))}",
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


def validate_registry(
    data: dict[str, Any], config_dir: Path, home: Path
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    defaults = data.get("defaults", {})
    if not isinstance(defaults, dict):
      raise ValueError("defaults must be an object")

    for key in defaults:
        if key not in ALLOWED_SCALAR_KEYS:
            raise ValueError(f"unsupported default key: {key}")

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
            "path": str(repo_root),
            "repo_name": _repo_name(str(repo_root)),
            "mcp_presets": [str(name) for name in mcp_presets],
            "mcp_presets_csv": ",".join(mcp_presets) if mcp_presets else "-",
            "notes": str(item.get("notes", "-")).strip() or "-",
        }
        for key in ALLOWED_SCALAR_KEYS:
            if key in item:
                validated[key] = item[key]
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
    home = Path.home()
    try:
        defaults, presets, repos = validate_registry(data, config_dir, home)
    except ValueError as exc:
        print(f"Registry validation failed: {exc}", file=sys.stderr)
        return 1

    generate_registry_base(config_dir)
    generate_registry_items(config_dir, defaults, repos)
    print(f"Generated repo bootstrap Base artifacts in {config_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
