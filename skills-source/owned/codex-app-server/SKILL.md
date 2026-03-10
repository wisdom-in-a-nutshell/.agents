---
name: "codex-app-server"
description: "Use when implementing or reviewing Codex App Server integrations (initialize/thread/turn/item lifecycle, streaming events, approvals, transport behavior, and client architecture). Keep the local references for conceptual grounding, but fetch current protocol and config details from the OpenAI docs MCP (`openaiDeveloperDocs`) whenever behavior needs to be exact or up to date."
---

# Codex App Server

Use this skill when building around Codex App Server primitives. Keep the client/harness thin and deterministic.

## Overview

Use this file for quick orientation and durable mental models only. For exact protocol fields, approvals, config keys, transport details, and other evolving behavior, fetch the current official docs via MCP (`openaiDeveloperDocs`).

## What App Server Is

Codex App Server is the stable, client-friendly JSON-RPC surface that exposes the Codex harness to UIs and partner integrations.

- It hosts Codex threads as durable runtime sessions behind a bidirectional protocol.
- It turns lower-level harness activity into UI-ready thread, turn, item, delta, and approval events.
- It lets clients reuse the same Codex harness across different surfaces without re-implementing the agent loop.
- It is the first-class integration surface to prefer when you want the full Codex harness instead of a narrower wrapper such as `codex exec` or `codex mcp-server`.

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

- Official docs via MCP (`openaiDeveloperDocs`) (primary source for current behavior)
- Local high-level architecture reference: `references/unlocking-the-codex-harness-high-level.md`
- Local README snapshot reference: `references/openai-codex-app-server-readme-reference.md`
- Live upstream README (latest source for snapshot): `https://raw.githubusercontent.com/openai/codex/refs/heads/main/codex-rs/app-server/README.md`
- App Server docs: `https://developers.openai.com/codex/app-server/`
- CLI reference: `https://developers.openai.com/codex/cli/reference/#codex-app-server`

## Reference Policy

1. Start with this file plus `references/unlocking-the-codex-harness-high-level.md` when you need the conceptual model for what App Server is and why it exists.
2. When the question is about the exact behavior of the locally installed Codex binary, prefer probing the local app server or generating local schema/types before generalizing from docs.
3. For exact current product behavior beyond the installed binary, fetch the official docs via MCP (`openaiDeveloperDocs`) before answering.
4. Use `references/openai-codex-app-server-readme-reference.md` as a local snapshot and helper reference, not as the canonical source for volatile details.
5. If the local snapshot and official docs disagree, prefer the latest official docs from MCP unless the question is specifically about the currently installed local binary.
6. If the docs are thin on architecture or motivation, use the local conceptual reference to explain the system at a high level without overriding official protocol details.

## Local Probe Workflow

Use the local Codex binary when you need the installed-build-specific protocol surface, method names, request schemas, or runtime-discoverable state.

Preferred local probes:

- `codex app-server generate-json-schema --out <dir>` for the exact local JSON Schema bundle
- `codex app-server generate-ts --out <dir>` for generated local TypeScript protocol bindings
- a live stdio session with `codex app-server` for handshake and request/response probing

Useful live requests after `initialize` + `initialized`:

- `model/list`
- `thread/start`
- `thread/read`
- `turn/start`
- `mcpServerStatus/list`
- `skills/list`
- `app/list`
- `experimentalFeature/list`
- `config/mcpServer/reload`

Use local probes to learn:

- what the installed binary actually supports
- the exact request and response shapes of that build
- which MCP servers, skills, models, apps, and experimental features are visible at runtime

Use official docs MCP to learn:

- the latest documented behavior
- integration guidance and semantics
- current official recommendations and compatibility guidance

## Fetch First For

- transport behavior and supported modes
- thread, turn, and item lifecycle details
- approval request payloads and available decisions
- dynamic tools and experimental API behavior
- config keys, auth behavior, and integration surface changes
- anything the user frames as latest, current, exact, or up to date

## Temporary Snapshot Automation

- Snapshot refresh is maintained by control-plane scripts outside this skill.
- Manual refresh script:
  - `~/.agents/scripts/refresh-codex-app-server-readme-reference.sh`
- Repo-level launchd installer:
  - `~/.agents/scripts/install-codex-app-server-snapshot-launchd.sh`
