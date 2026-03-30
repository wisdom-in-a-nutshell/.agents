#!/usr/bin/env python3
"""Machine-first Adi writing helper via a repo-local OpenAI-compatible endpoint."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import time
import uuid
from typing import Iterable, Sequence

from openai import OpenAI

SCHEMA_VERSION = "1.0"
EXIT_OK = 0
EXIT_GENERIC = 1
EXIT_USAGE = 2
EXIT_AUTH = 3
EXIT_DEPENDENCY = 4
EXIT_TIMEOUT = 5

SKILL_ROOT = Path(__file__).resolve().parent.parent
REFERENCES = SKILL_ROOT / "references"
DEFAULT_MODEL = os.environ.get("ADI_WRITING_MODEL", "claude-4.6-sonnet")
DEFAULT_TIMEOUT_SECONDS = float(os.environ.get("ADI_WRITING_TIMEOUT_SECONDS", "90"))
MODE_TO_REF = {
    "blog-post": REFERENCES / "blog-post.md",
    "email": REFERENCES / "email.md",
    "tweet": REFERENCES / "tweet.md",
    "short-post": REFERENCES / "short-post.md",
}


class CliError(Exception):
    def __init__(self, code: str, message: str, hint: str, exit_code: int, retryable: bool = False):
        self.code = code
        self.message = message
        self.hint = hint
        self.exit_code = exit_code
        self.retryable = retryable
        super().__init__(message)


def add_output_mode_flags(parser: argparse.ArgumentParser) -> None:
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--json", action="store_true", help="Emit machine JSON. This is the default behavior.")
    group.add_argument("--plain", action="store_true", help="Emit plain inspection output instead of JSON.")


def add_brief_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("brief", nargs="?", help="Brief text. If omitted, reads stdin unless --input-file or --no-input is used.")
    parser.add_argument("--mode", choices=sorted(MODE_TO_REF), default="blog-post")
    parser.add_argument("--input-file", type=Path, help="Read the brief from a file.")
    parser.add_argument("--context-file", action="append", type=Path, default=[], help="Extra context file(s) to include.")
    parser.add_argument("--instruction", action="append", default=[], help="Extra instruction(s) to append.")
    parser.add_argument("--no-input", action="store_true", help="Fail instead of reading from stdin when no brief is provided.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Draft external-facing writing in Adi's voice via a repo-local OpenAI-compatible endpoint."
    )
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    draft = subparsers.add_parser("draft", help="Generate a draft.")
    add_brief_flags(draft)
    draft.add_argument("--model", default=DEFAULT_MODEL)
    draft.add_argument("--temperature", type=float, default=0.45)
    draft.add_argument("--max-tokens", type=int, default=1800)
    draft.add_argument("--timeout-seconds", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    draft.add_argument("--output-file", type=Path, help="Optional file to write the draft to.")
    add_output_mode_flags(draft)

    render_prompt = subparsers.add_parser("render-prompt", help="Return the exact system and user prompts without calling the model.")
    add_brief_flags(render_prompt)
    render_prompt.add_argument("--model", default=DEFAULT_MODEL)
    add_output_mode_flags(render_prompt)

    validate_env = subparsers.add_parser("validate-env", help="Check whether the required repo-local env vars are available.")
    add_output_mode_flags(validate_env)

    return parser


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except FileNotFoundError as exc:
        raise CliError("E_INPUT_MISSING", f"Input file not found: {path}", "Pass an existing file path.", EXIT_USAGE) from exc


def resolve_brief(args: argparse.Namespace) -> str:
    if args.input_file and args.brief:
        raise CliError(
            "E_INVALID_USAGE",
            "Use either positional brief or --input-file, not both.",
            "Remove one of the two input sources.",
            EXIT_USAGE,
        )
    if args.input_file:
        return read_text(args.input_file)
    if args.brief:
        return args.brief.strip()
    if args.no_input:
        raise CliError(
            "E_INPUT_REQUIRED",
            "No brief was provided.",
            "Pass a brief argument, --input-file, or remove --no-input and pipe text on stdin.",
            EXIT_USAGE,
        )
    if not sys.stdin.isatty():
        brief = sys.stdin.read().strip()
        if brief:
            return brief
    raise CliError(
        "E_INPUT_REQUIRED",
        "No brief was provided.",
        "Pass a brief argument, --input-file, or pipe text on stdin.",
        EXIT_USAGE,
    )


def join_context(paths: Iterable[Path]) -> str:
    chunks: list[str] = []
    for path in paths:
        chunks.append(f"## Context: {path}\n{read_text(path)}")
    return "\n\n".join(chunks)


def build_prompts(mode: str, brief: str, extra_instructions: Sequence[str], context_paths: Sequence[Path]) -> tuple[str, str]:
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
        sections.append("## Extra instructions\n" + "\n".join(f"- {item}" for item in extra_instructions))
    context_block = join_context(context_paths)
    if context_block:
        sections.append(context_block)
    return system_prompt, "\n\n".join(sections)


def extract_text(response) -> str:
    content = response.choices[0].message.content
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text")
            else:
                text = getattr(item, "text", None)
            if text:
                parts.append(text)
        return "\n".join(parts).strip()
    return ""


def require_env() -> tuple[str, str]:
    endpoint = os.environ.get("LLM_API_ENDPOINT")
    api_key = os.environ.get("LLM_API_KEY")
    if not endpoint or not api_key:
        raise CliError(
            "E_AUTH_MISSING",
            "LLM_API_ENDPOINT and LLM_API_KEY must be set.",
            "Run inside a repo shell that exposes the repo-local LLM env, or load the repo .env first.",
            EXIT_AUTH,
        )
    return endpoint, api_key


def iso_utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def make_result(command: str, status: str, data: dict | None, error: dict | None, started: float) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "command": command,
        "status": status,
        "data": data,
        "error": error,
        "meta": {
            "request_id": str(uuid.uuid4()),
            "duration_ms": round((time.time() - started) * 1000, 2),
            "timestamp_utc": iso_utc_now(),
        },
    }


def wants_plain(args: argparse.Namespace) -> bool:
    return bool(getattr(args, "plain", False))


def emit(payload: dict, plain_text: str | None, plain: bool) -> None:
    if plain and plain_text is not None:
        print(plain_text)
        return
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def usage_to_dict(usage) -> dict | None:
    if usage is None:
        return None
    if hasattr(usage, "model_dump"):
        dumped = usage.model_dump()
        if isinstance(dumped, dict):
            return dumped
    data = {}
    for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
        value = getattr(usage, key, None)
        if value is not None:
            data[key] = value
    return data or None


def cmd_validate_env(args: argparse.Namespace) -> int:
    started = args._started_at
    endpoint = os.environ.get("LLM_API_ENDPOINT")
    api_key = os.environ.get("LLM_API_KEY")
    data = {
        "env": {
            "LLM_API_ENDPOINT": bool(endpoint),
            "LLM_API_KEY": bool(api_key),
        },
        "default_model": DEFAULT_MODEL,
        "ready": bool(endpoint and api_key),
    }
    payload = make_result("draft_with_llm validate-env", "ok", data, None, started)
    emit(payload, "ready" if data["ready"] else "missing env", wants_plain(args))
    return EXIT_OK


def cmd_render_prompt(args: argparse.Namespace) -> int:
    started = args._started_at
    brief = resolve_brief(args)
    system_prompt, user_prompt = build_prompts(args.mode, brief, args.instruction, args.context_file)
    data = {
        "mode": args.mode,
        "model": args.model,
        "prompt": {
            "system": system_prompt,
            "user": user_prompt,
        },
        "sources": {
            "brief_from": str(args.input_file) if args.input_file else ("stdin" if not sys.stdin.isatty() and not args.brief else "argument"),
            "context_files": [str(path) for path in args.context_file],
            "extra_instruction_count": len(args.instruction),
        },
    }
    payload = make_result("draft_with_llm render-prompt", "ok", data, None, started)
    emit(payload, f"[system]\n{system_prompt}\n\n[user]\n{user_prompt}", wants_plain(args))
    return EXIT_OK


def cmd_draft(args: argparse.Namespace) -> int:
    started = args._started_at
    endpoint, api_key = require_env()
    brief = resolve_brief(args)
    system_prompt, user_prompt = build_prompts(args.mode, brief, args.instruction, args.context_file)
    client = OpenAI(api_key=api_key, base_url=endpoint, timeout=args.timeout_seconds)
    try:
        response = client.chat.completions.create(
            model=args.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=args.temperature,
            max_tokens=args.max_tokens,
        )
    except Exception as exc:
        error_name = type(exc).__name__
        exit_code = EXIT_TIMEOUT if "timeout" in error_name.lower() else EXIT_DEPENDENCY
        hint = (
            "Increase --timeout-seconds or retry the request."
            if exit_code == EXIT_TIMEOUT
            else "Check the repo-local LLM endpoint, model name, and credentials."
        )
        raise CliError(
            "E_LLM_REQUEST_FAILED" if exit_code == EXIT_DEPENDENCY else "E_TIMEOUT",
            f"LLM request failed: {error_name}",
            hint,
            exit_code,
            retryable=True,
        ) from exc

    text = extract_text(response)
    if not text:
        raise CliError(
            "E_EMPTY_RESPONSE",
            "Model returned empty content.",
            "Retry with a clearer brief or a higher token limit.",
            EXIT_GENERIC,
            retryable=True,
        )
    if args.output_file:
        args.output_file.write_text(text + "\n", encoding="utf-8")
    data = {
        "mode": args.mode,
        "model": args.model,
        "draft": text,
        "output_file": str(args.output_file) if args.output_file else None,
        "usage": usage_to_dict(getattr(response, "usage", None)),
        "sources": {
            "context_files": [str(path) for path in args.context_file],
            "extra_instruction_count": len(args.instruction),
        },
    }
    payload = make_result("draft_with_llm draft", "ok", data, None, started)
    emit(payload, text, wants_plain(args))
    return EXIT_OK


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    args._started_at = time.time()
    try:
        if args.subcommand == "validate-env":
            return cmd_validate_env(args)
        if args.subcommand == "render-prompt":
            return cmd_render_prompt(args)
        if args.subcommand == "draft":
            return cmd_draft(args)
        raise CliError("E_INVALID_USAGE", f"Unknown subcommand: {args.subcommand}", "Run --help to inspect supported commands.", EXIT_USAGE)
    except CliError as exc:
        payload = make_result(
            f"draft_with_llm {getattr(args, 'subcommand', 'unknown')}",
            "error",
            None,
            {
                "code": exc.code,
                "message": exc.message,
                "retryable": exc.retryable,
                "hint": exc.hint,
            },
            getattr(args, "_started_at", time.time()),
        )
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return exc.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
