---
name: codex-agent-loop
description: Capture and apply Codex agent-loop mental models inside `codexclaw-workspaces`, especially when deciding what belongs in `model_instructions_file`, workspace `AGENTS.md`, `USER.md`, and memory files. Use when working on assistant identity, workspace boot behavior, prompt layering, or Codex-loop-informed personal-agent architecture for Adi or Angie profiles.
---

# Codex Agent Loop

Use this skill when shaping how a Codex-backed personal assistant should boot inside `codexclaw-workspaces`. Keep the Codex/App Server runtime model intact, but design the workspace so the assistant feels like a long-lived personal helper rather than a generic coding agent.

## Start Here

1. Read `docs/projects/personal-agent-workspace-architecture/tasks.md`.
2. Read the repository root `AGENTS.md`, then the relevant profile `AGENTS.md`.
3. If working on a profile-specific question, read that profile's `USER.md` and only the memory files needed for the task.
4. Read `references/prompt-layering.md` when the question is about `model_instructions_file`, `AGENTS.md`, or Codex agent-loop behavior.

## Working Model

- Treat `model_instructions_file` as the base assistant identity layer when the product intentionally wants behavior different from stock Codex.
- Treat workspace `AGENTS.md` as local boot and routing guidance, not the main identity layer once a custom base prompt exists.
- Treat `USER.md` as stable facts about the human, not as assistant behavior.
- Treat memory files as mutable context, not as identity.
- Keep one canonical answer to "who am I?" and avoid overlapping always-load files that restate the same role in different words.

## Design Defaults

- Prefer one canonical assistant-identity source.
- Keep base assistant behavior separate from changing user facts and changing memory.
- Use nested `AGENTS.md` only for materially different local modes such as `coaching/`.
- Keep this repo focused on durable private workspace data; runtime session state belongs elsewhere.
- When a rule belongs to Codex/App Server runtime mechanics rather than workspace structure, document it in `codexclaw`, not here.

## Design Questions

- If the assistant still feels like a stock coding agent, revisit the custom `model_instructions_file`.
- If `SOUL.md`, `IDENTITY.md`, and `AGENTS.md` overlap, consolidate.
- If a behavior changes by mode, prefer a mode-local override over growing the global base prompt.
- If a rule is about file loading order or workspace navigation, keep it close to the workspace layer.

## References

- `references/prompt-layering.md`
- `docs/projects/personal-agent-workspace-architecture/tasks.md`
