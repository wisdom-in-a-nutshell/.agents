---
name: "codex-app-server"
description: "Use when building this repo around the Codex App Server. Summarizes the JSONL/stdio protocol (initialize, thread/turn lifecycle, streaming items, approvals) and how to design a thin client/harness around it."
---

# Codex App Server (Project Harness)

We are building a personal assistant by putting a small "product layer" around the Codex App Server (Codex harness). We are not re-implementing the agent loop.

## Source Of Truth

- Prefer OpenAI Developer Docs as the source of truth.
- This repo is configured with the OpenAI docs MCP server (`openaiDeveloperDocs`). When anything is unclear or might have changed, search/fetch the official docs (Codex App Server, CLI reference, config, MCP, skills).
- When working on Codex/App Server, always use the `openaiDeveloperDocs` MCP tools to pull the **latest** docs into context (search, then fetch the exact page/section) rather than relying on memory or a vendored snapshot.
- Treat this skill as **orientation + durable defaults**, not a spec. If it diverges from docs, update it.

## Primary References

Consult these before implementing anything new:

- App Server docs (protocol + API + event stream): `https://developers.openai.com/codex/app-server/`
- CLI reference (how to launch transports): `https://developers.openai.com/codex/cli/reference/#codex-app-server`
- Background / design rationale (conceptual): `https://openai.com/index/unlocking-the-codex-harness/`
- Live upstream README (latest): `https://raw.githubusercontent.com/openai/codex/refs/heads/main/codex-rs/app-server/README.md`
- Local snapshot reference: `references/openai-codex-app-server-README.snapshot.md`

## What The App Server Gives You (Mental Model)

- A long-running process you talk to via **JSON-RPC-style** messages over:
  - `stdio` (default): newline-delimited JSON (JSONL)
  - `ws://` (experimental): one JSON message per WebSocket text frame
- Durable **threads** with **turns** made of streaming **items**.
- A bidirectional protocol:
  - The client sends requests (start/resume threads, start turns, etc.)
  - The server streams notifications (items, diffs, plans, progress)
  - The server can also send **server-initiated requests** (approvals, auth refresh, etc.) that the client must answer

Protocol note: the wire format is JSON-RPC 2.0 shaped, but **omits** the `"jsonrpc":"2.0"` header.

## Core Primitives (Thread / Turn / Item)

- **Thread**: durable conversation container (many turns).
- **Turn**: one unit of work initiated by user input (many items).
- **Item**: atomic unit in the event stream (user message, agent message, command execution, file change, tool call, compaction, review mode, etc.).

Items have a lifecycle:
- `item/started`
- optional `item/*/delta` notifications for streaming types (e.g. `item/agentMessage/delta`)
- `item/completed` (treat as authoritative final state)

## Tooling (Including Web Search)

Codex can expose built-in tools (shell, patching, planning, etc.) and may also expose a **web search** tool depending on your Codex configuration. Treat web search as:

- Available only if enabled by config and runtime policy.
- Often "cached index" by default; "live" access (fetching current pages) is a stricter setting and depends on network/sandbox policy.

For anything beyond built-ins, wire tools in via MCP servers.

## Experimental Surface Area

Some methods/fields are gated behind an **experimental API** capability. Default to stable:

- During `initialize`, omit `capabilities` or set `capabilities.experimentalApi=false`.
- Only enable `experimentalApi=true` when the docs explicitly require it for a feature we need.

## Best Practices (From Codex Harness / Agent Loop Writeups)

These are practical constraints that keep Codex efficient and reliable:

- Keep the **tools list stable** across turns in a thread. Changing tools mid-thread can cause expensive cache misses and behavior shifts.
- Ensure any client-side tool lists are **deterministically ordered**. Non-deterministic tool ordering can reduce caching effectiveness.
- Avoid switching **model** mid-thread unless necessary (also affects caching and behavior).
- Avoid changing **sandbox policy / approval mode / cwd** mid-thread. If you must represent a change, prefer the “append a new context item/event” approach (do not rewrite earlier prompt context).
- Keep “static” instructions and structure stable; put “variable” information at the end. Cache hits require exact prefix matches.
- Prefer **durable thread ids**: treat `threadId` as the stable unit you can resume from any client; keep your client stateless aside from the `threadId` and minimal UX state.
- Let Codex handle **compaction** rather than inventing your own summarization pipeline.

## Client Lifecycle (Minimum)

1. Spawn the server process:
   - Local: `codex app-server`
   - Remote (recommended early): run it on macmini and connect via SSH so you do not expose a new network service yet.
2. Send `initialize` once per connection, then `initialized`.
3. Start or resume a thread:
   - `thread/start` (new)
   - `thread/resume` (existing id)
4. Start a turn with user input: `turn/start`.
5. Stream notifications from stdout until `turn/completed`.
6. Persist the `threadId` client-side so you can `thread/resume` later from any device.

## Events To Expect

- Thread: `thread/started`
- Turn: `turn/started`, `turn/completed`
- Items: `item/started`, `item/*/delta` (for streaming types), `item/completed`
- Approvals: the server can send a request asking the client to allow/deny an action; a turn may pause until you reply.

## Optional: Generate Typed Bindings

When you build a richer client, prefer generating types from the exact Codex version you run:

- `codex app-server generate-ts --out ./schemas`
- `codex app-server generate-json-schema --out ./schemas`

## Design Rules For This Repo

- Keep state minimal: prefer Codex thread persistence + a small set of markdown "memory" files in-repo.
- Capability-first rule: before adding custom memory, workflow, or integration code, verify in official Codex/App Server docs whether a first-class primitive already exists; only add custom shims for confirmed gaps.
- Do not build a parallel agent loop.
- Be Codex-native: prefer Codex **apps/connectors**, **skills**, and **MCP servers** over bespoke integrations whenever possible.
- Build a thin, stable client that can run on other machines and talk to the macmini-hosted server over SSH (later: replace transport with a secure tunnel/daemon if needed).

## Docs Pointers (Consult Via MCP)

When implementing or debugging, consult the official docs via the MCP server:

- Codex App Server: protocol, lifecycle, methods, notifications, approval flow
- Configuration: project-scoped `.codex/config.toml`, enabling/disabling features (including web search behavior)
- MCP: adding tool servers safely and predictably
- For protocol-level details, cross-check the local snapshot in `references/openai-codex-app-server-README.snapshot.md`
