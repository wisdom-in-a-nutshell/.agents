# Reddit Plan Schema

Use `submit-plan` for repeatable posts or when paths/body text should stay in project-local files.

## Minimal gallery example

```json
{
  "kind": "gallery",
  "subreddit": "AIAgents",
  "title": "Agent Engineering 101: A Visual Guide (AGENTS.md, Skills, and MCP)",
  "flair_id": "abc123",
  "images": [
    {"image_path": "public/blog/agent-engineering-101/02-toolkit.png"},
    {"image_path": "public/blog/agent-engineering-101/01-problem.png"},
    {"image_path": "public/blog/agent-engineering-101/03-agents-md.png"},
    {"image_path": "public/blog/agent-engineering-101/04-skills.png"},
    {"image_path": "public/blog/agent-engineering-101/05-mcp.png"}
  ],
  "comment_file": "docs/projects/agent-engineering-reddit-distribution/resources/reddit-full-body.md"
}
```

Use explicit gallery image objects in JSON plan files, even when you do not need
captions:

```json
{
  "image_path": "relative/or/absolute/path.png"
}
```

## Minimal self-post example

```json
{
  "kind": "self",
  "subreddit": "ChatGPTCoding",
  "title": "Agent Engineering 101: A Visual Guide (AGENTS.md, Skills, and MCP)",
  "selftext_file": "docs/projects/agent-engineering-reddit-distribution/resources/reddit-full-body.md"
}
```

## Fields

- `kind`: `link`, `self`, `image`, or `gallery`
- `subreddit`: subreddit name without `r/`
- `title`: submission title
- `url`: required for `link`
- `selftext`: inline body text for `self`
- `selftext_file`: file-backed body text for `self`
- `image_path`: required for `image`
- `images`: list of gallery image objects for `gallery`
- `flair_id`: optional flair template id
- `flair_text`: optional flair text when the subreddit allows it
- `nsfw`: optional boolean
- `spoiler`: optional boolean
- `send_replies`: optional boolean, defaults to `true`
- `resubmit`: optional boolean for link posts, defaults to `true`
- `comment_text`: inline first comment body
- `comment_file`: file-backed first comment body

## Path behavior

- Relative paths are resolved relative to the plan file.
- Absolute paths are used as-is.
- In JSON plan files, prefer explicit gallery image objects with `image_path`.
- Optional gallery fields on each image object are `caption` and `outbound_url`.
- If a workflow ever seems to accept plain-string gallery entries, treat that as
  a convenience path rather than the canonical shape; object form is the safe
  default.
