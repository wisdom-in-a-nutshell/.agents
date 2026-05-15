---
name: whiyh-gpt-hill-climb
description: "Monitor, analyze, and improve the Who's In Your Head GPT/default game path. Use when Codex is asked to check recent games, misses, dropoffs, abandoned sessions, model latency, cache/token efficiency, model errors, share signals, or GPT model performance for this repo; when running a recurring telemetry automation/report; or when hill-climbing prompts, routing, mechanics, clients, telemetry, Mongo indexes, or tests to improve speed, completion rate, correct rate, and reported-miss rate."
---

# WIYH GPT Hill Climb

Use this skill for the repeatable improvement loop around the live game at
`/Users/dobby/GitHub/whos-in-your-head`.

The product target is concrete: make model turns fast, cheap, and correct.
Optimize only the GPT product paths: `gpt-chat-latest` as the default and the
fast GPT option (`gpt-5.4-mini`) when selected. Supporting signals are
completion rate up, drop rate down, route/model errors low, cache/token
efficiency healthy, and reported misses down.

## Modes

Choose the narrowest mode that matches the request.

- **Report-only mode**: Use for recurring automation, "check recent games",
  "how are misses/dropoffs/latency/cache doing", or "what happened recently".
  Read telemetry, summarize, and recommend at most one next investigation or
  change. Do not edit code when the user or automation prompt explicitly asks
  for report-only behavior.
- **Improvement mode**: Use only when the user asks to change behavior or when
  an active goal, heartbeat, or automation prompt explicitly authorizes
  hill-climbing. This includes user language such as "continue", "improve",
  "do the best you can", "fix what is worth fixing", or similar standing
  permission. Work on a short-lived branch, make one focused change, validate,
  then return to `main` only when the branch is ready for the normal hook/deploy
  path.

In improvement mode, prefer doing the best focused fix over merely reporting
when telemetry shows a concrete repeated failure, route/model error, duplicate
turn, or clear latency/cost waste. Fix damage caps first when needed, then fix
the root cause if it is visible and low-risk.

When this skill runs from automation, a heartbeat, or an active goal, treat the
human's standing instruction as permission to act. Do not wait for human
feedback just because multiple reasonable fixes exist. Choose the smallest
conservative change that improves the product, work on a short-lived branch,
validate it, return it to `main` for the normal hook/deploy path, and report
what changed. Ask only if the next step is destructive, exposes private data,
requires a missing secret/account decision, or conflicts with repo guidance.

## Cadence Guard

- Do not poll telemetry more often than every 30 minutes unless the user
  explicitly asks for an immediate check.
- For a recurring automation, prefer every 2 hours unless the user asks for a
  tighter loop. A 2-hour report reduces noise and gives enough completed games
  to avoid overfitting.
- Hourly reports are reasonable during high traffic when the last hour has
  roughly 30+ completed games. Still compare against a 2-hour window before
  editing when the pattern is noisy.
- After a deploy, wait a full telemetry window before judging the change unless
  checking deployment health or obvious route failures.

## GPT Path

Treat the GPT workflow as:

- `gpt-chat-latest` turn telemetry.
- The fast GPT path (`gpt-5.4-mini`) when selected.

Do not judge the GPT path only by completed rows whose final model is
`gpt-chat-latest`; players can explicitly choose the fast GPT option. Gemini,
Claude, and unsupported GPT paths are intentionally removed from the product;
do not optimize, compare, or route live games through them.

## Cost And Speed Bias

Focus optimization only on the GPT default path unless the user redirects:

- Keep `gpt-chat-latest` cheap and fast for ordinary turns.
- Do not reintroduce Gemini, Claude, or unsupported GPT paths while
  hill-climbing.
- Watch average model latency, route latency, total tokens, reasoning tokens,
  cached tokens, and cache read rate.
- Prefer prompt/mechanics/routing changes that reduce wasted questions, repeated
  retries, unnecessary escalation, or low-value expensive turns.
- Use instant/local deterministic handling only for app-owned mechanics such as
  the fixed opener, validation, state transitions, retry guards, warmups, and
  avoiding unnecessary model calls. Do not replace the model's gameplay
  judgment with hardcoded question trees or local guesses.
- Do not trade a meaningful correctness drop for small cost savings.

## Telemetry Pass

Start with aggregates before reading transcripts.

```bash
npm run telemetry -- summary --plain --minutes 30 --limit 10
npm run telemetry -- summary --plain --minutes 60 --limit 10
npm run telemetry -- dropoffs --plain --minutes 60 --limit 12
npm run telemetry -- token-stats --plain --model gpt --minutes 60 --limit 12
```

Read transcripts only when aggregates justify it:

- GPT correct rate regressed.
- GPT reported misses increased.
- GPT latency or slow turns increased.
- Route/model errors appeared.
- A repeated failure pattern is visible.

Transcript commands:

```bash
npm run telemetry -- misses --json --minutes 60 --model gpt --limit 8 --include-transcript
npm run telemetry -- model-results --json --model gpt --minutes 60 --limit 12 --include-transcript
```

For a quick live comparison or broader window, adjust only `--minutes`,
`--model`, and `--limit`. Keep transcript limits small.

## Failure Buckets

Classify each interesting failure before proposing a change:

- Premature narrow guess.
- Weak geography, language, field, genre, era, role, or format split.
- Nearby-person confusion after good narrowing.
- Player likely misremembered a fact or answered a category noisily.
- Too many `maybe` answers made confidence unstable.
- Persona/fictional-character boundary confusion.
- Stale routing, invalid fallback, content-filter recovery, or model error.
- UX/client issue such as accidental starts, deploy interruption, or slow waits.

Do not edit prompts from one isolated transcript unless it shows a clear rule
violation that is likely to recur.

## Slow Turn Checks

When dropoffs cluster around later questions or completion is interrupted,
inspect route/model timing. The most important distinction is whether the player
left because the model was slow, the app errored, or the narrowing path became
bad.

If a slow outlier looks like a stale duplicate turn, check whether the same
game state and answer created more than one model call. The intended route
behavior is server-side idempotency for `answer`: same state plus same answer
within a short runtime window should replay one generated result, not start a
second OpenAI request or write duplicate turn telemetry. Failed turns should not
be cached, so real retries still work.

Known prior issue: GPT content-filter incomplete near Q20 once triggered a slow
non-GPT fallback before GPT retry, producing a very long wait. Non-GPT fallback
paths have since been removed; the intended behavior is to retry the supported
GPT path before any supported GPT fallback.

## Improvement Workflow

Before editing:

1. Check the current branch and working tree.
2. If on `main`, create a short-lived `codex/<specific-task>` branch.
3. Preserve user changes. Do not revert unrelated work.

Allowed change surfaces include:

- Game-master prompts and runtime directives.
- State transitions, final-guess logic, and model routing.
- Fallback behavior and reasoning schedule.
- Telemetry events, private telemetry clients, Mongo/Cosmos documents, and
  indexes.
- Public aggregate stats, as long as they stay transcript-free.
- Tests and durable repo docs.

Safety constraints:

- Never expose API keys, Mongo URIs, raw model responses, hidden prompts, actual
  answers, or transcripts to public browser surfaces.
- Keep transcript access private/operator-only.
- Keep `/stats` aggregate-only.
- Prefer additive telemetry schema changes over breaking existing readers.

Validation before returning to `main`:

```bash
npm run lint
npm run typecheck
npm test
scripts/check-fast.sh
```

Use targeted tests while iterating. For gameplay behavior changes, run a local
API smoke with telemetry disabled:

```bash
GAME_TELEMETRY_ENABLED=false npm run dev -- --hostname 127.0.0.1 --port 3022
npm run play:api -- reset --base-url http://127.0.0.1:3022 --state-file tmp/<name>.json
npm run play:api -- start --model gpt-chat-latest --base-url http://127.0.0.1:3022 --state-file tmp/<name>.json
```

Answer a few turns and verify the model asks valid questions, continues the
game, and routes as expected. Remove temporary state files afterward.

After a validated change lands on `main`, check deploy status with GitHub
Actions, then wait a full telemetry window before judging product impact.
Delete merged local and remote short-lived branches so stale branches do not
accumulate.

## Report Format

Keep reports compact and operator-friendly:

1. **Window**: exact time window and sample size.
2. **Outcome**: completed, correct, incorrect, reported misses, active, abandoned.
3. **Speed/cache**: GPT route/model latency, slow outliers, token/cache read
   rate when available.
4. **Dropoffs**: where players left and whether it looks like latency, UX, or
   game quality.
5. **Misses**: short paraphrased buckets, not raw transcript dumps unless asked.
6. **Read**: whether this is healthy, noisy, or needs action.
7. **Next action**: at most one recommended investigation or change.
8. **Next check**: when to wait until, respecting the cadence guard.

## Known Learnings

- Accidental header/wordmark starts can create shallow Q1 dropoffs; keep start
  actions explicit.
- Long-tail creator paths need early splits by language, region, audience,
  format, publisher/industry, and role.
- Country/roots music paths need mainstream radio vs bluegrass/folk/Americana
  vs instrumental/songwriter-first splits.
- Business-executive paths need company, region, founder/current/former role,
  and public-company/private-company splits.
- Persona/fictional-character boundary questions are useful only with strong
  character-prone clues, not generic actor/TV clues.
- After the deterministic Alive = No opener, split real deceased humans from
  fictional, legendary, video-game, holiday, religious, folklore, and
  screen-persona figures before normal dead-person career checklists. Misses
  like Mario -> Momotaro and Master Chief -> historical warrior indicate this
  boundary failed.
- Some misses come from noisy user answers; do not prompt-tune around a single
  case where the user answered a key geography/category incorrectly.
- A 242s stale duplicate GPT turn showed that capping OpenAI SDK requests is
  not enough by itself. Keep the answer-turn replay/idempotency guard intact and
  watch duplicate same-state turns after deploys.

## Automation Prompt

For a recurring report-only check, use a prompt like:

```text
Use $whiyh-gpt-hill-climb in report-only mode. In /Users/dobby/GitHub/whos-in-your-head, review the last 60 minutes of GPT/default game telemetry and compare with the last 2 hours when the sample is noisy, including misses, dropoffs, latency, cache/token efficiency, model errors, and share signals when available. Focus optimization on `gpt-chat-latest` and the fast GPT option `gpt-5.4-mini`: make turns cheaper and faster where possible without hurting correctness. Summarize what changed, identify the most likely reason for any failures, and recommend at most one next action. Do not edit code.
```

For the same-thread hill-climb loop, use improvement mode:

```text
Use $whiyh-gpt-hill-climb in improvement mode. In /Users/dobby/GitHub/whos-in-your-head, review recent GPT/default game telemetry, then improve the product when there is a concrete repeated failure, route/model error, duplicate stale turn, or clear cost/latency waste worth fixing. Optimize accuracy first, then speed and cost without hurting correctness. Work on a short-lived `codex/*` branch, make one focused prompt/mechanics/routing/client/telemetry/docs change, validate with targeted tests plus `scripts/check-fast.sh`, return the validated patch to `main` for the normal hook/deploy path, and delete the short-lived branch. If the data is healthy or too noisy, report only.
```
