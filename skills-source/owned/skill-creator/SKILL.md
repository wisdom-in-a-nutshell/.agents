---
name: skill-creator
description: Create, update, route, adopt, promote, import, validate, register, and distribute agent skills through the `/Users/dobby/GitHub/agents` control-plane repo. Use when Codex needs to decide whether a skill belongs in `owned`, `external`, `repo-local`, or `dormant`; scaffold or edit SKILL.md/resources; generate agents/openai.yaml; update `skills/registry.json`; refresh upstream skills; or run bootstrap/check so skill runtime links stay reproducible.
---

# Skill Creator

Use this as the canonical lifecycle skill for agent skills in
`/Users/dobby/GitHub/agents`. It absorbs the old skill-router role:
placement decisions, registry ownership, creation, promotion, refresh, sync,
and validation belong in one workflow.

## Scope

- Apply `/Users/dobby/GitHub/agents/AGENTS.md` first when working in this repo.
- If the current repo is not `/Users/dobby/GitHub/agents`, decide placement and
  list exact control-plane changes unless the user explicitly asked to edit the
  agents repo.
- Edit canonical sources, not generated runtime symlinks under `.agents/skills`,
  `.claude/skills`, or `~/.agents/skills`.
- Keep `skills/registry.json` as the only mapping manifest.

## Read References

- Read `references/skill_design.md` before writing a substantial new `SKILL.md`,
  choosing bundled resources, splitting references, or reviewing skill quality.
- Read `references/control_plane_lifecycle.md` when updating
  `skills/registry.json`, importing an external skill, promoting repo-local
  skills, or choosing exact bootstrap/check commands.
- Read `references/openai_yaml.md` before creating or updating
  `agents/openai.yaml`.

## Placement Decision

Choose placement before creating or editing files:

1. Use `external` when the source is upstream and should remain refreshable.
2. Use `owned` when the skill is authored locally and should be reusable across
   one or more repos.
3. Use `repo-local` when the skill is specific to one repo and should stay in
   that repo.
4. Use managed `scope: dormant` when the source should stay tracked but should
   not be linked into any runtime.
5. Default to the narrowest useful scope. Prefer `scope: repo` or `dormant`
   over `global` unless the skill clearly belongs in the small default kit for
   unrelated repos.
6. When a skill depends on a repo-level MCP preset, align the repo-scoped skill
   targets with repos declaring that preset in `codex/config/repo-bootstrap.json`.
7. If placement is still ambiguous after inspecting context, ask one question:
   "Should this be external, owned, repo-local, or dormant?"

## Standard Workflow

1. Understand the intended use with concrete examples. Skip only when the usage
   pattern is already clear from the request or existing skill.
2. Route placement using the decision rules above.
3. Plan reusable resources: scripts for deterministic/repeated operations,
   references for context that should load only when needed, and assets for
   output files/templates.
4. Create or edit the canonical skill source.
5. Generate or update `agents/openai.yaml`.
6. Validate the skill folder.
7. Update registry/distribution when the skill is managed by this repo.
8. Run the required bootstrap/check commands.
9. Iterate from real use and update durable instructions when the skill exposes
   a repeatable gap.

## Creating Managed Owned Skills

For new owned skills in this repo, scaffold under
`/Users/dobby/GitHub/agents/skills-source/owned`:

```bash
python3 /Users/dobby/GitHub/agents/skills-source/owned/skill-creator/scripts/init_skill.py <skill-name> --path /Users/dobby/GitHub/agents/skills-source/owned
```

Use `--resources scripts,references,assets` only for resource directories the
skill actually needs. Use `--examples` only when placeholder examples help and
delete any placeholders before finishing.

After scaffolding:

- Replace TODOs in `SKILL.md`.
- Add only useful scripts, references, or assets.
- Test added scripts by running them.
- Generate `agents/openai.yaml` with explicit interface values.
- Validate with `scripts/quick_validate.py`.
- Add a managed `owned` registry entry with the narrowest useful scope.
- Run bootstrap/check.

## Updating Existing Skills

- Preserve the skill name unless the user asked for a rename.
- Keep frontmatter to exactly `name` and `description`.
- Put all trigger/use information in the frontmatter description; the body loads
  only after the skill triggers.
- Keep `SKILL.md` lean. Move detailed variants, schemas, examples, and long
  policy into directly linked files under `references/`.
- Keep information in one place; do not duplicate detailed guidance between
  `SKILL.md` and references.
- Regenerate `agents/openai.yaml` when the skill's scope or user-facing behavior
  changes.
- Run validation after edits.

## Importing External Skills

When the user gives a `skills.sh` URL or upstream reference and no special
handling is needed, prefer the canonical bootstrap helper:

```bash
cd /Users/dobby/GitHub/agents
./scripts/bootstrap-skill.sh <skills.sh-url-or-upstream-ref> --repo <repo> --apply
```

Use managed `external` entries only for skills that should remain refreshable
from upstream. If an imported skill becomes local infrastructure or intentionally
drifts, adopt it into `skills-source/owned/<skill>` and change `upstream_ref` to
`"-"`.

## Repo-Local and Promotion

- Keep a skill repo-local at `<repo>/.agents/skills/<skill>` when it is specific
  to one repo.
- Record repo-local skills in `unmanaged_repo_local_skills` for visibility.
- Promote a repo-local skill to managed owned when it becomes reusable or needs
  central distribution.
- For repo-scoped managed skills, prefer `scope: repo` first and use `global`
  only when it belongs in the small default kit.

## Registry and Distribution

When `skills/registry.json` changes, run sync/check in the same change:

```bash
cd /Users/dobby/GitHub/agents
./scripts/bootstrap-machine-agent-control-planes.sh --apply
./scripts/check-fast.sh
```

Use scoped bootstrap/check only when intentionally limiting a repo-scoped run:

```bash
cd /Users/dobby/GitHub/agents
./scripts/bootstrap-machine-agent-control-planes.sh --apply --repo <repo-root>
./scripts/check-agent-control-planes.sh --repo <repo-root>
```

If bootstrap creates tracked repo-local links, stage those generated links with
the canonical skill source and registry change. Do not stage unrelated
session-memory or work-in-progress files merely because lifecycle hooks touched
them.

## Validation Commands

Validate a single skill:

```bash
python3 /Users/dobby/GitHub/agents/skills-source/owned/skill-creator/scripts/quick_validate.py /path/to/skill-folder
```

Regenerate OpenAI UI metadata:

```bash
python3 /Users/dobby/GitHub/agents/skills-source/owned/skill-creator/scripts/generate_openai_yaml.py /path/to/skill-folder --interface display_name="..." --interface short_description="..." --interface default_prompt="Use $skill-name to ..."
```

## Safety Rules

- Do not hand-edit rendered runtime links or generated repo-local control-plane
  surfaces.
- Do not add README, changelog, installation guide, or other auxiliary docs to a
  skill unless the user explicitly asks; skills should contain only what agents
  need to do the job.
- Do not add compatibility shims or legacy fallbacks unless explicitly required.
- Keep temporary artifacts under the owning repo's `tmp/` directory and remove
  disposable scratch files before finishing.
