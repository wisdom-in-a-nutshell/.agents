---
name: managed-skill-bootstrap
description: Bootstrap upstream skills into the `~/.agents` managed registry and target repos. Use when a user provides a `skills.sh` URL or upstream skill ref and wants it imported, registered, synced, and linked reproducibly instead of installed ad hoc.
---

# Managed Skill Bootstrap

Use this skill when the task is not deciding *whether* something is `external` or `owned`, but executing the canonical bootstrap flow for an upstream skill.

This skill is specific to the `~/.agents` control-plane repo.

## Use This For

- `skills.sh` URL -> managed external skill
- upstream skill ref -> managed external skill
- "install this skill into repo X"
- "bootstrap this external skill"
- "wire this skill into codexclaw"

## Do Not Use This For

- deciding `external` vs `owned` vs `repo-local` from scratch
- creating a brand new locally authored skill
- promoting an existing repo-local skill to managed owned

Use `$skill-router` for those routing decisions.

## Canonical Command

Run the repo script from `~/.agents`:

```bash
./scripts/bootstrap-skill.sh <skills.sh-url-or-upstream-ref> --repo <repo> --apply
```

Examples:

```bash
./scripts/bootstrap-skill.sh https://skills.sh/microsoft/skills/copilot-sdk --repo codexclaw --apply
./scripts/bootstrap-skill.sh openai/skills:skills/.curated/openai-docs@main --repo win --apply
```

## What The Script Does

1. Parse the `skills.sh` URL or `upstream_ref`.
2. Add or update the managed external entry in `skills/registry.json`.
3. Import the canonical source under `skills-source/external/<skill>/`.
4. Sync managed skill links into the target repo or global runtime as needed.
5. Regenerate derived registry artifacts.

## Defaults

- Prefer `scope: repo` when the user names one or more target repos.
- Prefer `scope: global` only when the skill clearly belongs in the small cross-repo default kit.
- If the skill already exists as `global`, do not create a redundant repo-scoped duplicate.
- Edit canonical sources and registry state only. Do not hand-edit repo symlink destinations.

## Validation

After bootstrap:

1. Confirm the canonical source exists under `skills-source/external/<skill>/`.
2. Confirm the target repo symlink exists under `<repo>/.agents/skills/<skill>`.
3. Confirm generated registry artifacts are in sync.

## Notes

- The script is the executable source of truth. Keep workflow policy here, but keep mutation logic in `scripts/bootstrap-skill.py`.
- If the bootstrap flow grows meaningfully, extend the script and keep this skill focused on when and how to use it.
