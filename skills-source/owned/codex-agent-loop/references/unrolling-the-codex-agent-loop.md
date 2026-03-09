# How The Codex Agent Loop Works

Sources:

- `https://openai.com/index/unrolling-the-codex-agent-loop/`
- `references/openai-codex-prompt-loading.md`

## Contents

- What to remember
- Core objects: thread, turn, items
- The simplest loop
- What happens inside a turn
- How turns accumulate into a thread
- What the harness is responsible for
- Why builders care about prompt stability

## What To Remember

- Codex is a harness around model inference plus tool execution, not a single one-shot text completion.
- A `thread` contains multiple `turn`s, and one turn may contain many model and tool iterations before it finishes.
- The model is not handed one raw prompt string from the user. Codex sends structured `instructions`, `tools`, and `input`, and the Responses API derives the model-facing prompt from those pieces.
- Tool calls are part of the normal loop. Their outputs are appended into later prompt items so the model can continue from new observations.
- The loop ends only when the model emits an assistant message for that turn. The environment changes made by tools are often just as important as the final text.

## Core Objects

### `thread`

- The durable conversation container.
- Holds the running history across multiple user turns.
- Accumulates earlier assistant messages, tool calls, tool outputs, and other items that future turns may need.

### `turn`

- One user-initiated unit of work inside a thread.
- Starts when Codex adds the user's new message to the request.
- May include many internal cycles of model inference, tool execution, and appended observations.
- Ends when the model emits an assistant message instead of another tool call.

### `items`

- The real building blocks of Codex conversation state.
- Include messages, reasoning summaries, function calls, function-call outputs, environment context, skill/project guidance, and compaction artifacts.
- Grow over time as the harness keeps appending new state instead of rebuilding the whole conversation from scratch.

## The Simplest Loop

![Diagram titled “Agent loop” illustrating how an AI system processes a user request, calls tools, observes results, updates its plan, and returns outputs. Arrows connect steps such as user input, model reasoning, tool actions, and final response.](../assets/openai-unrolling-the-codex-agent-loop/agent-loop.svg)

At the highest level, the loop is:

1. Take user input.
2. Build a request for the model.
3. Run inference.
4. If the model asks for a tool, execute it and append the result.
5. Run inference again with the expanded state.
6. Stop only when the model emits an assistant message for the user.

Two details from the blog matter here:

- The assistant's output is not only the final text. In software work, the real output may be the files changed on disk, commands run, or external side effects that happened through tools.
- The loop is owned by the harness. The model proposes actions, but the client or harness executes tools, appends results, and decides when to call the model again.

## What Happens Inside A Turn

Inside one turn, Codex does more than "send the user's text to the model."

First, it prepares a structured Responses API request:

- `instructions`: the base instruction layer, either from `model_instructions_file` or the model's bundled base instructions
- `tools`: the tool definitions available during this request
- `input`: a list of prompt items, including sandbox and environment messages, local guidance, and finally the user's message

The model then produces streamed output. That output may include:

- visible assistant text for the UI
- reasoning summaries
- function calls that ask the harness to execute a tool
- completion events that signal the current inference is done

If the model emits a tool call, Codex:

1. executes the tool
2. captures the tool output
3. appends new items representing the model's call and the tool's result
4. sends another Responses API request with the old prompt as an exact prefix plus the newly appended items

That exact-prefix property is central to both correctness and performance. It means the next inference continues from the prior state rather than inventing a new prompt shape mid-turn.

## How Turns Accumulate Into A Thread

![Diagram titled “Multi-turn agent loop” showing how an AI agent iteratively takes user input, generates actions, consults tools, updates state, and returns results. Includes labeled steps, arrows, and example tool outputs illustrating the agent’s reasoning cycle.](../assets/openai-unrolling-the-codex-agent-loop/multi-turn-agent-loop.svg)

When a turn ends, Codex presents the assistant message to the user and waits. If the user replies, Codex starts a new turn in the same thread by appending:

- the assistant message from the prior turn
- the user's new message

This is why the prompt keeps growing over time:

- every turn inherits prior turns
- every tool call inside a turn adds more items
- every new observation becomes part of the future context unless the harness compacts it

The important implication is that "conversation state" is not just chat text. It is the entire sequence of items that the Responses API needs to reconstruct the conversation, including tool-related items and sometimes opaque encrypted artifacts.

## What The Harness Is Responsible For

The blog makes the harness responsibilities explicit. Codex has to:

- choose and expose the tools available for the request
- construct the `instructions`, `tools`, and `input` payload
- stream and interpret Responses API events
- execute tool calls safely
- convert tool execution results back into `input` items
- preserve prompt stability when possible
- manage context-window pressure through compaction

This is why "the agent" is not just the model. The harness is the operational layer that keeps the loop coherent.

## Where Prompt Layers Enter

The exact mechanics live in the lower-level references, but the high-level split is:

- `model_instructions_file` or bundled model prompt -> base `instructions`
- tool inventory -> `tools`
- project guidance, skills, environment context, user messages, appended tool outputs, and prior turn state -> `input`

That split is why changing the base prompt is not the same thing as editing `AGENTS.md`. They land in different parts of the request and have different weight and stability characteristics.

## Why Builders Care About Prompt Stability

The article keeps returning to one practical point: exact early prompt stability matters.

Reasons:

- prompt caching only helps on exact-prefix matches
- changing early prompt content can make behavior less predictable
- changing tool order or configuration can create expensive cache misses
- conversation growth is unavoidable, so you want the stable prefix to stay as reusable as possible

This leads to a durable engineering rule:

- keep the early prompt shape steady
- append new information later when possible
- avoid gratuitous churn in tools, model choice, sandbox settings, or other early request fields

## What Another Agent Should Carry Forward

If you only remember a handful of things from this skill, remember these:

- A turn is not one model call.
- Tool calls are first-class parts of the loop.
- The state is a growing list of items, not just plain chat messages.
- Codex owns the harness responsibilities around the model.
- Base instructions, local guidance, and mutable context are different layers.
- Prompt stability and compaction are core runtime concerns, not optional refinements.
