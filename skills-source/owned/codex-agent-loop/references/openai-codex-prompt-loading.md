# OpenAI Codex Prompt Loading

Primary sources:

- `https://developers.openai.com/codex/config-reference/`
- `https://developers.openai.com/codex/guides/agents-md/`
- `https://developers.openai.com/codex/config-advanced/`

Use this reference when you need the official behavior for `model_instructions_file`, `AGENTS.md`, and project-scoped Codex config.

## Key Official Rules

### `model_instructions_file`

The Codex config reference describes `model_instructions_file` as a replacement for built-in instructions instead of `AGENTS.md`.

Implication:

- setting `model_instructions_file` changes the base instruction layer
- it is not just another local override file

### `AGENTS.md` discovery

The AGENTS guide says Codex builds an instruction chain when it starts.

Discovery order:

1. global `~/.codex/AGENTS.override.md` or `~/.codex/AGENTS.md`
2. project root down to the current working directory
3. at most one instruction file per directory, with `AGENTS.override.md` preferred over `AGENTS.md`

Merge behavior:

- files are concatenated from root to current directory
- files closer to the current directory appear later and therefore override earlier guidance
- Codex stops once the configured byte limit is reached

### Project-scoped `.codex/config.toml`

The advanced config guide says Codex loads project-scoped `.codex/config.toml` files from project root to the current working directory.

Implications:

- closer config files win for the same key
- project config loads only when the project is trusted
- relative paths in project config resolve from the `.codex/` directory containing that file

## Practical Conclusions

### When to use `model_instructions_file`

Use it when you want to redefine the assistant's base behavior across a product or environment.

Examples:

- a private executive assistant instead of a stock coding agent
- a product-specific assistant with a different default posture
- a highly constrained system where the base identity must be controlled tightly

### When to use `AGENTS.md`

Use it when you want local, path-based guidance.

Examples:

- repository-specific rules
- subtree-specific overrides
- local loading/routing instructions

### When not to confuse them

Do not assume `AGENTS.md` can fully substitute for the base prompt layer.

Do not assume `model_instructions_file` is just another local project note.

They enter the Codex prompt stack differently and solve different problems.
