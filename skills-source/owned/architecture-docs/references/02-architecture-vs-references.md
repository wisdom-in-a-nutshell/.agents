# Architecture Vs References

Use this quick test when deciding where a doc belongs.

## `docs/architecture/`

Put a doc here when it explains:

- how the system is supposed to work
- how major parts connect
- how requests, jobs, or data flow
- how responsibilities are divided
- what high-level tradeoffs shape the design

## `docs/references/`

Put a doc here when it explains:

- exact field names
- schemas or DTOs
- env vars
- limits
- commands
- cache rules
- precedence rules
- operational lookup facts

## Simple test

- If the main question is "How does this system work?" use `docs/architecture/`.
- If the main question is "What exact facts do I need?" use `docs/references/`.

## Practical pattern

The best pairing is often:

- one architecture doc in `docs/architecture/`
- one or more supporting fact docs in `docs/references/`

The architecture doc gives the mental model.
The reference doc gives the exact details.
