# Unlocking The Codex Harness: High-Level Notes

Use this note for the durable conceptual model of Codex App Server. Do not treat it as the source of truth for exact fields or current protocol behavior; fetch official docs via `openaiDeveloperDocs` for that.

## What App Server Is

Codex App Server is the stable JSON-RPC integration surface for the Codex harness.

- The Codex harness is the broader runtime: the agent loop, thread persistence, config/auth loading, and tool execution policy.
- App Server exposes that harness to clients in a client-friendly, bidirectional protocol.
- Different surfaces can reuse the same harness without re-implementing Codex core behavior.

## Why It Exists

The App Server grew out of a practical need to reuse the Codex harness across multiple products.

- The CLI/TUI came first.
- The VS Code extension needed the same harness behind an IDE-friendly UI.
- More clients later needed the same behavior: desktop, web, partner IDEs, and multi-agent surfaces.
- That pushed the team toward a stable, backward-compatible protocol instead of product-specific bindings.

## Core Runtime Picture

At a high level:

- a client sends JSON-RPC requests
- the App Server translates those requests into Codex core operations
- a thread manager owns durable thread runtimes
- Codex core emits lower-level events
- the App Server translates those events back into stable, UI-ready notifications

One client request can therefore produce many streamed updates.

## Three Conversation Primitives

- `thread`: durable container for an ongoing Codex session
- `turn`: one unit of agent work started by a user input
- `item`: atomic typed unit of input or output inside a turn

The usual item lifecycle is:

- `item/started`
- optional `item/*/delta`
- `item/completed`

## Why The Protocol Feels UI-Friendly

The protocol is designed around how agent work actually unfolds in a product UI.

- work is not a single request/response
- progress can stream incrementally
- approvals can pause execution
- diffs, commands, and messages need their own typed lifecycle
- a client may disconnect and later reconnect to the same persisted thread

## Integration Guidance

Prefer App Server when you want the full Codex harness:

- durable threads
- approvals
- streamed items and deltas
- config and auth flows
- full client-driven interaction

Use narrower surfaces only when that smaller contract is enough:

- `codex exec` for one-shot automation
- `codex mcp-server` when Codex only needs to appear as a tool inside an MCP workflow

## Source

Distilled from the February 4, 2026 OpenAI engineering post "Unlocking the Codex harness: how we built the App Server."
