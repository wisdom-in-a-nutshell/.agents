#!/usr/bin/env python3
"""Raw-transcript parsing and dialogue normalization for Dobby session folders.

Owns the session-folder transcript contract:

- locating the raw runtime transcript for a session (Claude projects JSONL or
  Codex rollout JSONL),
- rendering the normalized, runtime-agnostic ``dialogue.md`` from a raw file.

raw.jsonl is the source of truth and is copied untouched; dialogue.md can be
re-rendered from it at any time, so every dialogue file carries the normalizer
version that produced it.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

NORMALIZER_VERSION = "1"
LOCAL_TIMEZONE = "Europe/Berlin"
MESSAGE_MAX_CHARS = 6000
RUNTIMES = ("codex", "claude")

DEFAULT_CLAUDE_PROJECTS_DIR = Path.home() / ".claude" / "projects"
DEFAULT_CODEX_SESSIONS_DIR = Path.home() / ".codex" / "sessions"
DEFAULT_CODEX_ARCHIVED_DIR = Path.home() / ".codex" / "archived_sessions"


class TranscriptError(RuntimeError):
    pass


@dataclass
class Section:
    role: str  # "user" | "agent" | "marker"
    timestamp: str | None = None
    parts: list[str] = field(default_factory=list)
    pending_tools: dict[str, int] = field(default_factory=dict)

    def flush_tools(self) -> None:
        if self.pending_tools:
            summary = ", ".join(
                f"{name} ×{count}" if count > 1 else name
                for name, count in self.pending_tools.items()
            )
            self.parts.append(f"[tools: {summary}]")
            self.pending_tools = {}

    def add_text(self, text: str) -> None:
        text = text.strip()
        if not text:
            return
        self.flush_tools()
        if len(text) > MESSAGE_MAX_CHARS:
            text = text[:MESSAGE_MAX_CHARS].rstrip() + "\n...[message truncated]"
        self.parts.append(text)

    def add_marker(self, marker: str) -> None:
        self.flush_tools()
        self.parts.append(marker)

    def add_tool(self, name: str) -> None:
        self.pending_tools[name] = self.pending_tools.get(name, 0) + 1


@dataclass
class Dialogue:
    runtime: str
    session_id: str | None = None
    cwd: str | None = None
    model: str | None = None
    started: str | None = None
    ended: str | None = None
    tool_counts: dict[str, int] = field(default_factory=dict)
    token_note: str | None = None
    sections: list[Section] = field(default_factory=list)

    def section(self, role: str, timestamp: str | None) -> Section:
        if self.sections and self.sections[-1].role == role:
            return self.sections[-1]
        current = Section(role=role, timestamp=timestamp)
        self.sections.append(current)
        return current

    def count_tool(self, name: str) -> None:
        self.tool_counts[name] = self.tool_counts.get(name, 0) + 1

    def see_timestamp(self, value: str | None) -> None:
        if not value:
            return
        if self.started is None:
            self.started = value
        self.ended = value


def claude_projects_dir() -> Path:
    return Path(os.environ.get("CLAUDE_PROJECTS_DIR") or DEFAULT_CLAUDE_PROJECTS_DIR)


def codex_sessions_dir() -> Path:
    return Path(os.environ.get("CODEX_SESSIONS_DIR") or DEFAULT_CODEX_SESSIONS_DIR)


def codex_archived_dir() -> Path:
    return Path(os.environ.get("CODEX_ARCHIVED_SESSIONS_DIR") or DEFAULT_CODEX_ARCHIVED_DIR)


def find_raw_transcript(runtime: str, session_id: str) -> Path | None:
    """Locate the runtime-owned raw transcript for a session id, if it still exists."""
    if runtime == "claude":
        matches = sorted(claude_projects_dir().glob(f"*/{session_id}.jsonl"))
    elif runtime == "codex":
        # Finalized threads are archived: rollouts move from the dated sessions
        # tree to the flat archived_sessions folder.
        matches = sorted(codex_sessions_dir().glob(f"*/*/*/rollout-*-{session_id}.jsonl"))
        matches += sorted(codex_archived_dir().glob(f"rollout-*-{session_id}.jsonl"))
    else:
        raise TranscriptError(f"runtime must be one of {', '.join(RUNTIMES)}")
    candidates = [path for path in matches if path.stat().st_size > 0]
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_size)


def _local_stamp(value: str | None) -> str | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return value
    return parsed.astimezone(ZoneInfo(LOCAL_TIMEZONE)).strftime("%Y-%m-%d %H:%M")


def _iter_jsonl(path: Path) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise TranscriptError(f"failed to read {path}: {exc}") from exc
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            entries.append(obj)
    return entries


_INJECTED_TAG_RE = re.compile(r"^\s*<([a-zA-Z_][a-zA-Z0-9_ -]{0,60})>")
_COMMAND_NAME_RE = re.compile(r"<command-name>\s*(?P<name>[^<]+?)\s*</command-name>")


def _context_marker(text: str) -> str | None:
    """Collapse harness-injected blocks into a one-line marker, or None for real text."""
    stripped = text.strip()
    if stripped.startswith("# AGENTS.md instructions"):
        return f"[context: AGENTS.md instructions, {len(stripped):,} chars]"
    match = _INJECTED_TAG_RE.match(stripped)
    if match:
        tag = match.group(1).strip()
        if tag == "turn_aborted":
            return "[turn interrupted by the user]"
        return f"[context: {tag}, {len(stripped):,} chars]"
    return None


def parse_codex_rollout(path: Path) -> Dialogue:
    dialogue = Dialogue(runtime="codex")
    for obj in _iter_jsonl(path):
        kind = obj.get("type")
        payload = obj.get("payload") or {}
        stamp = obj.get("timestamp")
        if kind == "session_meta":
            dialogue.session_id = payload.get("id") or dialogue.session_id
            dialogue.cwd = payload.get("cwd") or dialogue.cwd
            dialogue.see_timestamp(stamp)
        elif kind == "turn_context":
            dialogue.model = payload.get("model") or dialogue.model
            dialogue.cwd = payload.get("cwd") or dialogue.cwd
        elif kind == "event_msg":
            event = payload.get("type")
            if event == "user_message":
                text = payload.get("message") or ""
                section = dialogue.section("user", _local_stamp(stamp))
                marker = _context_marker(text)
                if marker:
                    section.add_marker(marker)
                else:
                    section.add_text(text)
                dialogue.see_timestamp(stamp)
            elif event == "turn_aborted":
                dialogue.section("agent", _local_stamp(stamp)).add_marker(
                    "[turn interrupted by the user]"
                )
                dialogue.see_timestamp(stamp)
            elif event == "token_count":
                info = (payload.get("info") or {}).get("total_token_usage") or {}
                total = info.get("total_tokens")
                output = info.get("output_tokens")
                if total:
                    dialogue.token_note = (
                        f"cumulative ~{total:,} (output ~{output:,})"
                        if output
                        else f"cumulative ~{total:,}"
                    )
        elif kind == "response_item":
            item = payload.get("type")
            if item == "message":
                role = payload.get("role")
                text = "".join(
                    block.get("text", "")
                    for block in payload.get("content") or []
                    if isinstance(block, dict)
                )
                if role == "assistant":
                    dialogue.section("agent", _local_stamp(stamp)).add_text(text)
                    dialogue.see_timestamp(stamp)
                # user/developer response items duplicate event_msg user messages
                # or carry injected context; surface only non-duplicate markers.
                elif role in ("user", "developer"):
                    marker = _context_marker(text)
                    if marker and marker != "[turn interrupted by the user]":
                        dialogue.section("user", _local_stamp(stamp)).add_marker(marker)
            elif item in ("function_call", "custom_tool_call"):
                name = payload.get("name") or "tool"
                dialogue.section("agent", _local_stamp(stamp)).add_tool(name)
                dialogue.count_tool(name)
                dialogue.see_timestamp(stamp)
    return dialogue


def _claude_text_from_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        )
    return ""


def _first_line(value: Any, limit: int = 160) -> str:
    if isinstance(value, list):
        value = _claude_text_from_content(value)
    if not isinstance(value, str):
        return ""
    line = value.strip().splitlines()[0] if value.strip() else ""
    return line[:limit]


def parse_claude_transcript(path: Path) -> Dialogue:
    dialogue = Dialogue(runtime="claude")
    tool_names: dict[str, str] = {}
    usage_seen: set[str] = set()
    context_peak = 0
    output_total = 0
    for obj in _iter_jsonl(path):
        kind = obj.get("type")
        if kind not in ("user", "assistant"):
            continue
        if obj.get("isSidechain"):
            continue
        dialogue.session_id = obj.get("sessionId") or dialogue.session_id
        dialogue.cwd = obj.get("cwd") or dialogue.cwd
        stamp = obj.get("timestamp")
        message = obj.get("message") or {}
        content = message.get("content")
        if kind == "assistant":
            dialogue.model = message.get("model") or dialogue.model
            usage = message.get("usage") or {}
            message_id = message.get("id") or ""
            if usage and message_id not in usage_seen:
                usage_seen.add(message_id)
                context_peak = max(
                    context_peak,
                    int(usage.get("input_tokens") or 0)
                    + int(usage.get("cache_read_input_tokens") or 0)
                    + int(usage.get("cache_creation_input_tokens") or 0),
                )
                output_total += int(usage.get("output_tokens") or 0)
            section = dialogue.section("agent", _local_stamp(stamp))
            for block in content if isinstance(content, list) else []:
                if not isinstance(block, dict):
                    continue
                block_type = block.get("type")
                if block_type == "text":
                    section.add_text(block.get("text") or "")
                elif block_type == "tool_use":
                    name = block.get("name") or "tool"
                    tool_names[block.get("id") or ""] = name
                    section.add_tool(name)
                    dialogue.count_tool(name)
            dialogue.see_timestamp(stamp)
        else:
            if obj.get("isMeta"):
                continue
            if isinstance(content, str):
                section = dialogue.section("user", _local_stamp(stamp))
                command = _COMMAND_NAME_RE.search(content)
                if command:
                    section.add_marker(f"[command: {command.group('name')}]")
                else:
                    marker = _context_marker(content)
                    if marker:
                        section.add_marker(marker)
                    else:
                        section.add_text(content)
                dialogue.see_timestamp(stamp)
                continue
            for block in content if isinstance(content, list) else []:
                if not isinstance(block, dict):
                    continue
                block_type = block.get("type")
                if block_type == "text":
                    text = block.get("text") or ""
                    section = dialogue.section("user", _local_stamp(stamp))
                    marker = _context_marker(text)
                    if marker:
                        section.add_marker(marker)
                    else:
                        section.add_text(text)
                    dialogue.see_timestamp(stamp)
                elif block_type == "image":
                    dialogue.section("user", _local_stamp(stamp)).add_marker("[image attached]")
                    dialogue.see_timestamp(stamp)
                elif block_type == "tool_result" and block.get("is_error"):
                    name = tool_names.get(block.get("tool_use_id") or "", "tool")
                    detail = _first_line(block.get("content"))
                    dialogue.section("agent", _local_stamp(stamp)).add_marker(
                        f"[tool error: {name} — {detail}]" if detail else f"[tool error: {name}]"
                    )
    if context_peak or output_total:
        dialogue.token_note = f"context peak ~{context_peak:,}, output ~{output_total:,}"
    return dialogue


def parse_raw_transcript(path: Path, runtime: str) -> Dialogue:
    if runtime == "codex":
        return parse_codex_rollout(path)
    if runtime == "claude":
        return parse_claude_transcript(path)
    raise TranscriptError(f"runtime must be one of {', '.join(RUNTIMES)}")


def render_dialogue_md(dialogue: Dialogue) -> str:
    sections: list[Section] = []
    for section in dialogue.sections:
        section.flush_tools()
        if section.parts:
            sections.append(section)
    user_turns = sum(1 for section in sections if section.role == "user")
    agent_turns = sum(1 for section in sections if section.role == "agent")
    total_tools = sum(dialogue.tool_counts.values())
    tool_summary = ", ".join(
        f"{name} ×{count}"
        for name, count in sorted(dialogue.tool_counts.items(), key=lambda kv: (-kv[1], kv[0]))
    )
    header = [
        "# Session dialogue",
        "",
        f"- session: {dialogue.session_id or 'unknown'}",
        f"- runtime: {dialogue.runtime}",
    ]
    if dialogue.cwd:
        header.append(f"- cwd: {dialogue.cwd}")
    if dialogue.model:
        header.append(f"- model: {dialogue.model}")
    if dialogue.started:
        span = _local_stamp(dialogue.started) or dialogue.started
        ended = _local_stamp(dialogue.ended) or dialogue.ended
        header.append(f"- span: {span} → {ended}")
    header.append(f"- turns: {user_turns} user · {agent_turns} agent")
    if total_tools:
        header.append(f"- tool calls: {total_tools} ({tool_summary})")
    if dialogue.token_note:
        header.append(f"- tokens: {dialogue.token_note}")
    header.append(f"- normalizer: v{NORMALIZER_VERSION}")
    header.append("")

    body: list[str] = []
    role_label = {"user": "User", "agent": "Agent"}
    for section in sections:
        label = role_label.get(section.role, section.role)
        stamp = f" — {section.timestamp}" if section.timestamp else ""
        body.append(f"## {label}{stamp}")
        body.append("")
        body.append("\n\n".join(section.parts))
        body.append("")
    return "\n".join(header + body).rstrip() + "\n"
