---
name: adi-writing
description: Write or edit external-facing content in Adi's voice. Use when drafting or rewriting blog posts, essays, tweets, LinkedIn posts, personal notes meant for publication, emails, website copy, or any other text that should sound like Adi rather than generic AI writing.
---

# Adi Writing

## Quick flow
1. Confirm the piece should sound like Adi, not generic polished AI output.
2. Read `references/voice.md`.
3. Read the mode reference that best matches the task:
   - `references/blog-post.md`
   - `references/email.md`
   - `references/tweet.md`
   - `references/short-post.md`
4. If the current repo has relevant examples of Adi's writing, inspect a small representative sample and adapt to them.
5. Match the format and keep the writing direct, human, and specific.
6. Preserve the real point; do not sand it down into bland professionalism.
7. When the runtime exposes a `writer` sub-agent, prefer using it for first drafts, rewrites, summaries, and tone-sensitive passes instead of local helper scripts.
8. When delegating to the `writer` sub-agent, pass strong context: the current draft, target format, audience, relevant repo examples, factual constraints, what to preserve, what to change, and any personal motivation or tone cues.
9. Keep fact-checking, source verification, and final editorial judgment with the parent agent unless the task is explicitly pure writing.

## Rules
- Lead with the point.
- Prefer simple language over inflated language.
- Keep the texture of real speech when it helps.
- Use examples, lived details, or concrete observations before abstraction.
- Default to current voice, not old blog or newsletter conventions.
- Do not make Adi sound like a marketer, consultant, or corporate content machine.
- Do not add greetings, sign-off flourishes, quote-of-the-day sections, or subscribe blocks unless the format actually needs them.
- Do not use em dashes.

## Iteration rule
- This skill is intentionally incomplete and should improve over time.
- When working with Adi, if a durable writing preference, recurring voice pattern, or repeated correction becomes clear, codify it back into this skill.
- Do not overfit to one draft or one repo. Only write back patterns that seem stable.

## References
- `references/voice.md`: canonical base voice and editing rules
- `references/blog-post.md`: blog-post mode
- `references/email.md`: email mode
- `references/tweet.md`: tweet mode
- `references/short-post.md`: short-post / LinkedIn / public-note mode

## Writer sub-agent usage

When available, the preferred drafting helper for this skill is the `writer` sub-agent rather than a repo-local script.

Practical rule:
- use the parent agent for structure, research, factual verification, and deciding the final shape
- use the `writer` sub-agent for wording, rewriting, tightening, and voice-sensitive drafting passes

When handing work to the `writer` sub-agent, include:
- the exact task
- the target format
- the current draft or raw notes
- relevant repo examples if they matter
- factual constraints and non-negotiables
- what tone to preserve or avoid
