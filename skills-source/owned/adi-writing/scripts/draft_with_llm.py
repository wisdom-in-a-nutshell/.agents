#!/usr/bin/env python3
"""Draft external-facing text in Adi's voice via an OpenAI-compatible endpoint."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Iterable

from openai import OpenAI

SKILL_ROOT = Path(__file__).resolve().parent.parent
REFERENCES = SKILL_ROOT / "references"
DEFAULT_MODEL = os.environ.get("ADI_WRITING_MODEL", "claude-4.6-sonnet")
MODE_TO_REF = {
    "blog-post": REFERENCES / "blog-post.md",
    "email": REFERENCES / "email.md",
    "tweet": REFERENCES / "tweet.md",
    "short-post": REFERENCES / "short-post.md",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Draft writing in Adi's voice via an OpenAI-compatible endpoint."
    )
    parser.add_argument(
        "brief",
        nargs="?",
        help="Short brief text. If omitted, reads stdin unless --input-file is used.",
    )
    parser.add_argument("--mode", choices=sorted(MODE_TO_REF), default="blog-post")
    parser.add_argument("--input-file", type=Path, help="Read the main brief from a file.")
    parser.add_argument(
        "--context-file",
        action="append",
        type=Path,
        default=[],
        help="Extra context file(s) to include.",
    )
    parser.add_argument(
        "--instruction",
        action="append",
        default=[],
        help="Extra instruction(s) to append.",
    )
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--temperature", type=float, default=0.45)
    parser.add_argument("--max-tokens", type=int, default=1800)
    parser.add_argument("--output-file", type=Path)
    parser.add_argument("--json", action="store_true", help="Emit JSON with text + metadata.")
    return parser.parse_args()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


def resolve_brief(args: argparse.Namespace) -> str:
    if args.input_file and args.brief:
        raise SystemExit("Use either positional brief or --input-file, not both.")
    if args.input_file:
        return read_text(args.input_file)
    if args.brief:
        return args.brief.strip()
    if not sys.stdin.isatty():
        return sys.stdin.read().strip()
    raise SystemExit("Provide a brief as an argument, via --input-file, or on stdin.")


def join_context(paths: Iterable[Path]) -> str:
    chunks: list[str] = []
    for path in paths:
        chunks.append(f"## Context: {path}\n{read_text(path)}")
    return "\n\n".join(chunks)


def build_prompts(
    mode: str,
    brief: str,
    extra_instructions: list[str],
    context_paths: list[Path],
) -> tuple[str, str]:
    voice = read_text(REFERENCES / "voice.md")
    mode_ref = read_text(MODE_TO_REF[mode])
    system_prompt = (
        "You are drafting external-facing writing in Adi's voice. "
        "Follow the voice and mode guidance exactly. Return only the draft. "
        "Do not add explanations, framing notes, or commentary.\n\n"
        f"# Voice guidance\n{voice}\n\n"
        f"# Mode guidance\n{mode_ref}"
    )
    sections = [
        f"Write a {mode} in Adi's voice.",
        "Preserve directness, specificity, and human texture.",
        "Do not sound corporate, consultant-like, or generic.",
        "Do not use em dashes.",
        f"## Brief\n{brief}",
    ]
    if extra_instructions:
        sections.append(
            "## Extra instructions\n" + "\n".join(f"- {item}" for item in extra_instructions)
        )
    context_block = join_context(context_paths)
    if context_block:
        sections.append(context_block)
    user_prompt = "\n\n".join(sections)
    return system_prompt, user_prompt


def extract_text(response) -> str:
    content = response.choices[0].message.content
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            text = getattr(item, "text", None)
            if text:
                parts.append(text)
        return "\n".join(parts).strip()
    return ""


def main() -> int:
    args = parse_args()
    endpoint = os.environ.get("LLM_API_ENDPOINT")
    api_key = os.environ.get("LLM_API_KEY")
    if not endpoint or not api_key:
        raise SystemExit("LLM_API_ENDPOINT and LLM_API_KEY must be set.")

    brief = resolve_brief(args)
    system_prompt, user_prompt = build_prompts(
        mode=args.mode,
        brief=brief,
        extra_instructions=args.instruction,
        context_paths=args.context_file,
    )

    client = OpenAI(api_key=api_key, base_url=endpoint)
    response = client.chat.completions.create(
        model=args.model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=args.temperature,
        max_tokens=args.max_tokens,
    )
    text = extract_text(response)
    if not text:
        raise SystemExit("Model returned empty content.")

    if args.output_file:
        args.output_file.write_text(text + "\n", encoding="utf-8")

    if args.json:
        payload = {
            "mode": args.mode,
            "model": args.model,
            "output_file": str(args.output_file) if args.output_file else None,
            "text": text,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
