from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


MCP_CLIENTS = ("codex", "claude", "copilot")
_PRESET_KEYS = {"args", "command", "cwd", "env", "targets", "transport", "url"}
_TARGET_KEYS = {"clients", "repos"}


class McpRegistryError(ValueError):
    """Raised when the canonical MCP catalog cannot be rendered safely."""


@dataclass(frozen=True)
class McpTarget:
    clients: tuple[str, ...]
    repos: tuple[str, ...]
    all_clients: bool
    all_repos: bool

    def as_dict(self) -> dict[str, str | list[str]]:
        return {
            "clients": "all" if self.all_clients else list(self.clients),
            "repos": "all" if self.all_repos else list(self.repos),
        }


@dataclass(frozen=True)
class McpCatalog:
    definitions: dict[str, dict[str, Any]]
    targets: dict[str, tuple[McpTarget, ...]]
    repo_paths: tuple[str, ...]
    repo_clients: dict[str, dict[str, tuple[str, ...]]]

    def presets_for(self, repo: str, client: str) -> list[tuple[str, dict[str, Any]]]:
        _require_client(client)
        assignments = self.repo_clients.get(repo, {})
        return [
            (name, self.definitions[name])
            for name in sorted(assignments)
            if client in assignments[name]
        ]

    def clients_for(self, preset: str, repo: str) -> tuple[str, ...]:
        return self.repo_clients.get(repo, {}).get(preset, ())

    def repos_for(self, preset: str, client: str | None = None) -> list[str]:
        if client is not None:
            _require_client(client)
        return [
            repo
            for repo in self.repo_paths
            if preset in self.repo_clients.get(repo, {})
            and (client is None or client in self.repo_clients[repo][preset])
        ]

    def clients_used_by(self, preset: str) -> list[str]:
        return [
            client
            for client in MCP_CLIENTS
            if any(client in self.clients_for(preset, repo) for repo in self.repo_paths)
        ]

    def global_clients_used_by(self, preset: str) -> list[str]:
        return [
            client
            for client in MCP_CLIENTS
            if any(
                target.all_repos and client in target.clients
                for target in self.targets.get(preset, ())
            )
        ]

    def exclusive_global_presets_for(
        self,
        client: str,
    ) -> list[tuple[str, dict[str, Any]]]:
        """Presets globally assigned to exactly one client.

        These can use a client-native user surface without widening availability
        to another runtime. Shared multi-client targets continue to render through
        project surfaces.
        """
        _require_client(client)
        return [
            (name, self.definitions[name])
            for name in sorted(self.definitions)
            if any(
                target.all_repos and target.clients == (client,)
                for target in self.targets.get(name, ())
            )
        ]

    def target_dicts(self, preset: str) -> list[dict[str, str | list[str]]]:
        return [target.as_dict() for target in self.targets.get(preset, ())]


def _require_client(client: str) -> None:
    if client not in MCP_CLIENTS:
        raise McpRegistryError(
            f"unknown MCP client `{client}`; expected one of: {', '.join(MCP_CLIENTS)}"
        )


def _ordered_unique(values: Iterable[str]) -> tuple[str, ...]:
    result: list[str] = []
    for value in values:
        if value not in result:
            result.append(value)
    return tuple(result)


def _client_selector(value: Any, label: str) -> tuple[tuple[str, ...], bool]:
    if value == "all":
        return MCP_CLIENTS, True
    if not isinstance(value, list) or not value:
        raise McpRegistryError(f"{label}.clients must be `all` or a non-empty array")
    if not all(isinstance(item, str) and item.strip() for item in value):
        raise McpRegistryError(f"{label}.clients must contain non-empty strings")
    clients = _ordered_unique(item.strip() for item in value)
    unknown = sorted(set(clients) - set(MCP_CLIENTS))
    if unknown:
        raise McpRegistryError(
            f"{label}.clients contains unsupported clients: {', '.join(unknown)}"
        )
    return clients, False


def _repo_selector(
    value: Any,
    label: str,
    repo_paths: tuple[str, ...],
) -> tuple[tuple[str, ...], bool]:
    if value == "all":
        return repo_paths, True
    if not isinstance(value, list) or not value:
        raise McpRegistryError(f"{label}.repos must be `all` or a non-empty array")
    if not all(isinstance(item, str) and item.strip() for item in value):
        raise McpRegistryError(f"{label}.repos must contain non-empty strings")
    repos = _ordered_unique(item.strip() for item in value)
    unknown = [repo for repo in repos if repo not in repo_paths]
    if unknown:
        raise McpRegistryError(
            f"{label}.repos references repos missing from repo-bootstrap.json: {', '.join(unknown)}"
        )
    return repos, False


def _validate_definition(name: str, raw: Any) -> tuple[dict[str, Any], Any]:
    label = f"presets.{name}"
    if not isinstance(raw, dict):
        raise McpRegistryError(f"{label} must be an object")
    unknown = sorted(set(raw) - _PRESET_KEYS)
    if unknown:
        raise McpRegistryError(f"{label} has unsupported keys: {', '.join(unknown)}")

    transport = raw.get("transport")
    if transport not in {"http", "stdio"}:
        raise McpRegistryError(f"{label}.transport must be `http` or `stdio`")
    if transport == "http":
        if not isinstance(raw.get("url"), str) or not raw["url"].strip():
            raise McpRegistryError(f"{label}.url must be a non-empty string")
        forbidden = sorted(key for key in ("args", "command", "cwd", "env") if key in raw)
        if forbidden:
            raise McpRegistryError(
                f"{label} http transport must not set: {', '.join(forbidden)}"
            )
    else:
        if not isinstance(raw.get("command"), str) or not raw["command"].strip():
            raise McpRegistryError(f"{label}.command must be a non-empty string")
        if "url" in raw:
            raise McpRegistryError(f"{label} stdio transport must not set url")
        args = raw.get("args", [])
        if not isinstance(args, list) or not all(isinstance(item, str) for item in args):
            raise McpRegistryError(f"{label}.args must be an array of strings")
        env = raw.get("env", {})
        if not isinstance(env, dict) or not all(
            isinstance(key, str) and isinstance(value, str) for key, value in env.items()
        ):
            raise McpRegistryError(f"{label}.env must be an object of string values")
        if "cwd" in raw and (not isinstance(raw["cwd"], str) or not raw["cwd"].strip()):
            raise McpRegistryError(f"{label}.cwd must be a non-empty string")

    definition = {key: value for key, value in raw.items() if key != "targets"}
    return definition, raw.get("targets")


def load_mcp_catalog_data(data: Any, repo_entries: Any) -> McpCatalog:
    if not isinstance(data, dict):
        raise McpRegistryError("MCP registry root must be an object")
    unknown_root = sorted(set(data) - {"version", "presets"})
    if unknown_root:
        raise McpRegistryError(
            "MCP registry has unsupported top-level keys: " + ", ".join(unknown_root)
        )
    if data.get("version") != 2:
        raise McpRegistryError("MCP registry version must be 2")
    presets = data.get("presets")
    if not isinstance(presets, dict):
        raise McpRegistryError("MCP registry presets must be an object")
    if not isinstance(repo_entries, list) or not repo_entries:
        raise McpRegistryError("repo-bootstrap repos must be a non-empty array")

    repo_paths: list[str] = []
    for idx, entry in enumerate(repo_entries):
        if not isinstance(entry, dict):
            raise McpRegistryError(f"repo-bootstrap repos[{idx}] must be an object")
        path = entry.get("path")
        if not isinstance(path, str) or not path.strip():
            raise McpRegistryError(
                f"repo-bootstrap repos[{idx}].path must be a non-empty string"
            )
        normalized = path.strip()
        if normalized in repo_paths:
            raise McpRegistryError(f"duplicate repo-bootstrap path: {normalized}")
        repo_paths.append(normalized)
    repo_path_tuple = tuple(repo_paths)

    definitions: dict[str, dict[str, Any]] = {}
    targets: dict[str, tuple[McpTarget, ...]] = {}
    mutable_repo_clients: dict[str, dict[str, set[str]]] = {
        repo: {} for repo in repo_path_tuple
    }

    for raw_name, raw_definition in presets.items():
        name = str(raw_name).strip()
        if not name:
            raise McpRegistryError("MCP preset names must be non-empty strings")
        definition, raw_targets = _validate_definition(name, raw_definition)
        if not isinstance(raw_targets, list):
            raise McpRegistryError(f"presets.{name}.targets must be an array")

        parsed_targets: list[McpTarget] = []
        for idx, raw_target in enumerate(raw_targets):
            label = f"presets.{name}.targets[{idx}]"
            if not isinstance(raw_target, dict):
                raise McpRegistryError(f"{label} must be an object")
            unknown = sorted(set(raw_target) - _TARGET_KEYS)
            if unknown:
                raise McpRegistryError(f"{label} has unsupported keys: {', '.join(unknown)}")
            clients, all_clients = _client_selector(raw_target.get("clients"), label)
            repos, all_repos = _repo_selector(raw_target.get("repos"), label, repo_path_tuple)

            # Claude's only managed project surface is root .mcp.json, which Copilot
            # also discovers. Refuse a target that would claim isolation we cannot keep.
            if "claude" in clients and "copilot" not in clients:
                raise McpRegistryError(
                    f"{label} targets Claude without Copilot, but managed .mcp.json is "
                    "shared by both clients"
                )

            target = McpTarget(clients, repos, all_clients, all_repos)
            parsed_targets.append(target)
            for repo in repos:
                mutable_repo_clients[repo].setdefault(name, set()).update(clients)

        definitions[name] = definition
        targets[name] = tuple(parsed_targets)

    repo_clients = {
        repo: {
            name: tuple(client for client in MCP_CLIENTS if client in clients)
            for name, clients in sorted(assignments.items())
        }
        for repo, assignments in mutable_repo_clients.items()
    }

    # Copilot CLI 1.0.70 treats .github/mcp.json as a fallback when root
    # .mcp.json exists, despite the public documentation describing a merge.
    # Reject a matrix that would silently drop Copilot-only repo servers. An
    # exclusive Copilot `repos: all` target is safe because it uses the user
    # MCP surface instead of .github/mcp.json.
    global_copilot_names = {
        name
        for name, preset_targets in targets.items()
        if any(
            target.all_repos and target.clients == ("copilot",)
            for target in preset_targets
        )
    }
    for repo, assignments in repo_clients.items():
        has_shared_workspace_mcp = any(
            "claude" in clients for clients in assignments.values()
        )
        private_copilot_names = sorted(
            name
            for name, clients in assignments.items()
            if "copilot" in clients
            and "claude" not in clients
            and name not in global_copilot_names
        )
        if has_shared_workspace_mcp and private_copilot_names:
            raise McpRegistryError(
                f"repo `{repo}` mixes shared .mcp.json servers with Copilot-only "
                ".github/mcp.json servers that Copilot CLI 1.0.70 does not merge: "
                + ", ".join(private_copilot_names)
            )
    return McpCatalog(definitions, targets, repo_path_tuple, repo_clients)


def load_mcp_catalog(registry_path: Path, repo_entries: Any) -> McpCatalog:
    try:
        data = json.loads(registry_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise McpRegistryError(f"invalid JSON in {registry_path}: {exc}") from exc
    return load_mcp_catalog_data(data, repo_entries)


def claude_server_from_preset(name: str, preset: dict[str, Any]) -> dict[str, Any]:
    transport = preset["transport"]
    if transport == "http":
        return {"type": "http", "url": preset["url"]}
    entry: dict[str, Any] = {
        "type": "stdio",
        "command": preset["command"],
    }
    if preset.get("args"):
        entry["args"] = list(preset["args"])
    if preset.get("env"):
        entry["env"] = dict(preset["env"])
    if preset.get("cwd"):
        entry["cwd"] = preset["cwd"]
    return entry


def copilot_server_from_preset(name: str, preset: dict[str, Any]) -> dict[str, Any]:
    transport = preset["transport"]
    if transport == "http":
        return {"tools": ["*"], "type": "http", "url": preset["url"]}
    entry: dict[str, Any] = {
        "tools": ["*"],
        "type": "local",
        "command": preset["command"],
        "args": list(preset.get("args", [])),
    }
    if preset.get("env"):
        entry["env"] = dict(preset["env"])
    return entry
