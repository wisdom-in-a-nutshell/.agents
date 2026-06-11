"""Tiny flat-frontmatter helpers for Dobby prose organs.

This is deliberately not YAML. It parses only the flat `key: value` subset used
by Dobby workspace prose organs so Python hooks/linters and the dashboard TS
reader can keep identical semantics.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


class FrontmatterError(ValueError):
    pass


@dataclass(frozen=True)
class ProseDocument:
    frontmatter: dict[str, str]
    body: str


def parse_frontmatter_text(text: str, *, source: str = "<string>") -> ProseDocument:
    if text.startswith("\ufeff"):
        raise FrontmatterError(f"{source}: BOM is not allowed")
    if "\r" in text:
        raise FrontmatterError(f"{source}: CRLF/CR line endings are not allowed")
    if not text.startswith("---\n"):
        raise FrontmatterError(f"{source}: frontmatter opening --- must be the first line")
    lines = text.split("\n")
    closing_index: int | None = None
    for index in range(1, len(lines)):
        if lines[index] == "---":
            closing_index = index
            break
    if closing_index is None:
        raise FrontmatterError(f"{source}: missing frontmatter closing ---")
    meta: dict[str, str] = {}
    for line_number, line in enumerate(lines[1:closing_index], start=2):
        if not line:
            raise FrontmatterError(f"{source}:{line_number}: blank frontmatter lines are not allowed")
        if ": " not in line:
            raise FrontmatterError(f"{source}:{line_number}: frontmatter line must be key: value")
        key, value = line.split(": ", 1)
        if not key or not key[0].isalpha() or not key.replace("_", "").isalnum() or "_" in key:
            # Contract keys are camel-ish flat scalars: [a-zA-Z][a-zA-Z0-9]*.
            raise FrontmatterError(f"{source}:{line_number}: invalid frontmatter key {key!r}")
        if key in meta:
            raise FrontmatterError(f"{source}:{line_number}: duplicate frontmatter key {key!r}")
        meta[key] = value.strip()
    body = "\n".join(lines[closing_index + 1 :])
    return ProseDocument(meta, body)


def read_frontmatter_file(path: Path) -> ProseDocument:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise FrontmatterError(f"{path}: failed to read file: {exc}") from exc
    return parse_frontmatter_text(text, source=str(path))


def render_frontmatter(meta: dict[str, object], body: str) -> str:
    lines = ["---"]
    for key, value in meta.items():
        lines.append(f"{key}: {value}")
    lines.append("---")
    lines.append(body.rstrip("\n"))
    return "\n".join(lines).rstrip("\n") + "\n"


def strip_leading_h1(body: str) -> str:
    lines = body.strip().splitlines()
    if lines and lines[0].startswith("# "):
        return "\n".join(lines[1:]).strip()
    return body.strip()


def iter_markdown_headings(body: str):
    """Yield (line_no, level, text) for ATX headings outside fenced blocks."""
    in_fence = False
    fence_marker = ""
    for line_no, raw in enumerate(body.replace("\r\n", "\n").split("\n"), start=1):
        stripped = raw.strip()
        if stripped.startswith("```"):
            marker = stripped[:3]
            if in_fence and marker == fence_marker:
                in_fence = False
                fence_marker = ""
            elif not in_fence:
                in_fence = True
                fence_marker = marker
            continue
        if in_fence:
            continue
        if not raw.startswith("#"):
            continue
        hashes = len(raw) - len(raw.lstrip("#"))
        if 1 <= hashes <= 6 and len(raw) > hashes and raw[hashes] == " ":
            yield line_no, hashes, raw[hashes + 1 :].strip()
