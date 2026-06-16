# Skill Design Reference

Use this reference when designing or reviewing the content of a skill.

## Core Principles

Skills are compact onboarding guides for a domain, workflow, tool, or file type.
They should provide procedural knowledge that the model would otherwise have to
rediscover.

Keep the context budget in mind. Codex is already capable, so include only
knowledge that is specific, fragile, local, or expensive to infer.

Prefer concise examples over broad explanations. Every paragraph should justify
its context cost.

## Degrees of Freedom

- Use text instructions when several approaches are valid and decisions depend
  on context.
- Use pseudocode or parameterized scripts when a preferred pattern exists but
  some variation is expected.
- Use specific scripts with few parameters when operations are fragile,
  repeated, or need deterministic behavior.

## Skill Anatomy

Every skill has a required `SKILL.md`:

- Frontmatter contains exactly `name` and `description`.
- `description` is the trigger surface. Put all "when to use" information there.
- The body contains instructions loaded only after the skill triggers.

Recommended optional resource folders:

- `agents/openai.yaml`: UI-facing metadata for skill lists and chips.
- `scripts/`: executable helpers for deterministic or repeated operations.
- `references/`: context that should load only when needed.
- `assets/`: files used in output, such as templates, icons, fonts, or images.

Do not add README, installation guide, quick reference, changelog, or similar
auxiliary documentation unless the user explicitly asks.

## Bundled Resources

Use `scripts/` when the same code would be rewritten repeatedly or reliability
matters. Test added scripts by running them.

Use `references/` for schemas, API docs, policies, workflow variants, or longer
examples. Keep reference files directly linked from `SKILL.md`; avoid nested
reference-chasing. For files longer than 100 lines, put a short table of
contents near the top.

Use `assets/` for materials that should be copied or transformed into outputs.
Do not load assets into context unless inspection is necessary.

## Progressive Disclosure

Skills load in three layers:

1. Metadata: `name` and `description`, always visible.
2. `SKILL.md` body: loaded when the skill triggers.
3. Bundled resources: loaded or executed only when needed.

Keep `SKILL.md` to the core workflow and navigation. Move detailed variant
instructions into one-level reference files, for example:

```text
cloud-deploy/
├── SKILL.md
└── references/
    ├── aws.md
    ├── azure.md
    └── gcp.md
```

## Skill Naming

- Use lowercase letters, digits, and hyphens only.
- Normalize user-provided titles to hyphen-case.
- Keep generated names under 64 characters.
- Prefer short, action-oriented names.
- Namespace by tool when it improves triggering, such as `gh-address-comments`.
- Name the skill folder exactly after the skill name.

## Skill Content Workflow

1. Understand concrete user prompts that should trigger the skill.
2. Identify reusable scripts, references, and assets from those examples.
3. Scaffold new managed skills with `scripts/init_skill.py`.
4. Write or edit resources before finalizing `SKILL.md`.
5. Validate the skill folder.
6. Forward-test complex or fragile skills against realistic prompts when useful.
7. Iterate from observed failures and convert repeatable fixes into durable
   instructions or helpers.
