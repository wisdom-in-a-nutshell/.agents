---
name: codex-agent-loop
description: Understand and apply how the Codex agent loop works, including prompt layering, `model_instructions_file`, `AGENTS.md`, tool iteration, prompt stability, and where App Server primitives fit. Use when designing Codex-native assistants, custom prompts, workspace boot flows, or runtime behavior across repositories and products.
---

# Codex Agent Loop

Use this skill when you need the durable mental model for how Codex actually runs: how prompts are assembled, how tool calls loop back into the next inference, how `model_instructions_file` differs from `AGENTS.md`, and how these ideas relate to App Server threads, turns, and items.

## Start Here

1. Read `references/unrolling-the-codex-agent-loop-source.md` for the high-fidelity article capture with local SVGs.
2. Read `references/unrolling-the-codex-agent-loop.md` for the distilled loop mechanics.
3. Read `references/openai-codex-prompt-loading.md` for official config and `AGENTS.md` behavior.
4. Read `references/unrolling-the-codex-agent-loop-diagrams.md` when you need visual mental models or Mermaid reconstructions.
5. If the task is specifically about App Server protocol or client integration, also use `$codex-app-server`.

## Working Model

- Treat `model_instructions_file` as the base assistant identity layer when behavior must differ from stock Codex.
- Treat `AGENTS.md` as path-local guidance discovered later in the instruction chain.
- Treat tool calls as part of the core loop, not as exceptional behavior.
- Treat prompt stability as an engineering concern: stable early prompt content improves consistency and caching.
- Keep exact protocol fields and config semantics in references, not in the main skill body.

## Design Defaults

- Separate base assistant identity from local workspace guidance.
- Avoid overlapping always-load files that all redefine the same assistant role.
- Prefer append-only context growth over rewriting the early prompt shape when possible.
- Use local overrides only when they are durable and path-specific.
- Reach for this skill for mental models; reach for exact docs or the App Server skill for implementation details.

## Reference Policy

1. Treat `references/unrolling-the-codex-agent-loop-source.md` as the primary source capture from the OpenAI blog.
2. Treat `references/unrolling-the-codex-agent-loop.md` as the primary distilled conceptual summary.
3. Treat `references/openai-codex-prompt-loading.md` as the primary source for official config and instruction-loading behavior.
4. Use `references/unrolling-the-codex-agent-loop-diagrams.md` for visual reconstructions.
5. When App Server protocol details matter, defer to `$codex-app-server` and official App Server docs.

## References

- `references/unrolling-the-codex-agent-loop-source.md`
- `references/unrolling-the-codex-agent-loop.md`
- `references/openai-codex-prompt-loading.md`
- `references/unrolling-the-codex-agent-loop-diagrams.md`
