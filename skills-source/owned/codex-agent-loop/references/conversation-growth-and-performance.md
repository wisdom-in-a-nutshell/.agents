# Conversation Growth, Caching, And Compaction

Source:

- `https://openai.com/index/unrolling-the-codex-agent-loop/`

## Contents

- Why prompt growth is unavoidable
- Why Codex keeps requests stateless
- How prompt caching shapes harness design
- What causes cache misses
- Why Codex appends changes instead of rewriting earlier items
- How compaction works

## Prompt Growth Is A Normal Property Of The Loop

Once you accept the Codex loop, prompt growth is unavoidable.

Reasons:

- every new user turn appends more conversation state
- every tool call inside a turn appends more items
- earlier assistant messages and tool outputs are part of the continuing thread

This is why the context window is a real systems concern for any long-lived agent harness.

## Why Codex Keeps Requests Stateless

The blog calls out an important implementation decision: Codex does not currently rely on `previous_response_id` for normal conversation state.

The practical reasons given are:

- keeping each request self-contained
- making provider behavior simpler because the request can be handled statelessly
- staying compatible with Zero Data Retention configurations

Codex still preserves useful prior reasoning state through encrypted fields returned by the server, but it does not require the provider to keep prior conversation state behind a stored response handle.

## Why Prompt Caching Matters

Without caching, repeated model calls over an ever-growing prompt become expensive quickly. Prompt caching changes that cost profile by allowing reuse when the new request begins with an exact prefix of an earlier one.

The blog's main operational takeaway is:

- exact-prefix matches are what matter
- static and stable content should stay early in the prompt
- variable content should be appended later

This applies not just to text, but also to:

- tools
- images
- model-specific instructions
- any other early request content

## What Causes Cache Misses

The article gives concrete examples of changes that can break cache reuse:

- changing the available tools mid-conversation
- changing the target model, which effectively changes the model-specific base instructions
- changing sandbox configuration
- changing approval mode
- changing the current working directory

The Codex team also called out a real bug where MCP tools were not enumerated in a consistent order, which caused avoidable cache misses. Dynamic tool inventories are especially tricky because an MCP server can change its tool list during a conversation.

The general lesson is simple:

- even semantically minor request-prefix churn can be operationally expensive

## Why Codex Appends Changes Instead Of Rewriting Earlier Items

When some runtime setting changes in the middle of a conversation, Codex tries to preserve the stable prefix by appending a new item rather than editing an earlier one.

Examples from the blog:

- if sandboxing or approval policy changes, Codex adds a new permissions-style developer message
- if the working directory changes, Codex adds a new environment-context user message

This is a concrete harness design pattern worth copying:

- preserve the old prefix
- append the new state as a later observation

That both reflects the chronology honestly and protects prompt caching where possible.

## Compaction Is Part Of The Loop, Not A Separate Convenience Feature

Because the prompt keeps growing, Codex must eventually reduce it. The blog describes two phases of this story:

### Earlier approach

- the user manually invoked `/compact`
- Codex sent the full conversation plus summarization instructions
- the resulting assistant summary became the new basis for later turns

### Current approach

- the Responses API offers `/responses/compact`
- the API returns a smaller list of items suitable for continuing the conversation
- that compacted list can include a special `type=compaction` item with opaque encrypted content that preserves latent understanding of the prior conversation
- Codex automatically compacts once its configured token threshold is exceeded

The important conceptual point is that compaction does not merely delete context. It replaces a large item history with a smaller, model-usable representation of that history.

## What This Means For Product Design

If you are building on top of Codex or designing a similar harness, preserve these rules:

- Do not assume conversation state can grow forever without intervention.
- Expect context-window management to be a first-class runtime responsibility.
- Keep early prompt content stable whenever possible.
- Treat tool ordering and tool inventory as performance-sensitive.
- Prefer appended state updates over rewriting early prompt sections.
- Design with the understanding that compaction will eventually happen.

## What To Retain

- The Codex loop naturally grows prompt state across both turns and tool iterations.
- Codex prefers stateless requests over `previous_response_id`-driven statefulness.
- Prompt caching depends on exact-prefix reuse, so early request stability is valuable.
- Mid-conversation config churn can be surprisingly expensive.
- Compaction is an operational necessity for long-lived agent threads.
