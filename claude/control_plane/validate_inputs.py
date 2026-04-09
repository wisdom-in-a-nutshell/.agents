from __future__ import annotations

import argparse
import json
from pathlib import Path

from .common import ControlPlaneError, main_guard


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate canonical Claude control-plane inputs."
    )
    parser.add_argument("--canonical-dir", required=True)
    parser.add_argument("--registry", required=True)
    parser.add_argument("--bootstrap", required=True)
    parser.add_argument("--mcp-registry", required=True)
    parser.add_argument("--skills-registry", required=True)
    parser.add_argument("--agent-registry", required=True)
    return parser.parse_args()


def _load_json_object(path: Path, *, label: str) -> dict:
    if not path.is_file():
        raise ControlPlaneError(f"missing required file: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ControlPlaneError(f"{label} root must be an object: {path}")
    return data


def main() -> int:
    args = parse_args()
    canonical_dir = Path(args.canonical_dir).expanduser().resolve()
    repo_registry = Path(args.registry).expanduser().resolve()
    bootstrap_file = Path(args.bootstrap).expanduser().resolve()
    mcp_registry = Path(args.mcp_registry).expanduser().resolve()
    skills_registry = Path(args.skills_registry).expanduser().resolve()
    agent_registry = Path(args.agent_registry).expanduser().resolve()

    global_claude = canonical_dir / "global.claude.md"
    settings_json = canonical_dir / "settings.json"
    for path in (
        global_claude,
        settings_json,
        repo_registry,
        bootstrap_file,
        mcp_registry,
        skills_registry,
        agent_registry,
    ):
        if not path.is_file():
            raise ControlPlaneError(f"missing required file: {path}")

    settings = _load_json_object(settings_json, label="settings")
    repo_data = _load_json_object(repo_registry, label="repo bootstrap")
    bootstrap_data = _load_json_object(bootstrap_file, label="Claude bootstrap")
    mcp_data = _load_json_object(mcp_registry, label="MCP registry")
    skills_data = _load_json_object(skills_registry, label="skills registry")
    agent_data = _load_json_object(agent_registry, label="agent registry")

    repos = repo_data.get("repos", [])
    if not isinstance(repos, list):
        raise ControlPlaneError(f"repos must be an array in {repo_registry}")

    defaults = bootstrap_data.get("defaults", {})
    if defaults is None:
        defaults = {}
    if not isinstance(defaults, dict):
        raise ControlPlaneError(f"defaults must be an object in {bootstrap_file}")

    default_settings = defaults.get("settings", {})
    if default_settings is not None and not isinstance(default_settings, dict):
        raise ControlPlaneError(f"defaults.settings must be an object in {bootstrap_file}")

    repo_overrides = bootstrap_data.get("repo_overrides", {})
    if repo_overrides is None:
        repo_overrides = {}
    if not isinstance(repo_overrides, dict):
        raise ControlPlaneError(f"repo_overrides must be an object in {bootstrap_file}")
    for repo_key, override in repo_overrides.items():
        if not isinstance(repo_key, str) or not repo_key.strip():
            raise ControlPlaneError(
                f"repo_overrides keys must be non-empty strings in {bootstrap_file}"
            )
        if override is None:
            continue
        if not isinstance(override, dict):
            raise ControlPlaneError(
                f"repo_overrides.{repo_key} must be an object in {bootstrap_file}"
            )

    presets = mcp_data.get("presets", {})
    global_presets = mcp_data.get("global_presets", [])
    if not isinstance(presets, dict):
        raise ControlPlaneError(f"presets must be an object in {mcp_registry}")
    if global_presets is None:
        global_presets = []
    if not isinstance(global_presets, list):
        raise ControlPlaneError(f"global_presets must be an array in {mcp_registry}")
    for preset_name, preset in presets.items():
        if not isinstance(preset, dict):
            raise ControlPlaneError(
                f"presets.{preset_name} must be an object in {mcp_registry}"
            )
        transport = preset.get("transport", preset.get("type"))
        if transport not in {"http", "stdio"}:
            raise ControlPlaneError(
                f"presets.{preset_name} must declare transport `http` or `stdio`"
            )
        if transport == "http" and not isinstance(preset.get("url"), str):
            raise ControlPlaneError(f"presets.{preset_name} must define a string url")
        if transport == "stdio" and not isinstance(preset.get("command"), str):
            raise ControlPlaneError(
                f"presets.{preset_name} must define a string command"
            )
    for preset_name in global_presets:
        if preset_name not in presets:
            raise ControlPlaneError(
                f"unknown global MCP preset `{preset_name}` in {mcp_registry}"
            )

    for idx, repo in enumerate(repos):
        if not isinstance(repo, dict):
            raise ControlPlaneError(f"repos[{idx}] must be an object")
        raw_path = repo.get("path")
        if not isinstance(raw_path, str) or not raw_path.strip():
            raise ControlPlaneError(f"repos[{idx}].path must be a non-empty string")
        preset_names = repo.get("mcp_presets", [])
        if preset_names is None:
            preset_names = []
        if not isinstance(preset_names, list):
            raise ControlPlaneError(f"repos[{idx}].mcp_presets must be an array")
        for preset_name in preset_names:
            if preset_name not in presets:
                raise ControlPlaneError(
                    f"unknown MCP preset `{preset_name}` in repos[{idx}]"
                )

    managed = skills_data.get("managed_skills", [])
    unmanaged = skills_data.get("unmanaged_repo_local_skills", [])
    if not isinstance(managed, list):
        raise ControlPlaneError(f"managed_skills must be an array in {skills_registry}")
    if not isinstance(unmanaged, list):
        raise ControlPlaneError(
            f"unmanaged_repo_local_skills must be an array in {skills_registry}"
        )

    managed_agents = agent_data.get("managed_agents", [])
    if not isinstance(managed_agents, list):
        raise ControlPlaneError(f"managed_agents must be an array in {agent_registry}")

    _ = settings
    return 0


if __name__ == "__main__":
    raise SystemExit(main_guard(main))
