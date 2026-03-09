# Building The Initial Prompt

Source:

- `https://openai.com/index/unrolling-the-codex-agent-loop/`

## Contents

- Which inference endpoint Codex targets
- The three request surfaces: `instructions`, `tools`, `input`
- How Codex populates the initial `input`
- How the server derives the prompt
- What the first streamed turn looks like
- How tool results become the next request

## Which Endpoint Codex Calls

The Codex harness talks to a Responses API endpoint. The exact endpoint depends on configuration:

- ChatGPT login uses a ChatGPT-hosted Codex responses endpoint.
- API-key authentication with OpenAI-hosted models uses `https://api.openai.com/v1/responses`.
- Local `gpt-oss` setups can point at a local OpenResponses-compatible endpoint such as Ollama or LM Studio.
- Other providers can host compatible Responses API surfaces as well.

The main point is that Codex is built around the Responses API shape rather than one hard-coded OpenAI-only transport.

## The Three Request Surfaces

The blog frames the request around three fields:

- `instructions`
- `tools`
- `input`

These are distinct:

- `instructions` is the base instruction layer inserted at high priority
- `tools` declares what actions the model is allowed to request
- `input` is the ordered list of messages and other items that make up the rest of the conversational state

Codex gets the base `instructions` from:

- `model_instructions_file` in `~/.codex/config.toml`, if configured
- otherwise the model's bundled `base_instructions`

That is why `model_instructions_file` is a powerful lever. It changes the top-level instruction layer, not just a local note later in the prompt.

## What Goes In `tools`

Codex exposes a mix of tool sources:

- Codex-provided tools such as the local `shell` tool
- built-in Codex tools such as `update_plan`
- Responses API tools such as web search
- user-configured tools, often from MCP servers

Each tool is declared using the schema expected by the Responses API. The important practical point is not the exact JSON shape, but that the tool list is part of the request prefix. If the list changes or even gets reordered, later requests may miss prompt-cache reuse.

## How Codex Populates The Initial `input`

Before appending the user's message, Codex inserts several items into `input`.

### 1. Permissions instructions

A `role=developer` message describing:

- filesystem sandboxing
- network access
- approval behavior
- writable locations, if any

This applies to the Codex-provided `shell` tool. Other tools are responsible for their own guardrails.

### 2. Optional `developer_instructions`

If configured, Codex adds another `role=developer` message from `config.toml`.

### 3. Aggregated user instructions

Codex aggregates project and user guidance into a later `role=user` message. This may include:

- global `$CODEX_HOME/AGENTS.override.md` or `$CODEX_HOME/AGENTS.md`
- repository and subdirectory `AGENTS.override.md` / `AGENTS.md`
- configured fallback filenames
- skill preamble and skill metadata
- skill usage guidance

More specific files appear later in the merged instruction chain.

### 4. Environment context

A `role=user` message describing the local environment, especially:

- current working directory
- shell

### 5. The user's message

Only after the earlier items are prepared does Codex append the user's actual request that starts the turn.

Each `input` entry is still a structured item. A typical message item looks like:

```json
{
  "type": "message",
  "role": "user",
  "content": [
    {
      "type": "input_text",
      "text": "Add an architecture diagram to the README.md"
    }
  ]
}
```

## How The Server Derives The Prompt

The client sends JSON, not a finalized prompt transcript. The Responses API server decides how to arrange that JSON into the prompt the model consumes.

The key implication from the blog:

- the server chooses the ordering of the earliest prompt items
- the client controls much of the content of those items
- the resulting prompt begins with the high-priority instruction and tool layers before the `input` chain

The first snapshot in the article is useful here because it shows the model sitting after that prompt assembly step.

![Snapshot diagram showing a single step in an AI agent loop. A user request enters the model, which produces a thought, an action with a tool name, and a tool input. The diagram highlights this intermediate reasoning step before the tool is called.](../assets/openai-unrolling-the-codex-agent-loop/snapshot-1.svg)

## What The First Streamed Turn Looks Like

When Codex sends the initial request, the Responses API answers with a Server-Sent Events stream.

The stream may contain events such as:

- reasoning summary deltas
- output item additions
- output text deltas for UI streaming
- completion events

Codex consumes those SSE events and republishes them into internal event objects for its own clients. Some events are purely for display, while others become durable items that must be appended into the next request.

## How Tool Results Become The Next Request

Suppose the model emits:

- a reasoning item
- a `function_call`

Codex then:

1. executes the requested tool
2. captures the result as a `function_call_output`
3. appends the reasoning item, the function call, and the function-call output into the next request

That yields the second snapshot:

![Diagram labeled “Snapshot 2” showing an AI agent after a tool call. The model receives a tool observation and produces a new thought and action. Arrows connect inputs, observations, and outputs to illustrate how the agent iterates its reasoning loop.](../assets/openai-unrolling-the-codex-agent-loop/snapshot-2.svg)

The important runtime invariant is:

- the next prompt uses the old prompt as an exact prefix
- only the newly appended tool-related items are added at the end

This is how Codex keeps the model grounded in the prior state while letting the loop continue.

## How A Turn Actually Ends

The turn does not end when the first inference call completes. It ends only when the model emits an assistant message instead of another tool call.

After that:

- Codex presents the assistant message to the user
- if the user replies, Codex appends the assistant message and the user's new message to start the next turn

The third snapshot shows that handoff into the continuing conversation:

![Diagram labeled “Snapshot 3” showing the final stage of an AI agent loop. After receiving tool results, the model generates a concluding thought and a final answer returned to the user. Arrows illustrate the transition from tool output to completed response.](../assets/openai-unrolling-the-codex-agent-loop/snapshot-3.svg)

## What To Retain

- The user does not directly author the final prompt transcript.
- `instructions`, `tools`, and `input` are distinct request surfaces.
- Codex prepends several items before the user's message ever appears.
- The model's tool requests are converted into structured items and appended into future requests.
- One turn can contain many Responses API calls before it ends.
