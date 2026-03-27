### Output

**Machine-readable output is paramount.**
For agent-native CLIs, stdout is primarily a result contract, not a user-facing canvas.

The default rule should be:
- stdout carries the stable machine result
- stderr carries diagnostics
- semantic output shape should not change just because a TTY is present

**Have plain-text inspection output only when it adds real leverage.**
Plain text remains useful in UNIX, but in this workflow it should be an explicit inspection mode, not the default behavioral contract.

**If inspection output would break the machine contract, keep it behind `--plain` or dedicated inspection commands.**
For example:
- `status`
- `list`
- `inspect`
- `get`

Do not overload the primary execution path with decorative or TTY-adaptive output.

**Display output as JSON by default, or at minimum whenever `--json` is passed.**
JSON makes structure explicit, stable, and testable.
It is the right default for agent callers.

**Display output on success, but keep the contract small and stable.**
The key question is not “is this friendly?” but “is this deterministic and sufficient?”

It is often enough to return:
- status
- identifiers
- timestamps
- changed resources
- retry/state metadata

**If you change state, report the new state explicitly.**
When a command mutates something, the result should include enough structured information for an agent or operator to understand what changed.

For example, a mutating command should return IDs, URNs, file paths, versions, or state summaries rather than celebratory prose.

**Make it easy to inspect the current state of the system.**
If your program changes complex state that is not visible in the filesystem, provide dedicated commands such as:
- `status`
- `get`
- `list`
- `inspect`
- `validate`

These are more reliable than hiding state behind verbose narration.

**By default, don’t output creator-only debugging noise.**
If a piece of output serves only to help the tool author debug internals, it should not be in the default success path.

**Don’t treat `stderr` like a log file, at least not by default.**
Do not print log level labels or extraneous context unless debug mode is explicitly requested.

### Errors

**Catch errors and rewrite them into stable classified failures.**
Errors should help both the agent and the operator.
That usually means:
- stable `error.code`
- concise `message`
- retryability signal
- actionable `hint`

**Signal-to-noise ratio is crucial.**
The more irrelevant output you produce, the harder it is for agents and operators to recover correctly.

**If there is an unexpected error, keep default output compact and put debug detail behind explicit debug flags.**
Do not dump stack traces or raw transport bodies into the normal success path.
