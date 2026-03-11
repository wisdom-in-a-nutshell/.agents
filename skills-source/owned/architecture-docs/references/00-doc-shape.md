# Architecture Doc Shape

Use this as the default shape for a human-friendly architecture doc.

## Recommended structure

1. Title
2. Short overview
3. Mermaid diagram
4. Main parts
5. Main flow
6. Tradeoffs or important constraints
7. Links to deeper references

## Progressive disclosure variant

Use this instead when one diagram would be too dense:

1. Title
2. Short overview
3. Level 1 diagram: simplest whole-system view
4. Level 2 diagram: main ownership zones or major parts
5. Level 3 diagram: one important runtime path or boot path
6. Short explanation after each level
7. Links to deeper references

## Example skeleton

```markdown
# System Name

One short paragraph explaining what this system does and how to think about it.

```mermaid
flowchart TD
    A[Client]
    B[API]
    C[Worker]
    D[(Database)]

    A --> B
    B --> C
    B --> D
    C --> D
```

## Main Parts

- `Client`: what the user or caller interacts with
- `API`: request entry point and orchestration layer
- `Worker`: background execution or async processing
- `Database`: stored state and durable records

## Main Flow

1. The client sends a request to the API.
2. The API validates input and decides whether work is synchronous or background.
3. Workers handle longer-running jobs.
4. Results are written to durable storage and surfaced back to the client.

## Notes

- Keep this doc high-level.
- Put exact contracts, schemas, and env vars in `docs/references/`.
```

## Writing guidance

- Prefer one strong diagram over many weak ones.
- But if one diagram becomes crowded, switch to progressive disclosure instead of overstuffing it.
- Keep the intro short and concrete.
- Use bullets for parts and numbered steps for flow.
- Link to deeper docs instead of overstuffing the page.
- When using grouped blocks, make sure the block labels read as labels, not flow steps.
