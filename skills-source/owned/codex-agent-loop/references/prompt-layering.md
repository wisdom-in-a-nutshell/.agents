# Prompt Layering

Use this reference when deciding whether behavior belongs in `model_instructions_file`, workspace `AGENTS.md`, `USER.md`, or memory files.

## Core Codex Loop Implication

The Codex agent-loop model separates:

- base `instructions`
- `tools`
- later `input` items such as project instructions and user context

For workspace design, this means `model_instructions_file` and `AGENTS.md` are different layers with different jobs.

## Practical Layer Split

### 1. `model_instructions_file`

Use for the base assistant contract:

- who the assistant is
- what it optimizes for
- privacy and external-action policy
- default proactivity style
- whether coding is the default mode or just one capability

This is the right place when the product intentionally wants behavior different from stock Codex.

### 2. Workspace `AGENTS.md`

Use for local boot behavior:

- what files to read first
- how the workspace is organized
- where current context lives
- when to read deeper mode-specific files

Do not use this as a second competing "soul" file if `model_instructions_file` already defines the assistant identity.

### 3. `USER.md`

Use for stable facts about the human:

- preferences
- communication style
- operating context
- durable facts that should not be phrased as assistant behavior

### 4. Memory files

Use for changing context:

- active priorities
- recent events
- durable memory
- archives

Memory should evolve. Identity should not churn every day.

## Design Defaults For `codexclaw-workspaces`

- If the goal is a personal executive-assistant/buddy, a custom `model_instructions_file` is the long-term canonical identity layer.
- A workspace root `AGENTS.md` is still useful for startup routing, but should stay small once the base prompt exists.
- `SOUL.md` and `IDENTITY.md` should not remain permanent always-load competitors with the base prompt.
- If needed, merge their durable assistant-identity content into `model_instructions_file`.

## Decision Rule

Ask one question:

"Is this defining the assistant, the human, or the current context?"

- Assistant -> `model_instructions_file`
- Human -> `USER.md`
- Current context -> memory
- Workspace loading/routing -> `AGENTS.md`

## When To Reintroduce Local Overrides

Use nested `AGENTS.md` only when a folder represents a real mode boundary, for example:

- `coaching/`
- a future mode with meaningfully different startup context

If the difference is not local and durable, do not add another instruction file.
