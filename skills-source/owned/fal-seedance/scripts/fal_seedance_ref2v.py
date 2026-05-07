#!/usr/bin/env python3
"""fal Seedance reference-to-video CLI (Python port).

Subcommands: validate | doctor [--remote] | run

JSON contract is identical to the prior Node.js client at
scripts/fal_seedance_ref2v.mjs (now removed). See SKILL.md for details.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import mimetypes
import os
import re
import secrets as _secrets
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

import fal_client
from fal_client import StorageSettings

SCHEMA_VERSION = "1.0"
DEFAULT_ENDPOINT = "bytedance/seedance-2.0/reference-to-video"
VALID_ENDPOINTS = {
    "bytedance/seedance-2.0/reference-to-video",
    "bytedance/seedance-2.0/fast/reference-to-video",
}
DEFAULT_SECRET_ENV_FILE = Path.home() / ".secrets" / "fal" / "env"
VALID_RESOLUTIONS = {"480p", "720p", "1080p"}
VALID_ASPECT_RATIOS = {"auto", "21:9", "16:9", "4:3", "1:1", "3:4", "9:16"}
VALID_LIFECYCLES = {"never", "immediate", "1h", "1d", "7d", "30d", "1y"}
DOCTOR_CHECK_FILENAME = "fal-seedance-doctor.txt"
SECRET_SYNC_HINT = (
    "Sync it with: /Users/dobby/GitHub/scripts/sync/keyvault-sync-machine-secrets.sh "
    "--apply --integration fal"
)
MAPPING_FILE = "/Users/dobby/GitHub/scripts/sync/machine-secrets/fal.env.map"


def now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat().replace("+00:00", "Z")


def make_request_id() -> str:
    return f"fal-seedance-{int(time.time() * 1000)}-{_secrets.token_hex(4)}"


class CliError(Exception):
    def __init__(self, code: str, message: str, *, exit_code: int = 1, retryable: bool = False, hint: str | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.exit_code = exit_code
        self.retryable = retryable
        self.hint = hint


def fail(code: str, message: str, *, exit_code: int = 1, retryable: bool = False, hint: str | None = None) -> None:
    raise CliError(code, message, exit_code=exit_code, retryable=retryable, hint=hint)


def is_url(value: str) -> bool:
    return bool(re.match(r"^https?://", value, re.IGNORECASE))


def slugify(value: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:80]
    return s or "seedance-ref2v"


def shell_unquote(raw: str) -> str:
    v = raw.strip()
    if v.startswith("'") and v.endswith("'"):
        return v[1:-1].replace("'\\''", "'")
    if v.startswith('"') and v.endswith('"'):
        return v[1:-1].replace('\\"', '"').replace("\\\\", "\\")
    return v


def expand_path(p: str | Path) -> Path:
    return Path(os.path.expanduser(str(p))).resolve()


def read_secret_env_file(secret_env_file: str | Path) -> dict[str, Any]:
    path = expand_path(secret_env_file)
    if not path.exists():
        fail("E_AUTH_MISSING", f"Secret env file not found: {path}", exit_code=3, hint=SECRET_SYNC_HINT)
    text = path.read_text("utf-8")
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r"^export\s+FAL_KEY=(.*)$", line)
        if m:
            value = shell_unquote(m.group(1))
            if not value:
                break
            return {"value": value, "path": str(path)}
    fail(
        "E_AUTH_MISSING",
        f"FAL_KEY was not found in {path}",
        exit_code=3,
        hint="Confirm /Users/dobby/GitHub/scripts/sync/machine-secrets/fal.env.map maps FAL_KEY=fal--api-key, then re-run the machine-secret sync.",
    )


@dataclass
class Options:
    command: str = "run"
    refs: list[str] = field(default_factory=list)
    video_urls: list[str] = field(default_factory=list)
    audio_urls: list[str] = field(default_factory=list)
    prompt: str | None = None
    prompt_file: str | None = None
    project: str | None = None
    output_dir: str | None = None
    receipt_dir: str | None = None
    name: str | None = None
    duration: str | int = "auto"
    resolution: str = "1080p"
    aspect_ratio: str = "auto"
    endpoint: str = DEFAULT_ENDPOINT
    generate_audio: bool = False
    seed: int | None = None
    dry_run: bool = False
    remote: bool = False
    json_output: bool = True
    plain: bool = False
    progress: str = "plain"
    secret_env_file: str = str(DEFAULT_SECRET_ENV_FILE)
    lifecycle: str = "30d"
    download: bool = True
    timeout_ms: int = 900_000
    poll_interval_ms: int = 1_000
    start_timeout_seconds: int | None = None


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="fal_seedance_ref2v.py",
        description="fal Seedance Reference-to-Video CLI.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("command", nargs="?", default="run", choices=["run", "validate", "doctor"])
    p.add_argument("--ref", "--image-url", dest="refs", action="append", default=[], help="Reference image path or URL; repeat up to 9.")
    p.add_argument("--video-url", dest="video_urls", action="append", default=[], help="Reference video URL; repeat up to 3.")
    p.add_argument("--audio-url", dest="audio_urls", action="append", default=[], help="Reference audio URL; repeat up to 3.")
    p.add_argument("--prompt", help="Seedance prompt. Refer to images as @Image1, @Image2, ...")
    p.add_argument("--prompt-file", help="Read prompt from a UTF-8 text file.")
    p.add_argument("--project", help="Project folder under projects/<id>.")
    p.add_argument("--output-dir")
    p.add_argument("--receipt-dir")
    p.add_argument("--name")
    p.add_argument("--duration", default="auto", help="auto or integer 4..15.")
    p.add_argument("--resolution", default="1080p", choices=sorted(VALID_RESOLUTIONS))
    p.add_argument("--aspect-ratio", default="auto", choices=sorted(VALID_ASPECT_RATIOS))
    p.add_argument("--endpoint", default=DEFAULT_ENDPOINT, choices=sorted(VALID_ENDPOINTS))
    p.add_argument("--generate-audio", dest="generate_audio", action="store_true")
    p.add_argument("--no-generate-audio", dest="generate_audio", action="store_false")
    p.set_defaults(generate_audio=False)
    p.add_argument("--seed", type=int)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--remote", action="store_true", help="doctor only: verify fal auth with a tiny storage upload.")
    p.add_argument("--plain", action="store_true", help="Print only the local video path or remote URL on success.")
    p.add_argument("--progress", default="plain", choices=["plain", "off"])
    p.add_argument("--secret-env-file", default=str(DEFAULT_SECRET_ENV_FILE))
    p.add_argument("--lifecycle", default="30d", choices=sorted(VALID_LIFECYCLES))
    p.add_argument("--no-download", dest="download", action="store_false")
    p.set_defaults(download=True)
    p.add_argument("--timeout-ms", type=int, default=900_000)
    p.add_argument("--poll-interval-ms", type=int, default=1_000)
    p.add_argument("--start-timeout-seconds", type=int, default=None)
    return p


def parse_args(argv: list[str]) -> Options:
    parser = build_arg_parser()
    ns = parser.parse_args(argv)
    return Options(
        command=ns.command,
        refs=list(ns.refs),
        video_urls=list(ns.video_urls),
        audio_urls=list(ns.audio_urls),
        prompt=ns.prompt,
        prompt_file=ns.prompt_file,
        project=ns.project,
        output_dir=ns.output_dir,
        receipt_dir=ns.receipt_dir,
        name=ns.name,
        duration=ns.duration,
        resolution=ns.resolution,
        aspect_ratio=ns.aspect_ratio,
        endpoint=ns.endpoint,
        generate_audio=ns.generate_audio,
        seed=ns.seed,
        dry_run=ns.dry_run,
        remote=ns.remote,
        plain=ns.plain,
        progress=ns.progress,
        secret_env_file=ns.secret_env_file,
        lifecycle=ns.lifecycle,
        download=ns.download,
        timeout_ms=ns.timeout_ms,
        poll_interval_ms=ns.poll_interval_ms,
        start_timeout_seconds=ns.start_timeout_seconds,
    )


def validate_run_options(opts: Options) -> None:
    if not opts.prompt and not opts.prompt_file:
        fail("E_USAGE", "Missing prompt", exit_code=2, hint="Pass --prompt <text> or --prompt-file <path>.")
    if opts.prompt and opts.prompt_file:
        fail("E_USAGE", "Use either --prompt or --prompt-file, not both", exit_code=2)
    if not opts.refs and not opts.video_urls and not opts.audio_urls:
        fail("E_USAGE", "At least one reference input is required", exit_code=2, hint="Pass one or more --ref image paths/URLs.")
    if len(opts.refs) > 9:
        fail("E_USAGE", "Seedance Ref2V accepts at most 9 image references", exit_code=2)
    if len(opts.video_urls) > 3:
        fail("E_USAGE", "Seedance Ref2V accepts at most 3 video references", exit_code=2)
    if len(opts.audio_urls) > 3:
        fail("E_USAGE", "Seedance Ref2V accepts at most 3 audio references", exit_code=2)
    if len(opts.refs) + len(opts.video_urls) + len(opts.audio_urls) > 12:
        fail("E_USAGE", "Seedance Ref2V accepts at most 12 total reference files", exit_code=2)
    if opts.endpoint == "bytedance/seedance-2.0/fast/reference-to-video" and opts.resolution == "1080p":
        fail(
            "E_USAGE",
            "1080p is not supported by the fast endpoint",
            exit_code=2,
            hint="Use --endpoint bytedance/seedance-2.0/reference-to-video for 1080p, or pass --resolution 720p.",
        )
    if opts.duration != "auto":
        try:
            d = int(opts.duration)
        except (TypeError, ValueError):
            fail("E_USAGE", f"Invalid duration: {opts.duration}", exit_code=2, hint="Use auto or an integer from 4 to 15.")
        if d < 4 or d > 15:
            fail("E_USAGE", f"Invalid duration: {opts.duration}", exit_code=2, hint="Use auto or an integer from 4 to 15.")
        opts.duration = d
    if opts.seed is not None and opts.seed < 0:
        fail("E_USAGE", f"Invalid seed: {opts.seed}", exit_code=2)
    if opts.timeout_ms <= 0:
        fail("E_USAGE", "Invalid --timeout-ms", exit_code=2)
    if opts.poll_interval_ms <= 0:
        fail("E_USAGE", "Invalid --poll-interval-ms", exit_code=2)


def read_prompt(opts: Options) -> str:
    if opts.prompt:
        return opts.prompt
    path = Path(opts.prompt_file).resolve()
    if not path.exists():
        fail("E_NOT_FOUND", f"Prompt file not found: {path}", exit_code=2)
    text = path.read_text("utf-8").strip()
    if not text:
        fail("E_USAGE", f"Prompt file is empty: {path}", exit_code=2)
    return text


def resolve_output_paths(opts: Options) -> dict[str, Any]:
    stamp = _dt.datetime.now(_dt.timezone.utc).isoformat().replace(":", "-").replace(".", "-")
    base_name = slugify(opts.name or f"seedance-ref2v-{stamp}")
    project_root = Path("projects") / opts.project if opts.project else None
    out_dir = Path(opts.output_dir) if opts.output_dir else (project_root / "seedance" / "renders" if project_root else None)
    receipt_dir = Path(opts.receipt_dir) if opts.receipt_dir else (project_root / "seedance" / "receipts" if project_root else None)
    if not out_dir or not receipt_dir:
        fail("E_USAGE", "Missing output location", exit_code=2, hint="Pass --project <id>, or both --output-dir and --receipt-dir.")
    return {
        "base_name": base_name,
        "output_dir": str(out_dir.resolve()),
        "receipt_dir": str(receipt_dir.resolve()),
        "video_path": str((out_dir / f"{base_name}.mp4").resolve()),
        "receipt_path": str((receipt_dir / f"{base_name}.json").resolve()),
    }


def mime_from_path(path: Path) -> str:
    ext = path.suffix.lower()
    table = {
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp",
        ".mp4": "video/mp4", ".mov": "video/quicktime", ".mp3": "audio/mpeg", ".wav": "audio/wav",
    }
    return table.get(ext) or mimetypes.guess_type(str(path))[0] or "application/octet-stream"


def upload_local_file(file_path: str, lifecycle: str) -> dict[str, Any]:
    abs_path = Path(file_path).resolve()
    if not abs_path.exists():
        fail("E_NOT_FOUND", f"Reference file not found: {abs_path}", exit_code=2)
    if not abs_path.is_file():
        fail("E_USAGE", f"Reference is not a file: {abs_path}", exit_code=2)
    data = abs_path.read_bytes()
    url = fal_client.upload(
        data,
        content_type=mime_from_path(abs_path),
        file_name=abs_path.name,
        lifecycle=StorageSettings(expires_in=lifecycle),
    )
    return {
        "source": str(abs_path),
        "url": url,
        "uploaded": True,
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def prepare_references(refs: list[str], lifecycle: str, dry_run: bool) -> list[dict[str, Any]]:
    prepared: list[dict[str, Any]] = []
    for ref in refs:
        if is_url(ref):
            prepared.append({"source": ref, "url": ref, "uploaded": False})
            continue
        if dry_run:
            abs_path = Path(ref).resolve()
            if not abs_path.exists():
                fail("E_NOT_FOUND", f"Reference file not found: {abs_path}", exit_code=2)
            prepared.append({"source": str(abs_path), "url": None, "uploaded": False, "upload_required": True, "bytes": abs_path.stat().st_size})
            continue
        prepared.append(upload_local_file(ref, lifecycle))
    return prepared


def make_input(prompt: str, opts: Options, image_urls: list[str | None]) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "prompt": prompt,
        "image_urls": image_urls,
        "video_urls": list(opts.video_urls),
        "audio_urls": list(opts.audio_urls),
        "resolution": opts.resolution,
        "duration": opts.duration,
        "aspect_ratio": opts.aspect_ratio,
        "generate_audio": opts.generate_audio,
    }
    if opts.seed is not None:
        payload["seed"] = opts.seed
    return payload


def download_video(url: str, out_path: str) -> dict[str, Any]:
    target = Path(out_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + f".tmp-{os.getpid()}-{int(time.time() * 1000)}")
    req = Request(url)
    with urlopen(req) as resp:
        if resp.status >= 400:
            fail("E_NETWORK", f"Failed to download generated video: {resp.status} {resp.reason}", exit_code=4, retryable=True, hint=url)
        data = resp.read()
    tmp.write_bytes(data)
    tmp.rename(target)
    return {
        "path": str(target),
        "bytes": target.stat().st_size,
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def write_receipt(receipt_path: str, receipt: dict[str, Any]) -> None:
    p = Path(receipt_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(receipt, indent=2) + "\n", "utf-8")


def print_envelope(started_at_ms: int, command: str, status: str, request_id: str, *, data: Any = None, error: Any = None) -> None:
    duration = int(time.time() * 1000) - started_at_ms
    envelope = {
        "schema_version": SCHEMA_VERSION,
        "command": command,
        "status": status,
        "data": data,
        "error": error,
        "meta": {"request_id": request_id, "duration_ms": duration, "timestamp_utc": now_iso()},
    }
    sys.stdout.write(json.dumps(envelope, indent=2) + "\n")


def cmd_validate(opts: Options, started_at_ms: int, request_id: str) -> int:
    secret_path = expand_path(opts.secret_env_file)
    secret_present = False
    hint: str | None = None
    try:
        read_secret_env_file(secret_path)
        secret_present = True
    except CliError as exc:
        if exc.code == "E_AUTH_MISSING":
            hint = exc.hint
        else:
            raise
    print_envelope(
        started_at_ms,
        command="fal-seedance.ref2v.validate",
        status="ok",
        request_id=request_id,
        data={
            "endpoint": opts.endpoint,
            "secret_env_file": str(secret_path),
            "secret_present": secret_present,
            "sync_hint": hint,
            "mapping_file": MAPPING_FILE,
        },
    )
    return 0


def run_remote_doctor_check(secret: dict[str, Any], request_id: str) -> dict[str, Any]:
    os.environ["FAL_KEY"] = secret["value"]
    payload = f"fal-seedance doctor {request_id}\n".encode("utf-8")
    url = fal_client.upload(
        payload,
        content_type="text/plain",
        file_name=DOCTOR_CHECK_FILENAME,
        lifecycle=StorageSettings(expires_in="immediate"),
    )
    host = None
    try:
        from urllib.parse import urlparse
        host = urlparse(url).hostname
    except Exception:
        host = None
    return {
        "requested": True,
        "status": "ok",
        "method": "fal_client.upload",
        "inference": False,
        "uploaded_bytes": len(payload),
        "url_host": host,
    }


def cmd_doctor(opts: Options, started_at_ms: int, request_id: str) -> int:
    secret_path = expand_path(opts.secret_env_file)
    secret = read_secret_env_file(secret_path)
    if opts.remote:
        remote_check = run_remote_doctor_check(secret, request_id)
    else:
        remote_check = {
            "requested": False,
            "status": "skipped",
            "method": None,
            "inference": False,
            "hint": "Pass --remote to verify fal provider auth via storage upload without video inference.",
        }
    print_envelope(
        started_at_ms,
        command="fal-seedance.ref2v.doctor",
        status="ok",
        request_id=request_id,
        data={
            "endpoint": opts.endpoint,
            "secret_env_file": str(secret_path),
            "secret_present": True,
            "mapping_file": MAPPING_FILE,
            "remote_check": remote_check,
            "production_inference_performed": False,
        },
    )
    return 0


def classify_unexpected_error(error: BaseException) -> CliError:
    message = str(error) or error.__class__.__name__
    provider_status = getattr(error, "status", None)
    body = getattr(error, "body", None)
    provider_detail = None
    if isinstance(body, dict):
        provider_detail = body.get("detail") or body.get("message")
    combined = " ".join(filter(None, [message, str(provider_detail) if provider_detail else None]))

    if provider_status == 403 and re.search(r"exhausted balance|top up|billing|balance", combined, re.IGNORECASE):
        return CliError(
            "E_BILLING_REQUIRED",
            "fal account is locked because the balance is exhausted",
            exit_code=3,
            hint="Top up the fal account balance at https://fal.ai/dashboard/billing, then rerun doctor --remote.",
        )
    if re.search(r"401|403|unauthori[sz]ed|forbidden|invalid.*key|api key|authentication", combined, re.IGNORECASE):
        return CliError(
            "E_AUTH_PROVIDER",
            "fal rejected the configured credentials",
            exit_code=3,
            hint="Refresh ~/.secrets/fal/env from Key Vault and verify fal--api-key is valid.",
        )
    if re.search(r"network|ENOTFOUND|ECONN|ETIMEDOUT|timeout|socket|TLS|DNS", combined, re.IGNORECASE):
        return CliError(
            "E_NETWORK",
            "fal network request failed",
            exit_code=4,
            retryable=True,
            hint="Retry later or check network connectivity and fal status.",
        )
    return CliError(
        "E_UNEXPECTED",
        provider_detail or message,
        exit_code=1,
        hint="Run doctor --remote for provider connectivity, then retry with --dry-run before generation.",
    )


def cmd_run(opts: Options, started_at_ms: int, request_id: str) -> int:
    validate_run_options(opts)
    paths = resolve_output_paths(opts)
    prompt = read_prompt(opts)

    secret = None
    if not opts.dry_run:
        secret = read_secret_env_file(opts.secret_env_file)
        os.environ["FAL_KEY"] = secret["value"]

    references = prepare_references(opts.refs, opts.lifecycle, opts.dry_run)
    image_urls_for_payload = [ref["url"] for ref in references if ref.get("url")]
    planned_input = make_input(prompt, opts, image_urls_for_payload)

    if opts.dry_run:
        dry_image_urls: list[str] = [
            ref["url"] if ref.get("url") else f"upload://Image{i + 1}"
            for i, ref in enumerate(references)
        ]
        print_envelope(
            started_at_ms,
            command="fal-seedance.ref2v.run",
            status="ok",
            request_id=request_id,
            data={
                "dry_run": True,
                "endpoint": opts.endpoint,
                "input": make_input(prompt, opts, dry_image_urls),
                "references": references,
                "output": paths,
                "secret_env_file": str(expand_path(opts.secret_env_file)),
            },
        )
        return 0

    if opts.progress != "off":
        sys.stderr.write(f"Submitting fal Seedance request to {opts.endpoint}\n")

    def on_enqueue(req_id: str) -> None:
        if opts.progress != "off":
            sys.stderr.write(f"fal request id: {req_id}\n")

    def on_queue_update(update: Any) -> None:
        if opts.progress == "off":
            return
        status = getattr(update, "status", None) or update.__class__.__name__
        if status == "IN_QUEUE" or update.__class__.__name__ == "Queued":
            pos = getattr(update, "queue_position", None)
            sys.stderr.write(f"queue: position {pos}\n")
        elif status == "IN_PROGRESS" or update.__class__.__name__ == "InProgress":
            logs = getattr(update, "logs", None)
            last_log = logs[-1] if isinstance(logs, list) and logs else None
            if isinstance(last_log, dict) and last_log.get("message"):
                sys.stderr.write(f"progress: {last_log['message']}\n")
            else:
                sys.stderr.write("progress: IN_PROGRESS\n")

    try:
        result = fal_client.subscribe(
            opts.endpoint,
            arguments=planned_input,
            with_logs=opts.progress != "off",
            on_enqueue=on_enqueue,
            on_queue_update=on_queue_update,
            start_timeout=opts.start_timeout_seconds,
            client_timeout=opts.timeout_ms / 1000.0 if opts.timeout_ms else None,
        )
    except Exception as exc:
        raise classify_unexpected_error(exc) from exc

    video = (result or {}).get("video") if isinstance(result, dict) else None
    video_url = video.get("url") if isinstance(video, dict) else None
    if not video_url:
        fail("E_PROVIDER_OUTPUT", "fal result did not include video.url", exit_code=1, hint="Inspect the receipt payload and fal dashboard request.")

    downloaded = None
    if opts.download:
        downloaded = download_video(video_url, paths["video_path"])

    fal_request_id = (result or {}).get("requestId") if isinstance(result, dict) else None
    receipt = {
        "schema_version": SCHEMA_VERSION,
        "endpoint": opts.endpoint,
        "local_request_id": request_id,
        "fal_request_id": fal_request_id,
        "created_at_utc": now_iso(),
        "input": planned_input,
        "references": references,
        "result": result,
        "output": {
            "video_url": video_url,
            "local_video": downloaded,
            "receipt_path": paths["receipt_path"],
        },
        "secret_env_file": secret["path"] if secret else None,
    }
    write_receipt(paths["receipt_path"], receipt)

    if opts.plain:
        sys.stdout.write(f"{(downloaded or {}).get('path') if downloaded else video_url}\n")
        return 0

    print_envelope(
        started_at_ms,
        command="fal-seedance.ref2v.run",
        status="ok",
        request_id=request_id,
        data={
            "endpoint": opts.endpoint,
            "fal_request_id": fal_request_id,
            "video": video,
            "seed": (result or {}).get("seed") if isinstance(result, dict) else None,
            "local_video": downloaded,
            "receipt_path": paths["receipt_path"],
            "references": references,
        },
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    started_at_ms = int(time.time() * 1000)
    request_id = make_request_id()
    command = "fal-seedance.ref2v.run"
    try:
        opts = parse_args(argv if argv is not None else sys.argv[1:])
        command = f"fal-seedance.ref2v.{opts.command}"
        if opts.command == "validate":
            return cmd_validate(opts, started_at_ms, request_id)
        if opts.command == "doctor":
            return cmd_doctor(opts, started_at_ms, request_id)
        if opts.command == "run":
            return cmd_run(opts, started_at_ms, request_id)
        fail("E_USAGE", f"Unknown command: {opts.command}", exit_code=2, hint="Use run, validate, or doctor.")
    except CliError as exc:
        print_envelope(
            started_at_ms,
            command=command,
            status="error",
            request_id=request_id,
            error={"code": exc.code, "message": exc.message, "retryable": exc.retryable, "hint": exc.hint},
        )
        return exc.exit_code
    except KeyboardInterrupt:
        print_envelope(
            started_at_ms,
            command=command,
            status="error",
            request_id=request_id,
            error={"code": "E_INTERRUPTED", "message": "Interrupted", "retryable": True, "hint": None},
        )
        return 5
    except BaseException as exc:
        cli_err = classify_unexpected_error(exc)
        print_envelope(
            started_at_ms,
            command=command,
            status="error",
            request_id=request_id,
            error={"code": cli_err.code, "message": cli_err.message, "retryable": cli_err.retryable, "hint": cli_err.hint},
        )
        return cli_err.exit_code
    return 0


if __name__ == "__main__":
    sys.exit(main())
