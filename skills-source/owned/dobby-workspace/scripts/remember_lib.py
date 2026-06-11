#!/usr/bin/env python3
"""Shared remember-session prompt rendering for Dobby finalization runners.

Both runtimes preserve memory the same way — one final turn on top of the
ending conversation, driven by the versioned prompt in
`prompts/remember-session.md`. The Codex runner (`remember-session`) resumes an
App Server thread; the Claude runner (`remember-claude-session`) resumes a
Claude Code session. This module is the single source of truth for rendering
that instruction so the two runners cannot drift.
"""

from __future__ import annotations

import json
import re
from pathlib import Path


class RememberPromptError(RuntimeError):
    """Prompt template lookup or rendering failure."""


def prompt_template_path() -> Path:
    return Path(__file__).resolve().parents[1] / "prompts" / "remember-session.md"


def shell_quote(value: Path | str) -> str:
    return "'" + str(value).replace("'", "'\"'\"'") + "'"


def render_prompt_template(template: str, values: dict[str, str]) -> str:
    placeholders = set(re.findall(r"{{\s*([A-Za-z0-9_]+)\s*}}", template))
    expected = set(values)
    unknown = sorted(placeholders - expected)
    missing = sorted(expected - placeholders)
    if unknown:
        raise RememberPromptError(f"remember-session prompt has unknown placeholder(s): {', '.join(unknown)}")
    if missing:
        raise RememberPromptError(f"remember-session prompt is missing placeholder(s): {', '.join(missing)}")

    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        return values[key]

    rendered = re.sub(r"{{\s*([A-Za-z0-9_]+)\s*}}", replace, template)
    if "{{" in rendered or "}}" in rendered:
        raise RememberPromptError("remember-session prompt rendered with leftover placeholder braces")
    return rendered


def build_instruction(
    *,
    workspace_root: Path,
    thread_id: str,
    trigger: str,
    runtime: str = "codex",
) -> str:
    session_memory_cli = Path.home() / "GitHub/agents/skills-source/owned/dobby-workspace/scripts/session-memory"
    body_map_path = Path.home() / "GitHub/agents/skills-source/owned/dobby-workspace/references/body-map.md"
    template_path = prompt_template_path()
    try:
        template = template_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RememberPromptError(
            f"failed to read remember-session prompt template: {template_path}: {exc}"
        ) from exc
    values = {
        "workspace_root_json": json.dumps(str(workspace_root), ensure_ascii=False),
        "thread_id_json": json.dumps(thread_id, ensure_ascii=False),
        "trigger_json": json.dumps(trigger, ensure_ascii=False),
        "runtime_json": json.dumps(runtime, ensure_ascii=False),
        "body_map_path": str(body_map_path),
        "body_map_path_json": json.dumps(str(body_map_path), ensure_ascii=False),
        "session_memory_cli_json": json.dumps(str(session_memory_cli), ensure_ascii=False),
        "session_memory_cli_shell": shell_quote(session_memory_cli),
    }
    return render_prompt_template(template, values)
