#!/usr/bin/env python3
"""Shared Claude CLI helpers for Dobby lifecycle runners."""

from __future__ import annotations

import os
import shutil
from pathlib import Path


def claude_bin() -> str:
    """Resolve the claude CLI without depending on the caller's PATH."""
    override = os.environ.get("DOBBY_CLAUDE_BIN")
    if override:
        return override
    found = shutil.which("claude")
    if found:
        return found
    for candidate in (
        Path.home() / "bin/claude",
        Path("/opt/homebrew/bin/claude"),
        Path("/usr/local/bin/claude"),
    ):
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return "claude"
