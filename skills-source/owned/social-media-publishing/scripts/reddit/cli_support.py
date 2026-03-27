"""Shared CLI support for machine-first Reddit command wrappers."""

from __future__ import annotations

import importlib.util
import json
import os
import secrets
import shutil
import sys
import time
from dataclasses import asdict, is_dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

SCHEMA_VERSION = "1.0"
DEFAULT_ENV_PATH = Path.home() / ".secrets/reddit/env"
REDDIT_ENV_KEYS = [
    "REDDIT_CLIENT_ID",
    "REDDIT_CLIENT_SECRET",
    "REDDIT_USERNAME",
    "REDDIT_PASSWORD",
    "REDDIT_USER_AGENT",
]
OPTIONAL_ENV_KEYS = ["REDDIT_TOTP_SECRET"]


class CliError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        code: str = "E_GENERIC",
        exit_code: int = 1,
        retryable: bool = False,
        hint: str | None = None,
        details: Any | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.exit_code = exit_code
        self.retryable = retryable
        self.hint = hint
        self.details = details


def now_iso_utc() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def build_env_snapshot(env_path: Path) -> dict[str, Any]:
    file_values = parse_env_file(env_path)
    merged = dict(file_values)
    for key in REDDIT_ENV_KEYS + OPTIONAL_ENV_KEYS:
        if os.environ.get(key):
            merged[key] = os.environ[key]
    return {
        "env_path": env_path,
        "env_file_exists": env_path.exists(),
        "file_values": file_values,
        "merged_values": merged,
    }


def seed_env_from_file(env_path: Path) -> dict[str, Any]:
    snapshot = build_env_snapshot(env_path)
    for key, value in snapshot["file_values"].items():
        os.environ.setdefault(key, value)
    snapshot["merged_values"] = dict(snapshot["file_values"])
    for key in REDDIT_ENV_KEYS + OPTIONAL_ENV_KEYS:
        if os.environ.get(key):
            snapshot["merged_values"][key] = os.environ[key]
    return snapshot


def dependency_available(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


def command_exists(name: str) -> bool:
    return shutil.which(name) is not None


def require_runtime_dependencies(module_names: Iterable[str]) -> None:
    missing = [name for name in module_names if not dependency_available(name)]
    if missing:
        raise CliError(
            "Reddit runtime dependencies are missing.",
            code="E_DEPENDENCY",
            exit_code=4,
            hint="Use the Reddit posting environment or install the missing modules in the active interpreter.",
            details={"missing_modules": missing},
        )


def validate_reddit_auth(snapshot: dict[str, Any]) -> list[str]:
    merged = snapshot["merged_values"]
    return [key for key in REDDIT_ENV_KEYS if not merged.get(key)]


def make_status_payload(
    *,
    env_path: Path,
    supported_commands: list[str],
    dependency_names: list[str],
    include_ffmpeg: bool = False,
) -> dict[str, Any]:
    snapshot = build_env_snapshot(env_path)
    missing_auth = validate_reddit_auth(snapshot)
    dependencies = {name: dependency_available(name) for name in dependency_names}
    payload: dict[str, Any] = {
        "files": {
            "env_file": str(env_path),
            "env_file_exists": snapshot["env_file_exists"],
        },
        "auth": {
            "required_keys_present": {key: bool(snapshot["merged_values"].get(key)) for key in REDDIT_ENV_KEYS},
            "optional_keys_present": {key: bool(snapshot["merged_values"].get(key)) for key in OPTIONAL_ENV_KEYS},
        },
        "dependencies": dependencies,
        "capabilities": {
            "supported_commands": supported_commands,
            "json_default": True,
            "plain_available": True,
            "can_attempt_runtime": not missing_auth and all(dependencies.values()),
        },
        "notes": [],
    }
    if include_ffmpeg:
        payload["dependencies"]["ffmpeg"] = command_exists("ffmpeg")
        if not payload["dependencies"]["ffmpeg"]:
            payload["notes"].append("ffmpeg is missing; native video encode mode will fail.")
    if not snapshot["env_file_exists"]:
        payload["notes"].append("Reddit env file is missing. Expected machine-local credentials at ~/.secrets/reddit/env.")
    if missing_auth:
        payload["notes"].append("Missing Reddit auth keys: " + ", ".join(missing_auth))
    missing_deps = [name for name, present in payload["dependencies"].items() if not present]
    if missing_deps:
        payload["notes"].append("Missing runtime dependencies: " + ", ".join(missing_deps))
    return payload


def determine_output_mode(args: Any) -> str:
    if getattr(args, "plain", False):
        return "plain"
    return "json"


def flatten_plain(prefix: str, value: Any) -> list[str]:
    if isinstance(value, dict):
        lines: list[str] = []
        for key in sorted(value.keys()):
            child_prefix = f"{prefix}.{key}" if prefix else key
            lines.extend(flatten_plain(child_prefix, value[key]))
        return lines
    if isinstance(value, list):
        if not value:
            return [f"{prefix}=[]"]
        lines: list[str] = []
        for index, item in enumerate(value):
            child_prefix = f"{prefix}[{index}]"
            lines.extend(flatten_plain(child_prefix, item))
        return lines
    rendered = "" if value is None else str(value)
    return [f"{prefix}={rendered}"]


def emit_success(args: Any, command: str, data: dict[str, Any], *, start_time: float, request_id: str) -> int:
    envelope = {
        "schema_version": SCHEMA_VERSION,
        "command": command,
        "status": "ok",
        "data": data,
        "error": None,
        "meta": {
            "request_id": request_id,
            "duration_ms": int((time.time() - start_time) * 1000),
            "timestamp_utc": now_iso_utc(),
        },
    }
    if determine_output_mode(args) == "json":
        print(json.dumps(envelope, indent=2, sort_keys=True))
    else:
        print("\n".join(flatten_plain("data", data)))
    return 0


def emit_error(args: Any, command: str, error: CliError, *, start_time: float, request_id: str) -> int:
    envelope = {
        "schema_version": SCHEMA_VERSION,
        "command": command,
        "status": "error",
        "data": {},
        "error": {
            "code": error.code,
            "message": str(error),
            "retryable": error.retryable,
            "hint": error.hint,
            "details": error.details,
        },
        "meta": {
            "request_id": request_id,
            "duration_ms": int((time.time() - start_time) * 1000),
            "timestamp_utc": now_iso_utc(),
        },
    }
    if determine_output_mode(args) == "json":
        print(json.dumps(envelope, indent=2, sort_keys=True), file=sys.stderr)
    else:
        print(f"error.code={error.code}\nerror.message={str(error)}", file=sys.stderr)
        if error.hint:
            print(f"error.hint={error.hint}", file=sys.stderr)
    return error.exit_code


def to_jsonable(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        try:
            return value.model_dump(mode="json")
        except TypeError:
            return value.model_dump()
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(k): to_jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [to_jsonable(v) for v in value]
    if isinstance(value, tuple):
        return [to_jsonable(v) for v in value]
    return value


def read_text_file(path: str | Path, *, base_dir: Path | None = None) -> str:
    resolved = resolve_path(path, base_dir=base_dir)
    try:
        return resolved.read_text().strip()
    except FileNotFoundError as exc:
        raise CliError(
            f"Text file not found: {resolved}",
            code="E_INVALID_INPUT",
            exit_code=2,
        ) from exc


def resolve_path(path: str | Path, *, base_dir: Path | None = None) -> Path:
    candidate = Path(path).expanduser()
    if candidate.is_absolute():
        return candidate
    if base_dir is None:
        return candidate.resolve()
    return (base_dir / candidate).resolve()


def make_request_id() -> str:
    return secrets.token_hex(8)
