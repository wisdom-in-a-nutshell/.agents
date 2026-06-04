# Ryan Lopopolo / OpenAI Harness Principles

Distilled principles from the local Ryan Lopopolo / OpenAI source bundle. Use this file for everyday synthesis; load `references/raw/ryan-lopopolo-openai/source-manifest.md` only when exact source lookup is needed.

## Core Thesis

Agent-native engineering treats the repository, tools, checks, and docs as the harness around agents. The human role moves toward setting intent, choosing priorities, reviewing outcomes, and improving the harness so agents can execute more of the full job.

## Principles To Adapt

### Humans Steer, Agents Execute
- Humans should spend attention on goals, acceptance criteria, taste, risk, and prioritization.
- Agents should handle implementation, tests, docs, validation, cleanup, and routine follow-through.
- If the human has to repeat the same instruction, treat that as a missing harness affordance.

### The Full Job Matters
- A useful agent does not only write code; it drives the change to a verified result.
- The loop should include running checks, using the product or API, inspecting relevant output, and repairing failures.
- Stopping at "I changed the files" is weaker than proving the behavior changed.

### Repeated Failure Becomes Harness
- Turn recurring mistakes into tests, lints, scripts, clearer docs, skills, better errors, or better CLI affordances.
- Prefer one durable guardrail over repeating prompt text.
- Keep guidance concise; move exact facts and workflows into repo-owned docs.

### Proof Beats Assertion
- Final reports should include the evidence that mattered: commands, screenshots, logs, artifact URLs, smoke results, or CI status.
- If proof was not possible, say why and name the smallest harness improvement that would make it possible next time.
- Product and UI work need product-facing proof, not only static checks.

### Optimize For Agent Legibility
- Repos should have predictable structure, explicit contracts, and fast entry points.
- Tools should be non-interactive, deterministic, and friendly to agents.
- Failing commands should provide the command, location, exit code, focused output, and a likely remediation path.

### Keep Solo-Dev Process Lightweight
- Do not copy enterprise process wholesale.
- Prefer high-permission, direct, recoverable workflows when the repo is trusted and the blast radius is acceptable.
- Add process only when it reduces repeated mistakes, speeds recovery, or improves proof.

## What Not To Import By Default

- Mandatory PR ceremony for solo work.
- Broad security theater disconnected from real repo risks.
- Large review committees or heavyweight approval queues.
- Branch-heavy workflows when direct-to-main plus checks is faster and recoverable.
- More skills or docs than the agent can reliably choose from.

## Source Bundle

The raw source inventory lives at `references/raw/ryan-lopopolo-openai/source-manifest.md`.
