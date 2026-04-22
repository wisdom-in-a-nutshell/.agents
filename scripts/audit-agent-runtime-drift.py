#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore


SCHEMA_VERSION = "1.0"
COMMAND = "audit-agent-runtime-drift"
REQUIRED_PLUGIN_IDS = {"computer-use@openai-bundled"}
REVIEW_MARKETPLACE_PREFIXES = ("openai-",)


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def tail_text(value: str, *, max_lines: int = 80, max_chars: int = 12000) -> str:
    lines = value.splitlines()
    if len(lines) > max_lines:
        lines = ["..."] + lines[-max_lines:]
    text = "\n".join(lines)
    if len(text) > max_chars:
        return "..." + text[-max_chars:]
    return text


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_toml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    return tomllib.loads(path.read_text(encoding="utf-8"))


def check_result(
    name: str,
    status: str,
    summary: str,
    *,
    details: dict[str, Any] | None = None,
    hint: str | None = None,
    error_code: str | None = None,
) -> dict[str, Any]:
    return {
        "name": name,
        "status": status,
        "summary": summary,
        "details": details or {},
        "hint": hint,
        "error_code": error_code,
    }


def run_control_plane_check(agents_repo: Path, timeout_sec: int, *, skip: bool) -> dict[str, Any]:
    name = "agent_control_plane"
    script = agents_repo / "scripts" / "check-agent-control-planes.sh"
    if skip:
        return check_result(name, "skipped", "control-plane check skipped by request")
    if not script.is_file() or not os.access(script, os.X_OK):
        return check_result(
            name,
            "error",
            f"missing executable: {script}",
            hint="Restore the shared control-plane check script in ~/.agents/scripts/.",
            error_code="E_MISSING_CHECK_SCRIPT",
        )

    start = time.monotonic()
    try:
        completed = subprocess.run(
            [str(script)],
            cwd=str(agents_repo),
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        duration_ms = int((time.monotonic() - start) * 1000)
        output = "\n".join(part for part in [exc.stdout or "", exc.stderr or ""] if part)
        return check_result(
            name,
            "error",
            f"control-plane check timed out after {timeout_sec}s",
            details={"duration_ms": duration_ms, "output_tail": tail_text(output)},
            hint="Run ~/.agents/scripts/check-agent-control-planes.sh manually and inspect the slow or stuck check.",
            error_code="E_CONTROL_PLANE_TIMEOUT",
        )

    duration_ms = int((time.monotonic() - start) * 1000)
    combined_output = "\n".join(part for part in [completed.stdout, completed.stderr] if part)
    details = {
        "duration_ms": duration_ms,
        "exit_code": completed.returncode,
        "output_tail": tail_text(combined_output),
    }
    if completed.returncode == 0:
        return check_result(name, "ok", "shared agent control-plane check passed", details=details)
    return check_result(
        name,
        "error",
        f"shared agent control-plane check failed with exit code {completed.returncode}",
        details=details,
        hint="Run ~/.agents/scripts/check-agent-control-planes.sh and fix the first failing control-plane surface.",
        error_code="E_CONTROL_PLANE_CHECK_FAILED",
    )


def configured_plugin_ids(agents_repo: Path) -> set[str]:
    ids: set[str] = set()
    for relative in ("codex/config/global.config.toml", "codex/config/xcode.config.toml"):
        data = load_toml(agents_repo / relative)
        plugins = data.get("plugins", {})
        if isinstance(plugins, dict):
            ids.update(str(key) for key in plugins.keys())
    return ids


def enabled_canonical_plugin_ids(agents_repo: Path) -> set[str]:
    enabled: set[str] = set()
    for relative in ("codex/config/global.config.toml", "codex/config/xcode.config.toml"):
        data = load_toml(agents_repo / relative)
        plugins = data.get("plugins", {})
        if not isinstance(plugins, dict):
            continue
        for plugin_id, config in plugins.items():
            if isinstance(config, dict) and config.get("enabled") is True:
                enabled.add(str(plugin_id))
    return enabled


def managed_plugin_names(agents_repo: Path) -> set[str]:
    registry_path = agents_repo / "plugins" / "registry.json"
    if not registry_path.is_file():
        return set()
    registry = load_json(registry_path)
    names: set[str] = set()
    for item in registry.get("managed_plugins", []):
        if isinstance(item, dict) and isinstance(item.get("plugin"), str):
            names.add(item["plugin"])
    return names


def installed_codex_plugins(home: Path) -> list[dict[str, Any]]:
    cache_root = home / ".codex" / "plugins" / "cache"
    if not cache_root.is_dir():
        return []

    plugins: list[dict[str, Any]] = []
    for manifest in sorted(cache_root.glob("*/*/*/.codex-plugin/plugin.json")):
        version_dir = manifest.parent.parent
        plugin_dir = version_dir.parent
        marketplace_dir = plugin_dir.parent
        try:
            metadata = load_json(manifest)
        except Exception as exc:
            plugins.append(
                {
                    "id": f"{plugin_dir.name}@{marketplace_dir.name}",
                    "name": plugin_dir.name,
                    "marketplace": marketplace_dir.name,
                    "version": version_dir.name,
                    "path": str(version_dir),
                    "manifest_error": str(exc),
                }
            )
            continue
        plugin_name = metadata.get("name") if isinstance(metadata.get("name"), str) else plugin_dir.name
        plugins.append(
            {
                "id": f"{plugin_name}@{marketplace_dir.name}",
                "name": plugin_name,
                "marketplace": marketplace_dir.name,
                "version": metadata.get("version", version_dir.name),
                "path": str(version_dir),
                "display_name": (metadata.get("interface") or {}).get("displayName")
                if isinstance(metadata.get("interface"), dict)
                else None,
                "manifest_error": None,
            }
        )
    return plugins


def audit_codex_plugins(agents_repo: Path, home: Path) -> dict[str, Any]:
    installed = installed_codex_plugins(home)
    configured_ids = configured_plugin_ids(agents_repo)
    managed_names = managed_plugin_names(agents_repo)

    malformed = [plugin for plugin in installed if plugin.get("manifest_error")]
    if malformed:
        return check_result(
            "codex_plugin_inventory",
            "error",
            "one or more Codex plugin manifests could not be read",
            details={"malformed_plugins": malformed},
            hint="Inspect the listed ~/.codex/plugins/cache plugin manifests and reinstall or remove broken runtime plugins.",
            error_code="E_CODEX_PLUGIN_MANIFEST_INVALID",
        )

    unknown_review_plugins = [
        plugin
        for plugin in installed
        if str(plugin["marketplace"]).startswith(REVIEW_MARKETPLACE_PREFIXES)
        and plugin["id"] not in configured_ids
        and plugin["name"] not in managed_names
    ]
    if unknown_review_plugins:
        return check_result(
            "codex_plugin_inventory",
            "error",
            "unclassified OpenAI Codex plugin(s) installed locally",
            details={
                "unknown_plugins": unknown_review_plugins,
                "known_configured_plugin_ids": sorted(configured_ids),
                "known_managed_plugin_names": sorted(managed_names),
            },
            hint=(
                "Decide whether each plugin belongs in codex/config/*.toml, plugins/registry.json, "
                "or should be removed from the local Codex runtime."
            ),
            error_code="E_UNCLASSIFIED_CODEX_PLUGIN",
        )

    return check_result(
        "codex_plugin_inventory",
        "ok",
        "installed OpenAI Codex plugins are classified",
        details={
            "installed_plugins": installed,
            "known_configured_plugin_ids": sorted(configured_ids),
            "known_managed_plugin_names": sorted(managed_names),
        },
    )


def plugin_enabled_in_config(config_path: Path, plugin_id: str) -> bool:
    data = load_toml(config_path)
    plugins = data.get("plugins", {})
    if not isinstance(plugins, dict):
        return False
    plugin_config = plugins.get(plugin_id)
    return isinstance(plugin_config, dict) and plugin_config.get("enabled") is True


def audit_required_codex_plugins(agents_repo: Path, home: Path) -> dict[str, Any]:
    canonical_enabled = enabled_canonical_plugin_ids(agents_repo)
    required_ids = sorted(REQUIRED_PLUGIN_IDS & canonical_enabled)
    installed_ids = {plugin["id"] for plugin in installed_codex_plugins(home)}
    live_global_config = home / ".codex" / "config.toml"
    live_xcode_config = home / "Library" / "Developer" / "Xcode" / "CodingAssistant" / "codex" / "config.toml"

    failures: list[str] = []
    details: dict[str, Any] = {
        "required_plugin_ids": required_ids,
        "installed_plugin_ids": sorted(installed_ids),
        "live_global_config": str(live_global_config),
        "live_xcode_config": str(live_xcode_config),
    }
    for plugin_id in required_ids:
        if plugin_id not in installed_ids:
            failures.append(f"{plugin_id} is enabled canonically but not installed in ~/.codex/plugins/cache")
        if not plugin_enabled_in_config(live_global_config, plugin_id):
            failures.append(f"{plugin_id} is not enabled in live ~/.codex/config.toml")
        if live_xcode_config.exists() and not plugin_enabled_in_config(live_xcode_config, plugin_id):
            failures.append(f"{plugin_id} is not enabled in live Xcode Codex config")

    if failures:
        return check_result(
            "codex_required_plugins",
            "error",
            "required Codex plugin availability check failed",
            details={**details, "failures": failures},
            hint="Re-run ~/.agents/codex/scripts/sync-config.sh --apply or install the missing Codex plugin.",
            error_code="E_REQUIRED_CODEX_PLUGIN_UNAVAILABLE",
        )

    return check_result(
        "codex_required_plugins",
        "ok",
        "required Codex plugins are installed and enabled",
        details=details,
    )


def build_payload(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    start = time.monotonic()
    request_id = str(uuid.uuid4())
    agents_repo = Path(args.agents_repo).expanduser().resolve()
    home = Path(args.home).expanduser().resolve()

    checks = [
        run_control_plane_check(agents_repo, args.timeout_sec, skip=args.skip_control_plane_check),
        audit_codex_plugins(agents_repo, home),
        audit_required_codex_plugins(agents_repo, home),
    ]

    error_checks = [check for check in checks if check["status"] == "error"]
    warning_checks = [check for check in checks if check["status"] == "warning"]
    exit_code = 1 if error_checks else 0
    status = "error" if error_checks else "ok"

    payload = {
        "schema_version": SCHEMA_VERSION,
        "command": COMMAND,
        "status": status,
        "data": {
            "summary": {
                "checks": len(checks),
                "errors": len(error_checks),
                "warnings": len(warning_checks),
                "skipped": sum(1 for check in checks if check["status"] == "skipped"),
            },
            "checks": checks,
        },
        "error": None
        if not error_checks
        else {
            "code": "E_AGENT_RUNTIME_DRIFT",
            "message": f"{len(error_checks)} agent runtime drift check(s) failed",
            "retryable": False,
            "hint": "Run ~/.agents/scripts/audit-agent-runtime-drift.py --plain and fix the failing checks.",
        },
        "meta": {
            "request_id": request_id,
            "duration_ms": int((time.monotonic() - start) * 1000),
            "timestamp_utc": utc_now(),
            "agents_repo": str(agents_repo),
            "home": str(home),
        },
    }
    return payload, exit_code


def print_plain(payload: dict[str, Any]) -> None:
    summary = payload["data"]["summary"]
    heading = "OK" if payload["status"] == "ok" else "FAILED"
    print(f"Agent runtime drift audit: {heading}")
    print(
        "checks: "
        f"total={summary['checks']} errors={summary['errors']} "
        f"warnings={summary['warnings']} skipped={summary['skipped']}"
    )
    for check in payload["data"]["checks"]:
        label = {
            "ok": "OK",
            "warning": "WARN",
            "error": "FAIL",
            "skipped": "SKIP",
        }.get(check["status"], check["status"].upper())
        print(f"- {label} {check['name']}: {check['summary']}")
        if check.get("hint") and check["status"] != "ok":
            print(f"  hint: {check['hint']}")
        if check["status"] == "error" and check.get("details"):
            failures = check["details"].get("failures")
            if isinstance(failures, list):
                for failure in failures[:8]:
                    print(f"  - {failure}")
            unknown = check["details"].get("unknown_plugins")
            if isinstance(unknown, list):
                for plugin in unknown[:8]:
                    print(f"  - {plugin.get('id')} at {plugin.get('path')}")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit local agent runtime drift against the ~/.agents control plane."
    )
    output = parser.add_mutually_exclusive_group()
    output.add_argument("--json", action="store_true", help="Emit the stable JSON result contract (default).")
    output.add_argument("--plain", action="store_true", help="Emit concise plain text for operator inspection.")
    parser.add_argument("--no-input", action="store_true", help="Accepted for non-interactive callers; this command never prompts.")
    parser.add_argument("--agents-repo", default=str(Path(__file__).resolve().parents[1]), help="Path to the .agents repo.")
    parser.add_argument("--home", default=str(Path.home()), help="Home directory whose agent runtimes should be audited.")
    parser.add_argument("--timeout-sec", type=int, default=600, help="Timeout for the shared control-plane check.")
    parser.add_argument(
        "--skip-control-plane-check",
        action="store_true",
        help="Skip the full shared control-plane check; intended for focused tests only.",
    )
    args = parser.parse_args(argv)
    if args.timeout_sec < 1:
        parser.error("--timeout-sec must be >= 1")
    return args


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    payload, exit_code = build_payload(args)
    if args.plain:
        print_plain(payload)
    else:
        print(json.dumps(payload, indent=2, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
