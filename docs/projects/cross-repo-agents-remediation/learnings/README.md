# Project Learnings

## Summary
- This project remediates the mistaken nested `AGENTS.md` model across multiple repos and replaces it with a root-only `AGENTS.md` contract plus migrated docs.
- It is worth capturing learnings because the same misunderstanding affected a broad portfolio and the cleanup will expose better defaults for AGENTS, docs placement, delegation, and shipping.
- Keep appending to this file during the run whenever something would have made the cleanup faster, safer, or easier to resume.

## What Helped
- The portfolio is already biased toward agent-native repos, so migrating nested guidance into docs should usually be structurally straightforward.
- The root-only contract was easy to apply consistently across very different repos once it was stated plainly: one root `AGENTS.md`, no nested `AGENTS.md`, no `CLAUDE.md`, `docs/architecture/` for system shape, and `docs/references/` for exact facts.
- Fast parent-side verification with `rg --files -g 'AGENTS.md' -g 'CLAUDE.md'`, `git diff --check`, and a quick read of root `AGENTS.md` caught contract regressions cheaply before recycling worker slots.
- One repo per worker with a rolling wave of up to six active workers gave clean ownership boundaries and made it practical to verify and refill slots continuously.

## What Slowed Things Down
- The initial mental model for nested `AGENTS.md` loading was wrong, so guidance was distributed across the wrong surface.
- The first worker relaunch wasted time because the prompt overemphasized the parent control-plane tracker; workers reflected the orchestration setup back instead of just fixing their assigned repos.
- Blind portfolio-wide deletes are only safe when they do not overlap with in-flight repo edits. `CLAUDE.md` deletion was trivial mechanically, but it still needed coordination with active repo workers.

## Improvement Opportunities
### MCPs / Tools
- Keep using quick portfolio inventory scans during long runs. Counting `AGENTS.md` and `CLAUDE.md` across `/Users/dobby/GitHub` made it obvious which repos were still pending and whether active workers were actually collapsing each repo to the target state.

### Skills
- The repo-contract and docs-migration instructions were stable enough to delegate repeatedly. A future version of `$agent-native-repo-playbook` could include a compact "root-only remediation" recipe so the worker prompt can be even shorter.

### AGENTS / Docs
- Do not use nested `AGENTS.md` as navigational aids. If a repo is almost always started from root, local guidance belongs in `docs/architecture/` or `docs/references/`, not in subtree agent files.
- Keep root `AGENTS.md` short. It should state the repo-wide contract and link to docs, not absorb every former nested note.
- Preserve useful content before deletion, but do not preserve stale dated execution notes. Those belong in project trackers, not durable reference docs.

### Validation / Feedback Loops
- Parent verification should be standardized as:
  - only one `AGENTS.md` remains
  - no `CLAUDE.md` remains
  - `git diff --check` passes
  - repo-native validation runs where practical
- Broken local tool shims are a recurring failure mode. Some repos could not run `pnpm` via the configured shim even though direct binaries inside `node_modules/.bin` still worked; future runs should prefer the repo-local binary when available.

### Delegation / Subagents
- Worker prompts must be self-contained and repo-local. They should not mention the parent tracker except to say "do not edit it."
- The parent should own the cross-repo tracker as a single writer. Workers should return repo-local results only.
- Reusing freed slots immediately after parent verification kept throughput high without losing supervision.

## Recommended Follow-Ups
- Capture the final cross-repo contract as a durable example future repos can copy without recreating nested `AGENTS.md` sprawl.
- After this run is fully finished, update the bootstrap/control-plane defaults so new repos start with the root-only contract and do not regenerate nested `AGENTS.md` or `CLAUDE.md` by default.

## Notes For Future Runs
- Root-only `AGENTS.md` plus `docs/architecture/` and `docs/references/` should be treated as the portfolio default unless the workflow itself changes.
- Mid-run snapshot on 2026-04-05: the final five repos in flight had already eliminated all `CLAUDE.md` files, and two of them had already collapsed to one root `AGENTS.md` before their workers formally completed. This made the inventory scan a useful early signal that the rollout pattern was working.
