#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sys
from fnmatch import fnmatch
from pathlib import Path
from urllib.parse import unquote


BACKUP_PATTERNS = (
    "*.bak",
    "*.bak.*",
    "*.orig",
    "*.rej",
    "*.tmp",
)
SKIP_DIRS = {
    ".git",
    ".cache",
    ".tmp",
    "tmp",
    "temp",
    "__pycache__",
    "node_modules",
}
MARKDOWN_LINK_RE = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check lightweight repo hygiene rules for the .agents control plane."
    )
    parser.add_argument(
        "--root",
        default=str(Path(__file__).resolve().parents[1]),
        help="Repository root to check.",
    )
    return parser.parse_args()


def is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def iter_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in root.rglob("*"):
        rel_parts = path.relative_to(root).parts
        if any(part in SKIP_DIRS for part in rel_parts):
            continue
        if path.is_file() or path.is_symlink():
            files.append(path)
    return files


def check_backup_artifacts(root: Path, files: list[Path]) -> list[str]:
    errors: list[str] = []
    for path in files:
        name = path.name
        if any(fnmatch(name, pattern) for pattern in BACKUP_PATTERNS):
            errors.append(f"backup/scratch artifact in repo tree: {path.relative_to(root)}")
    return errors


def check_broken_symlinks(root: Path, files: list[Path]) -> list[str]:
    errors: list[str] = []
    for path in files:
        if path.is_symlink() and not path.exists():
            errors.append(f"broken symlink in repo tree: {path.relative_to(root)}")
    return errors


def markdown_files(root: Path, files: list[Path]) -> list[Path]:
    docs: list[Path] = []
    for path in files:
        if path.suffix.lower() != ".md":
            continue
        rel = path.relative_to(root)
        if rel.parts[0] == "docs" or rel in {
            Path("AGENTS.md"),
            Path("codex/AGENTS.md"),
            Path("mcp/AGENTS.md"),
        }:
            docs.append(path)
    return docs


def normalize_link_target(raw_target: str) -> str:
    target = raw_target.strip()
    if target.startswith("<") and target.endswith(">"):
        target = target[1:-1].strip()
    target = target.split("#", 1)[0].split("?", 1)[0].strip()
    return unquote(target)


def should_skip_link(target: str) -> bool:
    if not target:
        return True
    lowered = target.lower()
    return (
        target.startswith("#")
        or lowered.startswith("http://")
        or lowered.startswith("https://")
        or lowered.startswith("mailto:")
        or lowered.startswith("obsidian://")
        or lowered.startswith("app://")
        or lowered.startswith("plugin://")
    )


def resolve_link(doc: Path, target: str) -> Path:
    if target.startswith("/"):
        return Path(target)
    return (doc.parent / target).resolve()


def check_markdown_links(root: Path, files: list[Path]) -> list[str]:
    errors: list[str] = []
    for doc in markdown_files(root, files):
        text = doc.read_text(encoding="utf-8")
        for match in MARKDOWN_LINK_RE.finditer(text):
            target = normalize_link_target(match.group(1))
            if should_skip_link(target):
                continue
            resolved = resolve_link(doc, target)
            if not is_within(resolved.resolve(), root):
                continue
            if not resolved.exists():
                rel_doc = doc.relative_to(root)
                errors.append(f"broken local markdown link in {rel_doc}: {target}")
    return errors


def main() -> int:
    args = parse_args()
    root = Path(args.root).expanduser().resolve()
    if not root.is_dir():
        print(f"ERROR: root does not exist: {root}", file=sys.stderr)
        return 2

    files = iter_files(root)
    errors = []
    errors.extend(check_backup_artifacts(root, files))
    errors.extend(check_broken_symlinks(root, files))
    errors.extend(check_markdown_links(root, files))

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print("OK: repo hygiene checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
