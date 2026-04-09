from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

ALLOWED_SCOPES = {"global", "repo"}
ALLOWED_ACCESS_PROFILES = {"read_only", "workspace_write", "full_access"}
CLAUDE_OPTIONAL_KEYS = {
    "background",
    "color",
    "description",
    "disallowed_tools",
    "effort",
    "hooks",
    "initial_prompt",
    "isolation",
    "max_turns",
    "mcp_servers",
    "memory",
    "model",
    "name",
    "permission_mode",
    "prompt_file",
    "skills",
    "tools",
}


def _validate_agent_id(value: str) -> str:
    agent_id = value.strip()
    if not agent_id:
        raise ValueError("agent id must be a non-empty string")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", agent_id):
        raise ValueError(
            f"agent id `{agent_id}` must use lowercase letters, digits, and hyphens"
        )
    return agent_id


def _ordered_unique_strings(values: list[Any], *, label: str) -> list[str]:
    ordered: list[str] = []
    for value in values:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{label} entries must be non-empty strings")
        item = value.strip()
        if item not in ordered:
            ordered.append(item)
    return ordered


def load_agent_registry(
    registry_path: Path,
    *,
    root_dir: Path,
    valid_repo_names: set[str] | None = None,
) -> list[dict[str, Any]]:
    data = json.loads(registry_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"agent registry root must be an object: {registry_path}")

    version = data.get("version")
    if version != 1:
        raise ValueError(f"agent registry version must be 1 in {registry_path}")

    agents = data.get("managed_agents", [])
    if not isinstance(agents, list) or not agents:
        raise ValueError(f"managed_agents must be a non-empty array in {registry_path}")

    normalized: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for idx, item in enumerate(agents):
        if not isinstance(item, dict):
            raise ValueError(f"managed_agents[{idx}] must be an object")

        agent_id = _validate_agent_id(str(item.get("agent", "")))
        if agent_id in seen_ids:
            raise ValueError(f"duplicate managed agent id `{agent_id}` in {registry_path}")
        seen_ids.add(agent_id)

        description = str(item.get("description", "")).strip()
        if not description:
            raise ValueError(f"managed_agents[{idx}].description must be a non-empty string")

        scope = str(item.get("scope", "")).strip()
        if scope not in ALLOWED_SCOPES:
            raise ValueError(f"managed_agents[{idx}].scope must be one of {sorted(ALLOWED_SCOPES)}")

        repos_raw = item.get("repos", [])
        if repos_raw is None:
            repos_raw = []
        if not isinstance(repos_raw, list):
            raise ValueError(f"managed_agents[{idx}].repos must be an array")
        repos = _ordered_unique_strings(repos_raw, label=f"managed_agents[{idx}].repos")
        if scope == "global" and repos:
            raise ValueError(f"managed_agents[{idx}] is global and must not define repos")
        if scope == "repo" and not repos:
            raise ValueError(f"managed_agents[{idx}] is repo-scoped and must define repos")
        if valid_repo_names is not None:
            unknown = [repo for repo in repos if repo not in valid_repo_names]
            if unknown:
                raise ValueError(
                    f"managed_agents[{idx}] references unknown repos: {', '.join(sorted(unknown))}"
                )

        access_profile = str(item.get("access_profile", "")).strip()
        if access_profile not in ALLOWED_ACCESS_PROFILES:
            raise ValueError(
                f"managed_agents[{idx}].access_profile must be one of {sorted(ALLOWED_ACCESS_PROFILES)}"
            )

        codex_raw = item.get("codex")
        claude_raw = item.get("claude")

        codex: dict[str, Any] | None = None
        if codex_raw is not None:
            if not isinstance(codex_raw, dict):
                raise ValueError(f"managed_agents[{idx}].codex must be an object")
            materialize = bool(codex_raw.get("materialize", True))
            if materialize:
                config_file = str(codex_raw.get("config_file", "")).strip()
                if not config_file:
                    raise ValueError(f"managed_agents[{idx}].codex.config_file must be a non-empty string")
                nickname_candidates = codex_raw.get("nickname_candidates", [])
                if nickname_candidates is None:
                    nickname_candidates = []
                if not isinstance(nickname_candidates, list) or any(
                    not isinstance(value, str) for value in nickname_candidates
                ):
                    raise ValueError(
                        f"managed_agents[{idx}].codex.nickname_candidates must be an array of strings"
                    )
                codex_name = str(codex_raw.get("name", agent_id.replace("-", "_"))).strip()
                if not codex_name:
                    raise ValueError(f"managed_agents[{idx}].codex.name must be a non-empty string")
                codex = {
                    "materialize": True,
                    "name": codex_name,
                    "config_file": config_file,
                    "description": str(codex_raw.get("description", description)).strip() or description,
                    "nickname_candidates": [str(value) for value in nickname_candidates],
                    "source_path": root_dir / "codex" / "config" / "agents" / config_file,
                }
            else:
                codex = {"materialize": False}

        claude: dict[str, Any] | None = None
        if claude_raw is not None:
            if not isinstance(claude_raw, dict):
                raise ValueError(f"managed_agents[{idx}].claude must be an object")
            unknown_keys = sorted(set(claude_raw) - (CLAUDE_OPTIONAL_KEYS | {"materialize"}))
            if unknown_keys:
                raise ValueError(
                    f"managed_agents[{idx}].claude contains unsupported keys: {', '.join(unknown_keys)}"
                )
            materialize = bool(claude_raw.get("materialize", True))
            if materialize:
                prompt_file = str(claude_raw.get("prompt_file", "")).strip()
                if not prompt_file:
                    raise ValueError(f"managed_agents[{idx}].claude.prompt_file must be a non-empty string")
                claude_name = str(claude_raw.get("name", agent_id)).strip()
                if not claude_name:
                    raise ValueError(f"managed_agents[{idx}].claude.name must be a non-empty string")
                claude = {
                    "materialize": True,
                    "name": claude_name,
                    "description": str(claude_raw.get("description", description)).strip() or description,
                    "prompt_file": prompt_file,
                    "source_path": root_dir / "claude" / "config" / "agents" / prompt_file,
                }
                for key in sorted(CLAUDE_OPTIONAL_KEYS - {"description", "name", "prompt_file"}):
                    if key in claude_raw:
                        claude[key] = claude_raw[key]
            else:
                claude = {"materialize": False}

        if not (codex and codex.get("materialize")) and not (claude and claude.get("materialize")):
            raise ValueError(f"managed_agents[{idx}] must materialize in at least one runtime")

        normalized.append(
            {
                "agent": agent_id,
                "description": description,
                "scope": scope,
                "repos": repos,
                "access_profile": access_profile,
                "codex": codex,
                "claude": claude,
            }
        )

    return normalized

