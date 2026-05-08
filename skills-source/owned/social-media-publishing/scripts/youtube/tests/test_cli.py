from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


def load_cli_module():
    path = Path(__file__).resolve().parents[1] / "cli.py"
    spec = importlib.util.spec_from_file_location("youtube_cli", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def read_json_stdout(capsys):
    out = capsys.readouterr().out
    return json.loads(out)


def test_upload_video_dry_run_reports_modal_route_for_local_file(
    tmp_path: Path, capsys
) -> None:
    cli = load_cli_module()
    video = tmp_path / "video.mp4"
    video.write_bytes(b"video")
    desc = tmp_path / "desc.md"
    desc.write_text("Description", encoding="utf-8")

    exit_code = cli.run(
        [
            "--env-file",
            str(tmp_path / "missing.env"),
            "--progress",
            "off",
            "upload-video",
            "--video",
            str(video),
            "--title",
            "Test video",
            "--description-file",
            str(desc),
            "--credentials-id",
            "ADITHYAN",
            "--dry-run",
        ]
    )

    payload = read_json_stdout(capsys)
    assert exit_code == 0
    assert payload["status"] == "ok"
    assert payload["data"]["selected_route"] == "modal"
    assert payload["data"]["dry_run"] is True
    assert payload["data"]["artifact"]["source"] == "local_file"
    assert payload["data"]["payload_preview"]["video_volume_path"].endswith(
        "/video.mp4"
    )
    assert "description" not in payload["data"]["payload_preview"]


def test_upload_video_requires_credentials_id(tmp_path: Path, capsys) -> None:
    cli = load_cli_module()
    video = tmp_path / "video.mp4"
    video.write_bytes(b"video")

    exit_code = cli.run(
        [
            "--env-file",
            str(tmp_path / "missing.env"),
            "--progress",
            "off",
            "upload-video",
            "--video",
            str(video),
            "--title",
            "Test video",
            "--dry-run",
        ]
    )

    payload = read_json_stdout(capsys)
    assert exit_code == 2
    assert payload["status"] == "error"
    assert payload["error"]["code"] == "E_MISSING_CREDENTIALS_ID"


def test_upload_video_public_url_calls_modal(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    cli = load_cli_module()

    monkeypatch.setattr(
        cli, "maybe_reexec_with_modal_python", lambda *_args, **_kwargs: None
    )
    monkeypatch.setattr(cli, "import_modal_module", lambda: object())

    captured = {}

    def fake_call_modal_upload(*, modal, config, payload, args):
        captured["payload"] = payload
        return {
            "video_id": "abc123",
            "video_url": "https://www.youtube.com/watch?v=abc123",
            "attempts": 1,
            "upload_retried": False,
            "response": {"id": "abc123"},
        }

    monkeypatch.setattr(cli, "call_modal_upload", fake_call_modal_upload)

    exit_code = cli.run(
        [
            "--env-file",
            str(tmp_path / "missing.env"),
            "--progress",
            "off",
            "upload-video",
            "--video-url",
            "https://example.com/video.mp4",
            "--title",
            "Test video",
            "--description",
            "Description",
            "--privacy",
            "unlisted",
            "--credentials-id",
            "ADITHYAN",
        ]
    )

    payload = read_json_stdout(capsys)
    assert exit_code == 0
    assert payload["status"] == "ok"
    assert payload["data"]["selected_route"] == "modal"
    assert payload["data"]["result"]["video_url"].endswith("abc123")
    assert captured["payload"]["video_url"] == "https://example.com/video.mp4"
    assert "video_volume_path" not in captured["payload"]
