# Unrolling The Codex Agent Loop

Source:

- `https://openai.com/index/unrolling-the-codex-agent-loop/`

Use this reference when working on the mental model behind Codex-backed assistants, especially when deciding how much behavior should live in a base prompt versus later local guidance.

## Why This Matters

The article explains the actual loop that Codex runs:

- user input is turned into prompt items
- the model is sampled
- the model either answers or requests a tool call
- tool results are appended back into the conversation state
- the loop repeats until the turn ends with an assistant message

This matters because assistant identity and local guidance sit on top of the loop rather than replacing it.

## Core Terms

### Thread

- the durable conversation container
- contains multiple turns

### Turn

- one unit of user-requested work
- may contain many inference and tool-call iterations before completion

### Prompt Items

- the structured prompt is built from items with roles and types
- later requests append more items rather than replacing the whole idea of the conversation

## Prompt Construction Takeaways

The article describes three important payload areas:

- `instructions`
- `tools`
- `input`

In Codex:

- `model_instructions_file` supplies the base `instructions` layer when set
- otherwise built-in model instructions are used
- `AGENTS.md` and related local guidance are aggregated later into user-side instruction content

This is the key reason `model_instructions_file` and workspace `AGENTS.md` should not be treated as interchangeable.

## Loop Mechanics

The first request starts with a prompt assembled from:

- server/base system instructions
- client-supplied tools
- client-supplied instructions
- input items such as permissions guidance, developer instructions, project guidance, environment context, and the user message

The model then emits either:

- a final assistant message
- or a tool request

When the model emits a tool request:

- the client executes the tool
- the tool output is appended as new prompt items
- the next model call sees the previous prompt as an exact prefix plus the new appended items

## Important Design Implications

### 1. A turn is not one inference call

A single user request can trigger many model/tool iterations.

### 2. Prompt growth is normal

Conversation state grows across turns and within turns as tool outputs and assistant/user messages accumulate.

### 3. Exact-prefix stability matters

The article explicitly calls out prompt caching. Stable early prompt content helps repeated calls stay efficient.

### 4. Configuration churn is expensive

Changing tools, instructions, or other early prompt content mid-conversation can reduce caching efficiency and make behavior less predictable.

### 5. Base identity and local routing are different jobs

Because `instructions` and workspace/project guidance enter at different layers, the clean split is:

- base assistant identity -> `model_instructions_file`
- local loading/routing -> workspace `AGENTS.md`
- stable human facts -> `USER.md`
- changing context -> memory files

## Performance Notes From The Article

- Codex avoids `previous_response_id` for statelessness and Zero Data Retention compatibility.
- Prompt caching depends on exact prefix matches.
- Tool ordering and prompt stability matter.
- Long histories eventually require compaction.
- Compaction preserves a smaller but still useful representation of prior context.

## What To Carry Into Product Design

- Do not model the assistant as a single one-shot response generator.
- Design boot behavior assuming a durable thread with multiple turns.
- Keep the assistant identity layer stable.
- Keep changing user/workspace context outside the base prompt.
- Avoid overlapping always-load files that all try to redefine the same assistant persona.
