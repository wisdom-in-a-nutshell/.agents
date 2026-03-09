# Prompt Layering

Use this reference when deciding whether behavior belongs in `model_instructions_file`, `AGENTS.md`, local data files, or later turn context.

## Core Split

The Codex loop separates:

- base `instructions`
- `tools`
- later `input` items such as project guidance, environment context, user messages, and appended tool outputs

This is why `model_instructions_file` and `AGENTS.md` are not interchangeable.

## Practical Layer Split

### 1. `model_instructions_file`

Use for the base assistant contract:

- who the assistant is
- what it optimizes for
- privacy and external-action policy
- default proactivity style
- whether coding is the default mode or one capability among many

This is the right place when the product intentionally wants behavior different from stock Codex.

### 2. `AGENTS.md`

Use for path-local boot behavior:

- what to read first in this repository or folder
- local working agreements
- path-based overrides
- durable local rules that should load later in the prompt chain

Do not use `AGENTS.md` as a second competing base identity layer if the base prompt already defines the assistant role.

### 3. Local human/context files

Use separate files when they are data rather than instructions:

- user facts
- profile/context notes
- durable memory
- current working context

These files can be referenced by local guidance, but they should not all try to redefine the assistant persona.

## Decision Rule

Ask one question:

"Is this base identity, path-local guidance, or mutable context?"

- base identity -> `model_instructions_file`
- path-local guidance -> `AGENTS.md`
- mutable context -> local data/memory files

## Design Defaults

- Prefer one canonical assistant-identity source.
- Keep changing context out of the base prompt.
- Use local overrides only when they are truly local and durable.
- Avoid overlapping always-load files that restate the same assistant role in different words.
