---
name: codex-agent-loop
description: "Understand and apply how the Codex agent loop works, including request assembly (`instructions`, `tools`, `input`), thread/turn/item mental models, tool iteration, prompt growth, caching, compaction, and where `model_instructions_file` and `AGENTS.md` enter. Keep the local references for the durable conceptual model, but fetch current official docs via `openaiDeveloperDocs` for exact config, prompt-loading, and other evolving Codex behavior."
---

# Codex Agent Loop

Use this skill when you need the durable mental model for how Codex actually runs: how the initial request is assembled, how inference and tool calls loop within a turn, how conversation state grows across turns, and where `model_instructions_file`, `AGENTS.md`, and local guidance enter.

## Read Order

1. Read `references/unrolling-the-codex-agent-loop.md` for the end-to-end model of threads, turns, items, and tool iteration.
2. Read `references/building-the-initial-prompt.md` for the first request, prompt item ordering, tool definitions, and SSE event flow.
3. Read `references/conversation-growth-and-performance.md` for prompt growth, exact-prefix caching, statelessness, `previous_response_id`, ZDR, and compaction.
4. Read `references/openai-codex-prompt-loading.md` only when exact `model_instructions_file`, `AGENTS.md`, or project config semantics matter.
5. Read `references/prompt-layering.md` only when deciding what belongs in the base prompt versus local guidance or mutable context.

## Core Model

- A `thread` is the durable conversation container.
- A `turn` begins with a new user request and may contain many inference and tool-call iterations before it ends.
- The Responses API request surface is structured as `instructions`, `tools`, and `input`; the server derives the actual prompt shape from those parts.
- Tool calls are part of the normal loop, and their outputs are appended back into later `input` items.
- Stable early prompt content matters because it affects both behavior and prompt caching efficiency.

## Use This Skill Well

- Start with the conceptual reference before reading the lower-level details.
- If the question is narrow, load only the specific reference that answers it.
- Keep the distinction between base `instructions`, later `input`, and appended tool outputs explicit.
- Preserve the blog's mental model: a turn is not a single model call, and the loop does not end until the assistant emits a final message for that turn.
- Use the embedded SVGs in the references when you want the original diagrams in context.
- Reach for exact docs via MCP when configuration or current product behavior matters.

## Reference Policy

1. Treat `references/unrolling-the-codex-agent-loop.md` as the main reusable explanation another agent should remember.
2. Treat `references/building-the-initial-prompt.md` and `references/conversation-growth-and-performance.md` as the detailed mechanics that preserve most of the blog's substance.
3. Fetch official docs via `openaiDeveloperDocs` before answering questions about exact current prompt loading, `AGENTS.md` discovery, fallback filenames, byte limits, config keys, or other evolving behavior.
4. Treat `references/openai-codex-prompt-loading.md` as a local helper summary of official guidance, not a replacement for checking current docs when precision matters.

## Fetch First For

- `model_instructions_file` and config-key semantics
- `AGENTS.md` discovery order, fallback filenames, and byte limits
- project-scoped `.codex/config.toml` behavior
- current Codex config reference details
- any question phrased as latest, current, official, exact, or up to date

## References

- `references/building-the-initial-prompt.md`
- `references/conversation-growth-and-performance.md`
- `references/unrolling-the-codex-agent-loop.md`
- `references/openai-codex-prompt-loading.md`
- `references/prompt-layering.md`
