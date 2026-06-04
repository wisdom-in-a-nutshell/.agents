# Harness Engineering Article Text Reference

Source: https://openai.com/index/harness-engineering/

Title: Harness engineering: leveraging Codex in an agent-first world

Author: Ryan Lopopolo, Member of the Technical Staff

Published: 2026-02-11

Accessed: 2026-06-04

This is a text-reference version for source intake and later synthesis. It is
not a verbatim copy of the full article. Keep future playbook guidance in our
own words and use this file to navigate the article's argument.

## Short Summary

Ryan Lopopolo describes an OpenAI experiment where a team built and shipped a
real internal product while enforcing a hard constraint: humans did not write
code directly, and Codex wrote product code, tests, documentation, tooling,
CI, observability, and review-related artifacts.

The core shift is that engineers stop treating code production as the scarce
resource. Human attention becomes the constraint. Engineers therefore work on
the harness: repository structure, tools, feedback loops, docs, validation
paths, and guardrails that let agents do the full software engineering job.

The article's strongest practical claim is that repository-local knowledge,
mechanical invariants, and agent-readable proof loops compound. When agents fail,
the fix is not only a better prompt for the current task; it is a durable change
to the repo so future agents receive the missing context automatically.

## Article Shape

### Opening Claim

The article opens with the team building a production-like internal beta with no
manually written code. The team still steers and validates, but Codex writes the
artifacts. This reframes software engineering away from hands-on implementation
and toward designing environments where agents can reliably execute.

Useful playbook implication:

- Score whether a repo enables agents to complete work, not merely whether it
  has tidy docs.

### Empty Repository

The experiment began with an empty repository. Codex generated the initial
scaffold, repo structure, CI, formatting setup, package management, framework
choices, and the first `AGENTS.md`. Within months the repo grew into a large
product with high PR throughput from a small human team.

Useful playbook implication:

- Agent-native structure can be intentional from the first commit, but existing
  repos should be migrated toward agent legibility incrementally.

### Redefining Engineering Work

The article describes human engineering work as systems design, scaffolding, and
leverage. When agents struggled, humans looked for missing capability: missing
tools, abstractions, docs, validation, or enforceable constraints.

Useful playbook implications:

- Treat repeated agent failure as a harness defect.
- Prefer durable repo changes over repeated one-off prompt fixes.
- Make standard tools directly usable by agents.

### Application Legibility

The team made the app, logs, metrics, traces, screenshots, DOM state, and
navigation paths legible to Codex. Agents could boot the app, drive UI flows,
query observability data, reproduce bugs, validate fixes, and loop for hours.

Useful playbook implications:

- Score whether agents can prove user-visible work.
- For UI/product repos, checks alone are not enough; agents need app-driving
  and observable evidence.
- Local logs and metrics should be queryable without human copy/paste.

### Repository Knowledge As System Of Record

The article rejects giant `AGENTS.md` files. `AGENTS.md` should be a short map,
while durable knowledge lives in structured repo docs. The article emphasizes
progressive disclosure: give the agent enough routing context, then let it load
the right deeper documents.

Useful playbook implications:

- Keep root guidance short.
- Use repo docs as the durable knowledge base.
- Prefer indexed references over large instruction blobs.
- Add checks for docs drift when stale docs repeatedly cause failures.

### Agent Legibility

The article argues that knowledge outside the repo effectively does not exist
for the agent at execution time. Team context, product principles, design taste,
architecture expectations, Slack decisions, and operational norms need to be
encoded into versioned files, scripts, schemas, or other agent-readable assets.

Useful playbook implications:

- Audit where important context currently lives outside the repo.
- Move recurring decisions and product/taste rules into durable references.
- Keep the encoded context compact and navigable.

### Enforcing Architecture And Taste

The article distinguishes documentation from enforcement. Agents move fast when
the system mechanically enforces important invariants while leaving local
implementation choices flexible. Examples include dependency boundaries, layer
rules, structured logging, schema naming, file-size limits, reliability rules,
and remediation-rich lint messages.

Useful playbook implications:

- Score whether important repo rules are mechanically enforced.
- Prefer custom fit-for-purpose checks over prose-only reminders when mistakes
  recur.
- Make error messages agent-useful by explaining the fix path.

### Merge Philosophy

The article says high agent throughput changes the tradeoff. Blocking on human
review becomes expensive, while correction becomes cheap. Short-lived PRs,
minimal blocking gates, and follow-up agent runs can be the right choice in a
high-throughput system.

Useful playbook implications:

- For Adi's style, prefer direct-to-main/fast checks/recovery over heavy review
  process.
- Score whether the repo can recover quickly from bad output.

### What Agent-Generated Means

The article treats everything in the repo as agent-writable: product code,
tests, CI, release tooling, docs, eval harnesses, review comments, repo scripts,
and dashboards. Humans prioritize, translate feedback into acceptance criteria,
and validate outcomes.

Useful playbook implications:

- Do not limit the playbook to code files.
- Score whether agents maintain the tools and docs that help future agents.

### Increasing Autonomy

The article's autonomy target is an agent that can validate current state,
reproduce a bug, record evidence, implement a fix, validate by driving the app,
record resolution evidence, open a PR, handle feedback, fix build failures,
escalate only judgment calls, and merge.

Useful playbook implications:

- Add a full-job-loop score.
- Require proof-of-work evidence for product/UI changes.
- Treat repeated human nudges as harness failures.

### Entropy And Garbage Collection

The article describes drift from agents copying existing patterns, including bad
ones. The response is recurring cleanup: encode golden principles, scan for
deviations, update quality grades, and open small targeted cleanup changes.

Useful playbook implications:

- Add a quality/debt feedback loop score.
- Promote repeated slop into recurring checks or cleanup tasks.
- Prefer continuous small cleanup over periodic large cleanup.

### What Is Still Unknown

The article is explicit that fully agent-generated systems are still young. The
long-term shape of architectural coherence and the right places for human
judgment are still being discovered.

Useful playbook implication:

- Keep the playbook pragmatic and revisable. Do not overfit to OpenAI's exact
  team structure or enterprise constraints.

## High-Signal Terms For Searching The Article

- `human time and attention`
- `AGENTS.md`
- `repository knowledge`
- `agent legibility`
- `mechanically`
- `custom linters`
- `pull requests`
- `validate`
- `record a video`
- `garbage collection`
- `golden principles`

