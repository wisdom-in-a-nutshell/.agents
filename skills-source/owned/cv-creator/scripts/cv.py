#!/usr/bin/env python3
"""
Generic CV build/review helper for repo-local LaTeX career materials.
"""

import argparse
import json
import shutil
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = "1.0"
TOOL_VERSION = "0.1.0"
REVIEW_TMP_ROOT = Path("/tmp/cv-review")


class CLIUsageError(Exception):
    pass


class CVArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        raise CLIUsageError(message)


def now_utc():
    return datetime.now(timezone.utc).isoformat()


def result(command, status, data=None, error=None, duration_ms=0):
    return {
        "schema_version": SCHEMA_VERSION,
        "command": command,
        "status": status,
        "data": data or {},
        "error": error,
        "meta": {
            "request_id": str(uuid.uuid4()),
            "duration_ms": round(duration_ms),
            "timestamp_utc": now_utc(),
        },
    }


def emit(obj, plain=False):
    if plain:
        if obj["status"] == "ok":
            print(obj.get("data", {}).get("message", "ok"))
        else:
            message = (obj.get("error") or {}).get("message", "error")
            hint = (obj.get("error") or {}).get("hint", "")
            print(f"ERROR: {message}", file=sys.stderr)
            if hint:
                print(f"HINT:  {hint}", file=sys.stderr)
    else:
        print(json.dumps(obj, indent=2))


def usage_error(message, hint, plain=False):
    err = {
        "code": "E_USAGE",
        "message": message,
        "retryable": False,
        "hint": hint,
    }
    emit(result("cv.parse", "error", error=err), plain)
    return 2


def check_dep(name):
    if shutil.which(name):
        return None
    return {
        "code": "E_DEP_MISSING",
        "message": f"Required tool '{name}' not found in PATH.",
        "retryable": False,
        "hint": f"Install or expose '{name}' before running this command.",
    }


def find_repo_root(start: Path) -> Path | None:
    current = start.resolve()
    for candidate in [current, *current.parents]:
        if (candidate / ".git").exists() or (candidate / "AGENTS.md").exists():
            return candidate
    return None


def source_for(repo_root: Path, kind: str, company: str | None) -> Path:
    latex_root = repo_root / "reference" / "career" / "cv" / "latex"
    if company:
        return latex_root / "tailored" / company / f"{kind}.tex"
    return latex_root / "base" / f"{kind}.tex"


def review_dir_for(company: str | None, kind: str) -> Path:
    label = company or "base"
    return REVIEW_TMP_ROOT / label / kind


def run_build(repo_root: Path, kind: str, company: str | None, plain: bool) -> int:
    t0 = time.monotonic()
    command = "cv.build"
    source = source_for(repo_root, kind, company)

    if not source.exists():
        err = {
            "code": "E_FILE_NOT_FOUND",
            "message": f"LaTeX source not found: {source}",
            "retryable": False,
            "hint": "Create the expected base or tailored file before building.",
        }
        emit(result(command, "error", error=err, duration_ms=(time.monotonic() - t0) * 1000), plain)
        return 2

    dep_err = check_dep("tectonic")
    if dep_err:
        emit(result(command, "error", error=dep_err, duration_ms=(time.monotonic() - t0) * 1000), plain)
        return 4

    proc = subprocess.run(
        ["tectonic", str(source.name)],
        cwd=str(source.parent),
        capture_output=True,
        text=True,
    )

    duration_ms = (time.monotonic() - t0) * 1000
    if proc.returncode != 0:
        if proc.stderr:
            print(proc.stderr, file=sys.stderr)
        err = {
            "code": "E_COMPILE_FAILED",
            "message": "tectonic compilation failed.",
            "retryable": True,
            "hint": "Check stderr output above for LaTeX errors.",
        }
        emit(result(command, "error", error=err, duration_ms=duration_ms), plain)
        return 1

    if proc.stderr:
        print(proc.stderr, file=sys.stderr)
    pdf = source.with_suffix(".pdf")
    data = {
        "message": f"Compiled successfully → {pdf}",
        "source": str(source),
        "pdf": str(pdf),
    }
    emit(result(command, "ok", data=data, duration_ms=duration_ms), plain)
    return 0


def run_review(repo_root: Path, kind: str, company: str | None, plain: bool) -> int:
    t0 = time.monotonic()
    command = "cv.review"
    source = source_for(repo_root, kind, company)
    pdf = source.with_suffix(".pdf")

    if not pdf.exists():
        err = {
            "code": "E_FILE_NOT_FOUND",
            "message": f"PDF not found: {pdf}",
            "retryable": False,
            "hint": "Run the build command first.",
        }
        emit(result(command, "error", error=err, duration_ms=(time.monotonic() - t0) * 1000), plain)
        return 2

    dep_err = check_dep("pdftoppm")
    if dep_err:
        emit(result(command, "error", error=dep_err, duration_ms=(time.monotonic() - t0) * 1000), plain)
        return 4

    review_dir = review_dir_for(company, kind)
    if review_dir.exists():
        shutil.rmtree(review_dir)
    review_dir.mkdir(parents=True, exist_ok=True)

    proc = subprocess.run(
        ["pdftoppm", "-png", str(pdf), str(review_dir / "page")],
        capture_output=True,
        text=True,
    )

    duration_ms = (time.monotonic() - t0) * 1000
    if proc.returncode != 0:
        if proc.stderr:
            print(proc.stderr, file=sys.stderr)
        err = {
            "code": "E_RENDER_FAILED",
            "message": "pdftoppm rendering failed.",
            "retryable": True,
            "hint": "Check stderr output above.",
        }
        emit(result(command, "error", error=err, duration_ms=duration_ms), plain)
        return 1

    pages = sorted(str(p) for p in review_dir.glob("page-*.png"))
    data = {
        "message": f"Rendered {len(pages)} page(s) to {review_dir}",
        "pdf": str(pdf),
        "pages": pages,
        "review_dir": str(review_dir),
    }
    emit(result(command, "ok", data=data, duration_ms=duration_ms), plain)
    return 0


def run_clean(plain: bool) -> int:
    t0 = time.monotonic()
    command = "cv.clean"
    removed = []
    if REVIEW_TMP_ROOT.exists():
        shutil.rmtree(REVIEW_TMP_ROOT)
        removed.append(str(REVIEW_TMP_ROOT))
    data = {
        "message": f"Cleaned {len(removed)} path(s)." if removed else "Nothing to clean.",
        "removed": removed,
    }
    emit(result(command, "ok", data=data, duration_ms=(time.monotonic() - t0) * 1000), plain)
    return 0


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    plain_requested = "--plain" in argv

    if "--version" in argv:
        data = {
            "message": TOOL_VERSION,
            "version": TOOL_VERSION,
        }
        emit(result("cv.version", "ok", data=data), plain_requested)
        return 0

    parser = CVArgumentParser(description="Build and review repo-local LaTeX CV files.")
    output_group = parser.add_mutually_exclusive_group()
    output_group.add_argument("--json", action="store_true", help="Emit JSON output (default).")
    output_group.add_argument("--plain", action="store_true", help="Emit plain text instead of JSON.")
    parser.add_argument("--no-input", action="store_true", help="Disable interactive input. This tool never prompts.")
    parser.add_argument("--version", action="store_true", help="Show tool version and exit.")
    parser.add_argument("command", choices=["build", "review", "clean"], nargs="?")
    parser.add_argument("--kind", choices=["resume", "cover-letter"], default="resume")
    parser.add_argument("--company", help="Company slug under tailored/<company>/")
    parser.add_argument("--root", help="Repo root override. Defaults to the current repo.")

    try:
        args = parser.parse_args(argv)
    except CLIUsageError as exc:
        return usage_error(
            str(exc),
            "Run `cv.py --help` to inspect valid commands and flags.",
            plain_requested,
        )

    if args.command is None:
        return usage_error(
            "Missing required command.",
            "Use one of: build, review, clean. Run `cv.py --help` for examples.",
            args.plain,
        )

    repo_root = Path(args.root).resolve() if args.root else find_repo_root(Path.cwd())
    if args.command != "clean" and not repo_root:
        err = {
            "code": "E_REPO_NOT_FOUND",
            "message": "Could not determine repo root from the current working directory.",
            "retryable": False,
            "hint": "Run from inside the target repo or pass --root <repo-path>.",
        }
        emit(result(f"cv.{args.command}", "error", error=err), args.plain)
        return 2

    if args.command == "build":
        return run_build(repo_root, args.kind, args.company, args.plain)
    if args.command == "review":
        return run_review(repo_root, args.kind, args.company, args.plain)
    return run_clean(args.plain)


if __name__ == "__main__":
    raise SystemExit(main())
