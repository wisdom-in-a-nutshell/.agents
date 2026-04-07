"""I/O helpers for the media toolkit."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from media_toolkit_lib.errors import CliError

DEFAULT_INPUT_UPLOAD_PREFIX = "share"


def upload_local_file(file_path: str) -> str:
    """Upload a local file to R2 and return its public URL."""

    path = Path(file_path).expanduser().resolve()
    if not path.exists() or not path.is_file():
        raise CliError(
            code="E_VALIDATION",
            message=f"Local file not found: {path}",
            exit_code=2,
            retryable=False,
            hint="Pass an existing local file path with --file.",
        )

    from services.storage import S3Config, S3Uploader

    uploader = S3Uploader(S3Config.R2)
    destination = (
        f"agent-media-toolkit/{datetime.now(timezone.utc).strftime('%Y/%m/%d')}/"
        f"{uuid.uuid4().hex}-{path.name}"
    )
    try:
        return uploader.upload_file(
            str(path),
            destination,
            prefix=DEFAULT_INPUT_UPLOAD_PREFIX,
        )
    except Exception as exc:  # noqa: BLE001
        raise CliError(
            code="E_UPLOAD_FAILED",
            message=f"Failed to upload local file: {path.name}",
            exit_code=4,
            retryable=True,
            hint="Check storage credentials and try again.",
        ) from exc


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
