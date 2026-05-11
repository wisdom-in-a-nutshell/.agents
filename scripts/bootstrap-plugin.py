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
from urllib.parse import urlparse


SCHEMA_VERSION = "1.0"
COMMAND = "bootstrap-plugin"

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
        enabled = "enabled" if data["enabled"] else "disabled"
        targets = ",".join(data["targets"])
        print(
            f"ok plugin={data['plugin']} marketplace={data['marketplace']} "
            f"state={enabled} targets={targets} "
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


def ordered_unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for raw in values:
        value = raw.strip()
        if not value or value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def parse_plugin_ref(raw: str) -> tuple[str, str]:
    raw = raw.strip()
    if not raw:
        raise ValueError("plugin reference must not be empty")

    parsed = urlparse(raw)
    if parsed.scheme and parsed.netloc:
        if parsed.netloc != "github.com":
            raise ValueError(f"unsupported plugin URL host: {parsed.netloc}")
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) < 5 or parts[0] != "openai" or parts[1] != "plugins" or parts[2] != "tree":
            raise ValueError(
                "GitHub plugin URLs must look like https://github.com/openai/plugins/tree/<branch>/plugins/<name>"
            )
        plugin_path = "/".join(parts[4:]).strip("/")
        if not plugin_path.startswith("plugins/"):
            raise ValueError("only official openai/plugins plugin URLs are supported")
        plugin_name = plugin_path.split("/")[-1]
        if not plugin_name:
            raise ValueError(f"invalid plugin path in URL: {raw}")
        return plugin_name, "openai-curated"

    if "@" in raw:
        plugin_name, marketplace = raw.rsplit("@", 1)
        plugin_name = plugin_name.strip()
        marketplace = marketplace.strip()
        if not plugin_name or not marketplace:
            raise ValueError(f"invalid plugin id: {raw}")
        return plugin_name, marketplace

    return raw, "openai-curated"


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
        description="Bootstrap a native Codex plugin entry into ~/.agents."
    )
    parser.add_argument(
        "plugin_ref",
        help="Plugin name, plugin id (name@marketplace), or official openai/plugins GitHub tree URL.",
    )
    parser.add_argument(
        "--target",
        action="append",
        choices=["global", "xcode"],
        default=[],
        help="Codex config target to render into. Repeat for multiple targets. Default: global.",
    )
    parser.add_argument(
        "--disabled",
        action="store_true",
        help="Track the plugin as disabled instead of enabled.",
    )
    parser.add_argument(
        "--category",
        default="Coding",
        help="Category shown in the Obsidian registry view (default: Coding).",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply changes. Default is dry-run.",
    )
    parser.add_argument(
        "--registry-file",
        default=str(Path.home() / ".agents" / "plugins" / "registry.json"),
        help="Path to plugins registry JSON.",
    )
    parser.add_argument(
        "--timeout-sec",
        type=int,
        default=300,
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
    request_id = f"bootstrap-plugin-{uuid.uuid4()}"
    started_at = time.time()

    try:
        plugin_name, marketplace = parse_plugin_ref(args.plugin_ref)
    except ValueError as exc:
        return finish_error(
            request_id,
            started_at,
            code="E_INVALID_PLUGIN_REF",
            message=str(exc),
            hint="Pass a plugin name, name@marketplace, or an official openai/plugins tree URL.",
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

    root_dir = registry_file.parent.parent.resolve()

    try:
        registry = json.loads(registry_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return finish_error(
            request_id,
            started_at,
            code="E_INVALID_REGISTRY_JSON",
            message=f"Invalid JSON in {registry_file}: {exc}",
            hint="Repair plugins/registry.json before bootstrapping a plugin.",
            exit_code=EXIT_USAGE,
            plain=args.plain,
        )

    managed = registry.get("managed_plugins")
    if not isinstance(managed, list):
        return finish_error(
            request_id,
            started_at,
            code="E_INVALID_REGISTRY_SHAPE",
            message="managed_plugins must be an array",
            hint="Repair plugins/registry.json before bootstrapping a plugin.",
            exit_code=EXIT_USAGE,
            plain=args.plain,
        )

    targets = ordered_unique(args.target or ["global"])
    enabled = not args.disabled
    existing_entry: dict[str, Any] | None = None
    for entry in managed:
        if not isinstance(entry, dict):
            continue
        if (
            str(entry.get("plugin", "")).strip() == plugin_name
            and str(entry.get("marketplace", "")).strip() == marketplace
        ):
            existing_entry = entry
            break

    desired_entry = {
        "plugin": plugin_name,
        "marketplace": marketplace,
        "enabled": enabled,
        "targets": targets,
        "category": args.category,
    }

    registry_changed = False
    actions: list[str] = []
    if existing_entry is None:
        managed.append(desired_entry)
        registry_changed = True
        actions.append(f"Registry add: native Codex plugin {plugin_name}@{marketplace}.")
    else:
        for key, value in desired_entry.items():
            if existing_entry.get(key) != value:
                existing_entry[key] = value
                registry_changed = True
        if registry_changed:
            actions.append(f"Registry update: native Codex plugin {plugin_name}@{marketplace}.")
        else:
            actions.append(f"Registry unchanged: native Codex plugin already tracked.")

    commands_run: list[dict[str, Any]] = []
    if args.apply:
        if registry_changed:
            registry_file.write_text(json.dumps(registry, indent=2) + "\n", encoding="utf-8")

        child_commands = [
            [sys.executable, "scripts/sync-plugins-registry.py", "--apply"],
            [str(root_dir / "scripts/bootstrap-machine-agent-control-planes.sh"), "--apply"],
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
        actions.append("Regenerated Codex plugin registry views.")
        actions.append("Applied shared Codex and Claude control planes.")
    else:
        actions.append("Would regenerate Codex plugin registry views.")
        actions.append("Would apply shared Codex and Claude control planes.")

    data = {
        "plugin": plugin_name,
        "marketplace": marketplace,
        "plugin_id": f"{plugin_name}@{marketplace}",
        "enabled": enabled,
        "targets": targets,
        "category": args.category,
        "registry_file": str(registry_file),
        "registry_changed": registry_changed,
        "apply": bool(args.apply),
        "actions": actions,
        "commands_run": commands_run,
    }
    return finish_ok(request_id, started_at, data, plain=args.plain)


if __name__ == "__main__":
    raise SystemExit(main())
