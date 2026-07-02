---
name: codex-reset-credits
description: Check local Codex rate-limit reset credits and expiration times. Use when the user asks when Codex resets, banked resets, reset credits, free resets, weekly resets, or 5-hour resets expire, or asks to inspect available Codex reset credits from the local Codex login.
---

# Codex Reset Credits

Use this skill to report the user's available Codex rate-limit reset credits and
their expiration dates from the local Codex auth session.

## Invocation

When this skill is active, users can ask:

```text
Use $codex-reset-credits to tell me when my Codex resets expire.
```

If this skill is not installed in the current runtime, point Codex at this skill
folder in the repo and ask it to add the folder as a Codex skill.

## Workflow

1. Run `scripts/check_codex_reset_credits.py`.
2. Do not print or expose tokens, account IDs, credit IDs, or user IDs.
3. Report the available count and expiration times.
4. Use friendly calendar dates in human answers, such as
   `12 July 2026, 03:44 CEST`. Include UTC only when useful for exactness.
5. If the endpoint fails, explain the failure compactly and do not paste auth
   file contents.

The endpoint is an undocumented ChatGPT backend endpoint surfaced by community
discussion, so treat the result as a direct account read rather than public API
documentation.

## Script Usage

From the repository root, run:

Default human-readable output:

```bash
python3 skills-source/owned/codex-reset-credits/scripts/check_codex_reset_credits.py
```

JSON output for programmatic follow-up:

```bash
python3 skills-source/owned/codex-reset-credits/scripts/check_codex_reset_credits.py --json
```

Use an explicit timezone when the user's location matters:

```bash
python3 skills-source/owned/codex-reset-credits/scripts/check_codex_reset_credits.py --timezone America/Los_Angeles
```

Example output:

```text
4 reset credits available
Timezone shown: America/New_York

Full reset: expires 11 July 2026, 21:44 EDT / 12 July 2026, 01:44 UTC
```
