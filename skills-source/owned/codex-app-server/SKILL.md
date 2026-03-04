---
name: "codex-app-server"
description: "Use when implementing or reviewing Codex App Server integrations (initialize/thread/turn/item lifecycle, streaming events, approvals, and transport behavior). Keep this file as a concise overview; use the local App Server README snapshot as the primary detailed reference, and use MCP docs as fallback when details are missing or unclear."
---

# Codex App Server

Use this skill when building around Codex App Server primitives. Keep the client/harness thin and deterministic.

## Overview

Use this file for quick orientation only. Detailed protocol and API behavior should come from the snapshot reference.

## Core Mental Model

- Transport is typically `stdio` with line-delimited JSON messages.
- Work happens in durable `thread`s made of `turn`s made of `item`s.
- Items stream during a turn and complete with final state events.
- Server can request approvals from the client; client must respond.

## Implementation Defaults

- Do not build a parallel agent loop; use App Server primitives directly.
- Keep model/tools/runtime settings stable within a thread when possible.
- Persist `threadId` and resume threads instead of recreating context.
- Prefer deterministic ordering for any tool lists sent by the client.

## Primary References

- Local reference (primary detail source): `references/openai-codex-app-server-readme-reference.md`
- Live upstream README (latest source for snapshot): `https://raw.githubusercontent.com/openai/codex/refs/heads/main/codex-rs/app-server/README.md`
- App Server docs: `https://developers.openai.com/codex/app-server/`
- CLI reference: `https://developers.openai.com/codex/cli/reference/#codex-app-server`

## Reference Policy

1. Treat `references/openai-codex-app-server-readme-reference.md` as the primary source for detailed behavior.
2. If the snapshot does not answer a question clearly, fetch official docs via MCP (`openaiDeveloperDocs`).
3. If the snapshot and MCP docs disagree, prefer the latest official docs from MCP.

## Temporary Snapshot Automation

- Snapshot refresh is maintained by control-plane scripts outside this skill.
- Manual refresh script:
  - `~/.agents/scripts/refresh-codex-app-server-snapshot.sh`
- Repo-level launchd installer:
  - `~/.agents/scripts/install-codex-app-server-snapshot-launchd.sh`
