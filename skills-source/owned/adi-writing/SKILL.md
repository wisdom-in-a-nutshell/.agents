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
7. When a repo already exposes `LLM_API_ENDPOINT` and `LLM_API_KEY`, you can use `scripts/draft_with_llm.py` for a fast first draft in Adi's voice.

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
