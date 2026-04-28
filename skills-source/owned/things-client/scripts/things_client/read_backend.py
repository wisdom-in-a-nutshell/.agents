from __future__ import annotations

import argparse
import os
from typing import Any

from .config import READ_BACKEND_ENV, READ_BACKENDS
from .errors import ThingsError
from .sqlite_backend import has_configured_database_path

def should_fallback_from_sqlite(exc: ThingsError) -> bool:
    return not has_configured_database_path() and exc.code in {"E_NOT_FOUND", "E_IO"}


def add_sqlite_fallback_meta(backend: dict[str, Any], exc: ThingsError) -> dict[str, Any]:
    updated = dict(backend)
    updated["fallback_from"] = "sqlite"
    updated["fallback_reason"] = exc.message
    return updated


def selected_read_backend(args: argparse.Namespace | None = None) -> str:
    raw = ""
    if args is not None:
        raw = str(getattr(args, "backend", "") or "")
    raw = (raw or os.environ.get(READ_BACKEND_ENV) or "auto").strip().lower()
    if raw not in READ_BACKENDS:
        raise ThingsError("E_VALIDATION", f"invalid read backend: {raw!r}; expected one of {', '.join(READ_BACKENDS)}")
    return raw


def read_with_backend(
    args: argparse.Namespace,
    *,
    sqlite_call,
    jxa_call,
) -> tuple[Any, dict[str, Any]]:
    selected = selected_read_backend(args)
    if selected in ("auto", "sqlite"):
        try:
            return sqlite_call()
        except ThingsError as exc:
            if selected == "sqlite" or not should_fallback_from_sqlite(exc):
                raise
            result, backend = jxa_call()
            return result, add_sqlite_fallback_meta(backend, exc)
    return jxa_call()
