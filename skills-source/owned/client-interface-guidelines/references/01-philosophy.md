## Philosophy

These are the fundamental principles of good CLI design for this environment.

### Machine-primary design

Assume the CLI is primarily an execution surface for agents.

That means:
- the default contract should be machine-readable
- behavior should be explicit, stable, and deterministic
- operator inspection is useful, but secondary

Do not start from the assumption that the CLI is a conversational UI for humans.
Start from the assumption that it is a programmable control surface.

### Simple parts that work together

A core tenet of UNIX is that small, simple programs with clean interfaces can be combined to build larger systems.
That still matters.

For agent-native work, structured JSON should usually be the primary result surface.
Plain text remains useful for shell inspection and debugging, but it should not displace the stable machine contract.

Whatever software you build will become part of a larger automated system.
Your only real choice is whether it becomes a well-behaved part.

This skill therefore prefers:
- composability over friendliness theater
- explicit contracts over adaptive output magic
- inspection affordances over human-mode polish

### Consistency across programs

Where possible, a CLI should follow patterns that already exist.
That helps humans and agents alike.

But inherited convention is not sacred.
If a convention makes machine use less deterministic or adds ambiguous mode-switching, break it.
For example, TTY-sensitive output semantics are often more harmful than helpful in a strongly agent-native environment.

### Saying (just) enough

A command is saying too little when an agent cannot tell whether it succeeded, failed, or partially completed.
A command is saying too much when it mixes logs, prose, and results into one unstable stream.
The end result is ambiguity.

The right balance here is:
- one stable result object on stdout
- optional diagnostics on stderr
- explicit inspection commands for current state

### Robustness

Software should be robust, and it should also feel inspectable and predictable to the operator maintaining the agent system.

That means:
- stable exit codes
- retry-safe behavior where possible
- no surprise prompts
- no secret leaks
- explicit state summaries for mutating commands
- dedicated status/list/get/inspect surfaces when state visibility matters

As a general rule, robustness comes from keeping the main contract simple.
Lots of dual-mode output behavior and adaptive UX tends to make a client fragile.

### Operator inspection, not human mode

There is still a place for human-readable affordances, but the right framing is operator inspection.

Useful examples:
- `status`
- `get`
- `list`
- `inspect`
- `validate`
- `dry-run`
- `--plain` for shell inspection
- `--debug` for diagnostics on stderr

These are not a separate human-first UI.
They are inspection and debugging paths layered on top of a machine-primary contract.

### Chaos

The terminal world is full of inconsistent inherited conventions.
Some are useful. Some are baggage.

The time might come when you need to break old CLI conventions.
Do so when the older convention makes automation less deterministic or inspection less trustworthy.

> “Abandon a standard when it is demonstrably harmful to productivity or user satisfaction.” — Jef Raskin, The Humane Interface
