# Agents Skill Control-Plane Lifecycle

Use this reference for exact paths, registry entries, and commands in
`/Users/dobby/GitHub/agents`.

## Paths

- Control-plane repo: `/Users/dobby/GitHub/agents`
- Managed owned skills: `skills-source/owned/<skill>`
- Managed external skills: `skills-source/external/<skill>`
- Registry: `skills/registry.json`
- Global runtime links: `~/.agents/skills/<skill>`
- Repo-local skill location: `<repo>/.agents/skills/<skill>`
- Repo targets in managed `repos`: repo names under `/Users/dobby/GitHub` or
  explicit repo roots such as `/Users/dobby/GitHub/agents`

## Managed Owned Registry Entry

Use `owned` for local skills that should be centrally maintained:

```json
{
  "skill": "<skill-name>",
  "origin": "owned",
  "scope": "repo",
  "repos": ["target-repo"],
  "source_path": "skills-source/owned/<skill-name>",
  "upstream_ref": "-"
}
```

Use `scope: global` with `repos: []` only for the small default kit.

## Managed External Registry Entry

Use `external` for upstream skills that should remain refreshable:

```json
{
  "skill": "<skill-name>",
  "origin": "external",
  "scope": "repo",
  "repos": ["target-repo"],
  "source_path": "skills-source/external/<skill-name>",
  "upstream_ref": "owner/repo:path/to/skill@ref"
}
```

Import or refresh external source after changing the entry:

```bash
cd /Users/dobby/GitHub/agents
./scripts/refresh-external-skills.sh --apply --skill <skill-name>
```

## Bootstrap Shortcut

For a `skills.sh` URL or upstream reference, prefer:

```bash
cd /Users/dobby/GitHub/agents
./scripts/bootstrap-skill.sh <skills.sh-url-or-upstream-ref> --repo <repo> --apply
```

This parses the upstream ref, adds or updates the managed external entry,
refreshes the source, syncs skill links, and regenerates repo bootstrap
artifacts.

Defaults:

- Prefer `scope: repo` when the user names a target repo.
- Prefer `scope: global` only for broadly useful default skills.
- Do not create a redundant repo-scoped duplicate when the skill is already
  global.

## Repo-Local Skill

Keep a skill repo-local when it is specific to one repo:

1. Store it in `<repo>/.agents/skills/<skill>`.
2. Add `{ "repo": "<repo>", "skill": "<skill>" }` to
   `unmanaged_repo_local_skills` in `skills/registry.json`.
3. Do not add a managed entry unless promoting it.

## Promote Repo-Local to Managed Owned

1. Copy or move `<repo>/.agents/skills/<skill>` to
   `skills-source/owned/<skill>`.
2. Add a managed `owned` registry entry, usually `scope: repo` first.
3. Remove the old unmanaged repo-local entry when the managed link replaces it.
4. Run bootstrap/check.

## Adopt External to Owned

Use this when an imported external skill has become local infrastructure or has
intentionally drifted from upstream:

```bash
git mv skills-source/external/<skill> skills-source/owned/<skill>
```

Then change its registry entry:

```json
{
  "skill": "<skill>",
  "origin": "owned",
  "scope": "repo",
  "repos": ["target-repo"],
  "source_path": "skills-source/owned/<skill>",
  "upstream_ref": "-"
}
```

Run bootstrap/check after the registry edit.

## Sync and Check

After any `skills/registry.json` change:

```bash
cd /Users/dobby/GitHub/agents
./scripts/bootstrap-machine-agent-control-planes.sh --apply
./scripts/check-fast.sh
```

For intentional repo-scoped troubleshooting:

```bash
cd /Users/dobby/GitHub/agents
./scripts/bootstrap-machine-agent-control-planes.sh --apply --repo <repo-root>
./scripts/check-agent-control-planes.sh --repo <repo-root>
```

Use `scripts/sync-skills-registry.sh` only for focused troubleshooting; the
shared bootstrap wrapper keeps Codex and Claude surfaces aligned.

## Safety

- Edit canonical skill sources, not symlink destinations.
- Keep distribution link-only.
- Do not add additional mapping manifests.
- If bootstrap creates tracked repo-local links, stage those links with the
  canonical source and registry change, not unrelated files.
