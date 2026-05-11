from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


ALLOWED_SCOPES = {"global", "repo", "dormant"}


@dataclass(frozen=True)
class ManagedPlugin:
    plugin: str
    marketplace: str
    enabled: bool
    category: str
    scope: str
    repos: tuple[str, ...]

    @property
    def plugin_id(self) -> str:
        return f"{self.plugin}@{self.marketplace}"


def expand_path(raw: str, home: Path) -> Path:
    if raw.startswith("~/"):
        return home / raw[2:]
    return Path(raw)


def resolve_repo_root(repo: str, github_root: Path, home: Path) -> Path:
    if repo.startswith("~/") or repo.startswith("/"):
        return expand_path(repo, home).resolve()
    return (github_root / repo).resolve()


def ensure_str(value: Any, field: str, idx: int, *, label: str = "managed_plugins") -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label}[{idx}] invalid {field}: {value!r}")
    return value.strip()


def validate_plugin_registry(
    data: dict[str, Any],
    *,
    root_dir: Path,
    home: Path,
) -> tuple[list[ManagedPlugin], list[dict[str, str]], Path]:
    managed = data.get("managed_plugins", [])
    if not isinstance(managed, list):
        raise ValueError("managed_plugins must be an array")

    unmanaged = data.get("unmanaged_repo_local_plugins", [])
    if not isinstance(unmanaged, list):
        raise ValueError("unmanaged_repo_local_plugins must be an array")

    paths = data.get("paths", {})
    if not isinstance(paths, dict):
        raise ValueError("paths must be an object")

    github_root_raw = str(paths.get("github_root", "~/GitHub")).strip()
    if not github_root_raw:
        raise ValueError("paths.github_root must be a non-empty string")
    github_root = expand_path(github_root_raw, home).resolve()

    seen_plugins: set[str] = set()
    validated_managed: list[ManagedPlugin] = []
    for idx, item in enumerate(managed):
        if not isinstance(item, dict):
            raise ValueError(f"managed_plugins[{idx}] must be an object")

        plugin = ensure_str(item.get("plugin"), "plugin", idx)
        marketplace = ensure_str(item.get("marketplace"), "marketplace", idx)
        category = str(item.get("category", "")).strip() or "Coding"
        enabled = item.get("enabled", True)
        if not isinstance(enabled, bool):
            raise ValueError(f"managed_plugins[{idx}] enabled must be a boolean")
        scope = str(item.get("scope", "global")).strip() or "global"
        if scope not in ALLOWED_SCOPES:
            raise ValueError(f"managed_plugins[{idx}] invalid scope: {scope}")

        repos_raw = item.get("repos", [])
        if not isinstance(repos_raw, list):
            raise ValueError(f"managed_plugins[{idx}] repos must be an array")
        repos: list[str] = []
        for repo in repos_raw:
            repo_ref = str(repo).strip()
            if repo_ref and repo_ref not in repos:
                repos.append(repo_ref)
        if scope == "repo" and not repos:
            raise ValueError(f"managed_plugins[{idx}] repo scope needs repos")
        if scope in {"global", "dormant"}:
            repos = []
        if scope == "dormant" and enabled:
            raise ValueError(f"managed_plugins[{idx}] dormant scope must be disabled")

        if "targets" in item:
            raise ValueError(
                f"managed_plugins[{idx}] targets is no longer supported; "
                "use scope/repos for global, repo-local, or dormant native Codex plugins"
            )

        plugin_id = f"{plugin}@{marketplace}"
        if plugin_id in seen_plugins:
            raise ValueError(f"duplicate managed plugin: {plugin_id}")
        seen_plugins.add(plugin_id)

        validated_managed.append(
            ManagedPlugin(
                plugin=plugin,
                marketplace=marketplace,
                enabled=enabled,
                category=category,
                scope=scope,
                repos=tuple(repos),
            )
        )

    validated_unmanaged: list[dict[str, str]] = []
    for idx, item in enumerate(unmanaged):
        if not isinstance(item, dict):
            raise ValueError(f"unmanaged_repo_local_plugins[{idx}] must be an object")
        repo = ensure_str(item.get("repo"), "repo", idx, label="unmanaged_repo_local_plugins")
        plugin = ensure_str(
            item.get("plugin"), "plugin", idx, label="unmanaged_repo_local_plugins"
        )
        validated_unmanaged.append({"repo": repo, "plugin": plugin})

    return validated_managed, validated_unmanaged, github_root
