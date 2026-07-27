#!/usr/bin/env python3
"""Safely archive one complete project-tracker directory.

The command moves the whole project directory into its sibling archive/
directory by default so no empty active tree remains. Pass --dry-run only to
inspect the validated move without applying it.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "1.0"
COMMAND = "project archive"
EXIT_GENERIC = 1
EXIT_USAGE = 2


class ArchiveError(Exception):
    def __init__(self, code: str, message: str, hint: str, exit_code: int = EXIT_USAGE) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.hint = hint
        self.exit_code = exit_code


def _meta(request_id: str, started_at: float) -> dict[str, Any]:
    return {
        "request_id": request_id,
        "duration_ms": round((time.monotonic() - started_at) * 1000),
        "timestamp_utc": datetime.now(UTC).isoformat(),
    }


def _emit(payload: dict[str, Any], *, plain: bool, error: bool = False) -> None:
    if plain:
        if error:
            detail = payload["error"]
            print(f"{detail['code']}: {detail['message']}", file=sys.stderr)
            print(f"hint: {detail['hint']}", file=sys.stderr)
            return
        data = payload["data"]
        action = "archived" if data["applied"] else "dry-run"
        print(
            f"project archive: {action} {data['source']} -> {data['destination']} "
            f"({data['file_count']} files)"
        )
        return
    print(json.dumps(payload, sort_keys=True))


def _success(
    request_id: str,
    started_at: float,
    data: dict[str, Any],
    *,
    plain: bool,
) -> int:
    _emit(
        {
            "schema_version": SCHEMA_VERSION,
            "command": COMMAND,
            "status": "ok",
            "data": data,
            "error": None,
            "meta": _meta(request_id, started_at),
        },
        plain=plain,
    )
    return 0


def _failure(
    request_id: str,
    started_at: float,
    error: ArchiveError,
    *,
    plain: bool,
) -> int:
    _emit(
        {
            "schema_version": SCHEMA_VERSION,
            "command": COMMAND,
            "status": "error",
            "data": None,
            "error": {
                "code": error.code,
                "message": error.message,
                "retryable": False,
                "hint": error.hint,
            },
            "meta": _meta(request_id, started_at),
        },
        plain=plain,
        error=True,
    )
    return error.exit_code


def _resolve_and_validate(source_raw: str, destination_raw: str) -> tuple[Path, Path]:
    source_input = Path(source_raw).expanduser()
    destination_input = Path(destination_raw).expanduser()

    if source_input.is_symlink():
        raise ArchiveError(
            "E_SOURCE_SYMLINK",
            f"Active project path must not be a symlink: {source_input}",
            "Pass the real active project directory.",
        )
    if not source_input.exists():
        raise ArchiveError(
            "E_SOURCE_NOT_FOUND",
            f"Active project directory does not exist: {source_input}",
            "Pass the project directory that directly contains tasks.md.",
        )
    if not source_input.is_dir():
        raise ArchiveError(
            "E_SOURCE_NOT_DIRECTORY",
            f"Active project path is not a directory: {source_input}",
            "Pass the complete active project directory, not tasks.md itself.",
        )

    source = source_input.resolve()
    destination = destination_input.resolve(strict=False)

    if destination.exists():
        raise ArchiveError(
            "E_DESTINATION_EXISTS",
            f"Archive destination already exists: {destination}",
            "Inspect the existing archive and choose a non-conflicting project name.",
        )
    if not (source / "tasks.md").is_file():
        raise ArchiveError(
            "E_TASKS_MISSING",
            f"Active project directory has no tasks.md: {source}",
            "Pass the complete project directory that owns the canonical tracker.",
        )
    if (
        source.name == "archive"
        or destination.name != source.name
        or destination.parent.name != "archive"
        or source.parent != destination.parent.parent
    ):
        raise ArchiveError(
            "E_INVALID_ARCHIVE_LAYOUT",
            f"Archive must move {source.name} into its tracker home's sibling archive directory",
            f"Use destination {source.parent / 'archive' / source.name}.",
        )

    archive_root = destination.parent
    if archive_root.is_symlink():
        raise ArchiveError(
            "E_ARCHIVE_ROOT_SYMLINK",
            f"Archive root must not be a symlink: {archive_root}",
            "Use the real archive directory under the tracker home.",
        )
    if archive_root.exists() and not archive_root.is_dir():
        raise ArchiveError(
            "E_ARCHIVE_ROOT_NOT_DIRECTORY",
            f"Archive root is not a directory: {archive_root}",
            "Repair the tracker home's archive path before retrying.",
        )
    return source, destination


def _tree_counts(source: Path) -> tuple[int, int]:
    file_count = 0
    directory_count = 1
    for path in source.rglob("*"):
        if path.is_dir():
            directory_count += 1
        else:
            file_count += 1
    return file_count, directory_count


def archive_project(
    source_raw: str,
    destination_raw: str,
    *,
    dry_run: bool,
) -> dict[str, Any]:
    source, destination = _resolve_and_validate(source_raw, destination_raw)
    file_count, directory_count = _tree_counts(source)
    data = {
        "applied": not dry_run,
        "source": str(source),
        "destination": str(destination),
        "file_count": file_count,
        "directory_count": directory_count,
        "source_removed": False,
        "destination_created": False,
    }
    if dry_run:
        return data

    archive_root = destination.parent
    archive_root_created = not archive_root.exists()
    try:
        archive_root.mkdir()
        source.rename(destination)
    except OSError as exc:
        if archive_root_created:
            try:
                archive_root.rmdir()
            except OSError:
                pass
        raise ArchiveError(
            "E_ARCHIVE_FAILED",
            f"Could not archive project: {exc}",
            "Confirm source and destination are on the same writable filesystem, then retry.",
            EXIT_GENERIC,
        ) from exc

    if source.exists() or not (destination / "tasks.md").is_file():
        raise ArchiveError(
            "E_ARCHIVE_POSTCONDITION",
            "Archive move completed without satisfying the source/destination postcondition",
            "Inspect both paths before making another archive attempt.",
            EXIT_GENERIC,
        )

    data["source_removed"] = True
    data["destination_created"] = True
    return data


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Archive one complete project tree into its tracker home's archive directory. "
            "Archives by default; this local atomic move has no timeout or prompt."
        )
    )
    parser.add_argument("--source", required=True, help="Active project directory containing tasks.md.")
    parser.add_argument(
        "--destination",
        required=True,
        help="Archive destination, e.g. docs/projects/archive/<project>.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and report the archive move without applying it.",
    )
    parser.add_argument(
        "--no-input",
        action="store_true",
        help="Accepted for agent callers; the command never prompts.",
    )
    output = parser.add_mutually_exclusive_group()
    output.add_argument("--json", action="store_true", help="Emit JSON (the default).")
    output.add_argument("--plain", action="store_true", help="Emit concise operator text.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    request_id = f"project-archive-{uuid.uuid4()}"
    started_at = time.monotonic()
    try:
        data = archive_project(args.source, args.destination, dry_run=args.dry_run)
    except ArchiveError as exc:
        return _failure(request_id, started_at, exc, plain=args.plain)
    return _success(request_id, started_at, data, plain=args.plain)


if __name__ == "__main__":
    raise SystemExit(main())
