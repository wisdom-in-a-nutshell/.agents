# Mermaid Guidelines

Architecture docs should use Mermaid to make the system easy to understand at a glance.

## Default

Use:

```mermaid
flowchart TD
```

Top-down is the default because it is usually easiest to scan quickly.

## Good defaults

- Keep node count modest.
- Prefer simple labels.
- Show the main path first.
- Group related nodes only when it improves understanding.
- Use subgraphs sparingly.

## Prefer

- `Client`
- `API`
- `Worker`
- `Queue`
- `Database`
- `Storage`
- `External API`

These kinds of labels are clearer than highly internal names unless the internal names matter.

## Avoid

- giant diagrams with every module shown
- crossing lines everywhere
- deeply nested subgraphs
- labels that require repo context to decode
- mixing too many concerns in one diagram

## Rule of thumb

If a person cannot understand the diagram in a few seconds, it is too detailed.

## When to split diagrams

Split into more than one diagram only when:

- one diagram would be too dense
- there are clearly different flows
- one diagram is for system shape and another is for one key runtime path

Usually one diagram is enough.
