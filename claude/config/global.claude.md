# Global Claude Guidance

This file is the canonical source for `~/.claude/CLAUDE.md`.

## Global Defaults

- Prefer `AGENTS.md` as the repo-local source of truth for shared instructions.
- If a repo uses `CLAUDE.md` with `@AGENTS.md`, treat that as the shared project guidance contract.
- Keep durable repo behavior, routing, and operating rules in versioned repo files instead of chat memory.
- Update the nearest `AGENTS.md` when a new repeatable local rule appears.
- Prefer automation over manual repetition.
- Keep changes concise, operational, and durable.

## Local Environment

- This machine keeps Codex as the primary control plane and Claude as a secondary control plane.
- When both Claude-native and shared repo guidance exist, follow the shared repo contract unless a Claude-only file clearly adds a tool-specific rule.
