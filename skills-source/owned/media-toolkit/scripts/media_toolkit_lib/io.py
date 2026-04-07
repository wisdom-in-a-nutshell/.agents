"""I/O helpers for the media toolkit."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

from media_toolkit_lib.errors import CliError

DEFAULT_INPUT_UPLOAD_PREFIX = "share"
DEFAULT_DESTINATION_PREFIX = "agent-media-toolkit"
DEFAULT_UPLOAD_MEDIA_BIN = Path(
    os.path.expandvars(
        os.getenv(
            "MEDIA_UPLOAD_BIN",
            str(Path.home() / "GitHub/scripts/bin/upload-media"),
        )
    )
).expanduser().resolve()


def upload_local_file(
    file_path: str,
    *,
    storage_prefix: str = DEFAULT_INPUT_UPLOAD_PREFIX,
    destination_prefix: str = DEFAULT_DESTINATION_PREFIX,
) -> dict[str, str]:
    """Upload a local file through the shared upload-media tool."""

    path = Path(file_path).expanduser().resolve()
    if not path.exists() or not path.is_file():
        raise CliError(
            code="E_VALIDATION",
            message=f"Local file not found: {path}",
            exit_code=2,
            retryable=False,
            hint="Pass an existing local file path with --file.",
        )

    if not DEFAULT_UPLOAD_MEDIA_BIN.exists():
        raise CliError(
            code="E_DEPENDENCY_MISSING",
            message=f"upload-media tool not found: {DEFAULT_UPLOAD_MEDIA_BIN}",
            exit_code=4,
            retryable=False,
            hint="Create the shared tool under $HOME/GitHub/scripts/bin/upload-media.",
        )

    command = [
        str(DEFAULT_UPLOAD_MEDIA_BIN),
        "--json",
        "--no-input",
        "--file",
        str(path),
        "--storage-prefix",
        storage_prefix,
        "--destination-prefix",
        destination_prefix,
    ]
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        raise CliError(
            code="E_DEPENDENCY_MISSING",
            message="Failed to execute upload-media.",
            exit_code=4,
            retryable=False,
            hint="Check that $HOME/GitHub/scripts/bin/upload-media is executable.",
        ) from exc

    payload = _parse_upload_media_output(completed.stdout)
    if completed.returncode != 0:
        error = payload.get("error") if isinstance(payload, dict) else None
        raise CliError(
            code=str((error or {}).get("code") or "E_UPLOAD_FAILED"),
            message=str((error or {}).get("message") or "upload-media failed."),
            exit_code=completed.returncode or 4,
            retryable=bool((error or {}).get("retryable", True)),
            hint=str(
                (error or {}).get("hint")
                or completed.stderr.strip()
                or "Inspect the upload-media output and retry."
            ),
            detail=payload or {"stderr": completed.stderr.strip()},
        )

    upload_payload = ((payload.get("data") or {}).get("upload")) if payload else None
    if not isinstance(upload_payload, dict) or not upload_payload.get("url"):
        raise CliError(
            code="E_UPLOAD_FAILED",
            message="upload-media returned an invalid response.",
            exit_code=4,
            retryable=False,
            hint="Inspect the upload-media JSON output for the missing upload payload.",
            detail=payload,
        )
    return {
        "file_path": str(upload_payload.get("file_path", path)),
        "file_name": str(upload_payload.get("file_name", path.name)),
        "storage_prefix": str(upload_payload.get("storage_prefix", storage_prefix)),
        "destination_path": str(upload_payload.get("destination_path", "")),
        "content_sha256": str(upload_payload.get("content_sha256", "")),
        "cached": bool(upload_payload.get("cached", False)),
        "url": str(upload_payload["url"]),
    }


def write_json_file(file_path: str, payload: dict[str, Any]) -> str:
    """Write JSON output to a local file."""

    path = _prepare_output_path(file_path)
    try:
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    except OSError as exc:
        raise CliError(
            code="E_OUTPUT_WRITE",
            message=f"Failed to write JSON output file: {path}",
            exit_code=1,
            retryable=False,
            hint="Check the output path and parent directory permissions.",
        ) from exc
    return str(path)


def _prepare_output_path(file_path: str) -> Path:
    path = Path(file_path).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _parse_upload_media_output(stdout: str) -> dict[str, Any]:
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise CliError(
            code="E_UPLOAD_FAILED",
            message="upload-media did not return valid JSON.",
            exit_code=4,
            retryable=False,
            hint="Inspect the upload-media stdout and verify the shared uploader installation.",
            detail={"stdout": stdout},
        ) from exc

    if not isinstance(payload, dict):
        raise CliError(
            code="E_UPLOAD_FAILED",
            message="upload-media returned an unexpected payload shape.",
            exit_code=4,
            retryable=False,
            hint="Inspect the upload-media JSON output for the malformed response.",
            detail={"stdout": stdout},
        )
    return payload
