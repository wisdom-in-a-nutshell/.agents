from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


VALID_RUNTIMES = {"codex", "claude", "copilot"}
VALID_SCOPES = {"global"}
EVENT_RUNTIME_SUPPORT = {
    "SessionStart": {"codex", "claude", "copilot"},
    "UserPromptSubmit": {"codex", "claude", "copilot"},
    "Stop": {"codex", "claude", "copilot"},
    "SessionEnd": {"claude", "copilot"},
}
VALID_EVENTS = set(EVENT_RUNTIME_SUPPORT)
EVENTS_WITH_MATCHERS = {"SessionStart", "SessionEnd"}
COPILOT_EVENT_NAMES = {
    "SessionStart": "sessionStart",
    "UserPromptSubmit": "userPromptSubmitted",
    "Stop": "agentStop",
    "SessionEnd": "sessionEnd",
}


class HookRegistryError(RuntimeError):
    """User-facing hook registry validation failure."""


def _load_json_object(path: Path, *, label: str) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise HookRegistryError(f"Missing {label}: {path}") from exc
    except json.JSONDecodeError as exc:
        raise HookRegistryError(f"Invalid JSON in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise HookRegistryError(f"{label} root must be an object: {path}")
    return data


def render_json(value: dict[str, Any]) -> str:
    return json.dumps(value, indent=2, sort_keys=True) + "\n"


def load_hooks_registry(path: Path) -> dict[str, Any]:
    registry = _load_json_object(path.expanduser().resolve(), label="hooks registry")
    validate_hooks_registry_data(registry, label=str(path))
    return registry


def validate_hooks_registry_data(registry: dict[str, Any], *, label: str) -> None:
    version = registry.get("version")
    if version != 1:
        raise HookRegistryError(f"{label}: version must be 1")

    hooks = registry.get("managed_hooks")
    if not isinstance(hooks, list):
        raise HookRegistryError(f"{label}: managed_hooks must be an array")

    seen_ids: set[str] = set()
    for idx, hook in enumerate(hooks):
        prefix = f"{label}: managed_hooks[{idx}]"
        if not isinstance(hook, dict):
            raise HookRegistryError(f"{prefix} must be an object")

        hook_id = hook.get("id")
        if not isinstance(hook_id, str) or not hook_id.strip():
            raise HookRegistryError(f"{prefix}.id must be a non-empty string")
        if hook_id in seen_ids:
            raise HookRegistryError(f"{prefix}.id duplicates `{hook_id}`")
        seen_ids.add(hook_id)

        event = hook.get("event")
        if event not in VALID_EVENTS:
            raise HookRegistryError(
                f"{prefix}.event must be one of {sorted(VALID_EVENTS)}"
            )

        scope = hook.get("scope")
        if scope not in VALID_SCOPES:
            raise HookRegistryError(
                f"{prefix}.scope must be one of {sorted(VALID_SCOPES)}"
            )

        enabled = hook.get("enabled", True)
        if not isinstance(enabled, bool):
            raise HookRegistryError(f"{prefix}.enabled must be a boolean")

        runtimes = hook.get("runtimes")
        if not isinstance(runtimes, list) or not runtimes:
            raise HookRegistryError(f"{prefix}.runtimes must be a non-empty array")
        runtime_values: list[str] = []
        for runtime in runtimes:
            if runtime not in VALID_RUNTIMES:
                raise HookRegistryError(
                    f"{prefix}.runtimes contains unsupported runtime `{runtime}`"
                )
            supported_runtimes = EVENT_RUNTIME_SUPPORT[event]
            if runtime not in supported_runtimes:
                raise HookRegistryError(
                    f"{prefix}.event `{event}` is not supported for runtime `{runtime}`"
                )
            if runtime in runtime_values:
                raise HookRegistryError(
                    f"{prefix}.runtimes contains duplicate runtime `{runtime}`"
                )
            runtime_values.append(runtime)

        command = hook.get("command")
        if not isinstance(command, str) or not command.strip():
            raise HookRegistryError(f"{prefix}.command must be a non-empty string")
        if "{runtime}" not in command:
            raise HookRegistryError(
                f"{prefix}.command must include a {{runtime}} placeholder"
            )

        timeout = hook.get("timeout")
        if not isinstance(timeout, (int, float)) or isinstance(timeout, bool) or timeout <= 0:
            raise HookRegistryError(f"{prefix}.timeout must be a positive number")

        matchers = hook.get("matchers", {})
        if matchers is None:
            matchers = {}
        if not isinstance(matchers, dict):
            raise HookRegistryError(f"{prefix}.matchers must be an object")
        for runtime, matcher in matchers.items():
            if runtime not in VALID_RUNTIMES:
                raise HookRegistryError(
                    f"{prefix}.matchers contains unsupported runtime `{runtime}`"
                )
            if not isinstance(matcher, str) or not matcher.strip():
                raise HookRegistryError(
                    f"{prefix}.matchers.{runtime} must be a non-empty string"
                )


def _managed_hooks_for_runtime(registry: dict[str, Any], runtime: str) -> list[dict[str, Any]]:
    if runtime not in VALID_RUNTIMES:
        raise HookRegistryError(f"unsupported runtime `{runtime}`")
    hooks = registry.get("managed_hooks", [])
    selected: list[dict[str, Any]] = []
    for hook in hooks:
        if not isinstance(hook, dict):
            continue
        if not hook.get("enabled", True):
            continue
        if hook.get("scope") != "global":
            continue
        runtimes = hook.get("runtimes", [])
        if runtime in runtimes:
            selected.append(hook)
    return selected


def _render_command(template: str, *, runtime: str, event: str) -> str:
    return template.replace("{runtime}", runtime).replace("{event}", event)


def _render_matcher_group(hook: dict[str, Any], runtime: str) -> dict[str, Any]:
    event = str(hook["event"])
    handler: dict[str, Any] = {
        "command": _render_command(str(hook["command"]), runtime=runtime, event=event),
        "timeout": hook["timeout"],
        "type": "command",
    }
    status_message = hook.get("status_message")
    if isinstance(status_message, str) and status_message.strip():
        handler["statusMessage"] = status_message

    group: dict[str, Any] = {"hooks": [handler]}
    matchers = hook.get("matchers", {})
    matcher = matchers.get(runtime) if isinstance(matchers, dict) else None
    if event in EVENTS_WITH_MATCHERS and isinstance(matcher, str) and matcher.strip():
        group["matcher"] = matcher
    return group


def render_runtime_hooks(registry: dict[str, Any], runtime: str) -> dict[str, Any]:
    events: dict[str, list[dict[str, Any]]] = {}
    for hook in _managed_hooks_for_runtime(registry, runtime):
        event = str(hook["event"])
        events.setdefault(event, []).append(_render_matcher_group(hook, runtime))
    return {"hooks": events}


def render_codex_hooks(registry: dict[str, Any]) -> dict[str, Any]:
    return render_runtime_hooks(registry, "codex")


def _render_copilot_bash_command(hook: dict[str, Any]) -> str:
    event = str(hook["event"])
    command = _render_command(str(hook["command"]), runtime="copilot", event=event)
    managed_prefix = "python3 ~/.agents/"
    if not command.startswith(managed_prefix):
        return command

    path_and_args = command.removeprefix(managed_prefix)
    if " " in path_and_args:
        script_rel, args = path_and_args.split(" ", 1)
        args = " " + args
    else:
        script_rel = path_and_args
        args = ""
    script_path = f"$HOME/.agents/{script_rel}"
    return f'if [ -f "{script_path}" ]; then python3 "{script_path}"{args}; fi'


def render_copilot_hooks(registry: dict[str, Any]) -> dict[str, Any]:
    events: dict[str, list[dict[str, Any]]] = {}
    for hook in _managed_hooks_for_runtime(registry, "copilot"):
        event = str(hook["event"])
        copilot_event = COPILOT_EVENT_NAMES[event]
        handler: dict[str, Any] = {
            "bash": _render_copilot_bash_command(hook),
            "cwd": ".",
            "timeoutSec": hook["timeout"],
            "type": "command",
        }
        events.setdefault(copilot_event, []).append(handler)
    return {"hooks": events, "version": 1}


def merge_claude_hooks(settings: dict[str, Any], registry: dict[str, Any]) -> dict[str, Any]:
    rendered = render_runtime_hooks(registry, "claude")["hooks"]
    merged = dict(settings)
    existing_hooks = merged.get("hooks", {})
    if existing_hooks is None:
        existing_hooks = {}
    if not isinstance(existing_hooks, dict):
        raise HookRegistryError("Claude settings `hooks` must be an object when present")

    hook_events = dict(existing_hooks)
    for event, groups in rendered.items():
        existing_groups = hook_events.get(event, [])
        if existing_groups is None:
            existing_groups = []
        if not isinstance(existing_groups, list):
            raise HookRegistryError(f"Claude settings hooks.{event} must be an array")
        hook_events[event] = _without_managed_groups(existing_groups) + groups

    if hook_events:
        merged["hooks"] = hook_events
    return merged


def _without_managed_groups(groups: list[Any]) -> list[Any]:
    kept: list[Any] = []
    markers = {
        "~/.agents/hooks/scripts/lifecycle.py",
        "~/.agents/hooks/scripts/session_start.py",
        "~/.agents/hooks/scripts/user_prompt_submit.py",
        "~/.agents/hooks/scripts/stop.py",
        "~/.agents/hooks/scripts/session_end.py",
    }
    for group in groups:
        if not isinstance(group, dict):
            kept.append(group)
            continue
        handlers = group.get("hooks", [])
        if not isinstance(handlers, list):
            kept.append(group)
            continue
        has_managed_handler = False
        for handler in handlers:
            if not isinstance(handler, dict):
                continue
            command = handler.get("command")
            if isinstance(command, str) and any(marker in command for marker in markers):
                has_managed_handler = True
                break
        if not has_managed_handler:
            kept.append(group)
    return kept


def _write_output(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_json(data), encoding="utf-8")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render shared hook control-plane outputs.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate", help="Validate hooks registry")
    validate.add_argument("--registry", required=True)

    codex = subparsers.add_parser("render-codex", help="Render Codex hooks.json")
    codex.add_argument("--registry", required=True)
    codex.add_argument("--output", required=True)

    copilot = subparsers.add_parser(
        "render-copilot",
        help="Render GitHub Copilot repo hooks JSON",
    )
    copilot.add_argument("--registry", required=True)
    copilot.add_argument("--output", required=True)

    claude = subparsers.add_parser(
        "render-claude-settings",
        help="Render Claude settings with managed hooks merged in",
    )
    claude.add_argument("--registry", required=True)
    claude.add_argument("--settings", required=True)
    claude.add_argument("--output", required=True)

    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        registry = load_hooks_registry(Path(args.registry))
        if args.command == "validate":
            return 0
        if args.command == "render-codex":
            _write_output(Path(args.output).expanduser().resolve(), render_codex_hooks(registry))
            return 0
        if args.command == "render-copilot":
            _write_output(
                Path(args.output).expanduser().resolve(),
                render_copilot_hooks(registry),
            )
            return 0
        if args.command == "render-claude-settings":
            settings = _load_json_object(
                Path(args.settings).expanduser().resolve(),
                label="Claude settings",
            )
            _write_output(
                Path(args.output).expanduser().resolve(),
                merge_claude_hooks(settings, registry),
            )
            return 0
    except HookRegistryError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    raise AssertionError(f"unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
