from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

from tests.control_plane.support import (
    REPO_ROOT,
    TempDirTestCase,
    write_executable,
    write_text,
)

SCRIPT_PATH = (
    REPO_ROOT
    / "skills-source/owned/local-transcription/scripts/local_transcription.py"
)


def load_client_module() -> Any:
    spec = importlib.util.spec_from_file_location(
        "local_transcription_skill_client",
        SCRIPT_PATH,
    )
    if spec is None or spec.loader is None:
        raise AssertionError("Unable to load local transcription skill client.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class LocalTranscriptionSkillClientTests(TempDirTestCase):
    def test_doctor_returns_agent_first_json_contract(self) -> None:
        module = load_client_module()
        upload_bin = write_executable(
            self.temp_path / "upload-media",
            "#!/usr/bin/env bash\nexit 0\n",
        )

        exit_code, stdout = module.run(
            [
                "doctor",
                "--json",
                "--upload-media-bin",
                str(upload_bin),
            ]
        )

        payload = json.loads(stdout)
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["schema_version"], "1.0")
        self.assertEqual(payload["command"], "local-transcription doctor")
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["error"], None)
        self.assertTrue(payload["data"]["ready"]["client"])
        self.assertTrue(payload["data"]["ready"]["upload_media"])

    def test_transcribe_local_file_uploads_to_cache_and_submits_artifact_job(
        self,
    ) -> None:
        module = load_client_module()
        audio_file = write_text(self.temp_path / "audio.m4a", "audio")
        argv_log = self.temp_path / "upload-argv.json"
        upload_bin = write_executable(
            self.temp_path / "upload-media",
            "\n".join(
                [
                    "#!/usr/bin/env python3",
                    "import json, pathlib, sys",
                    f"pathlib.Path({str(argv_log)!r}).write_text(json.dumps(sys.argv))",
                    "payload = {",
                    "  'schema_version': '1.0',",
                    "  'command': 'upload-media',",
                    "  'status': 'ok',",
                    "  'data': {'upload': {",
                    "    'file_path': sys.argv[sys.argv.index('--file') + 1],",
                    "    'file_name': 'audio.m4a',",
                    "    'storage_prefix': sys.argv[sys.argv.index('--storage-prefix') + 1],",
                    "    'destination_path': 'cache/local-transcription/audio.m4a',",
                    "    'content_sha256': 'abc123',",
                    "    'cached': False,",
                    "    'url': 'https://storage.example/cache/audio.m4a'",
                    "  }},",
                    "  'error': None,",
                    "  'meta': {}",
                    "}",
                    "print(json.dumps(payload))",
                    "",
                ]
            ),
        )
        fake_client = _FakeApiClient()

        with patch.object(module, "_build_api_client", return_value=fake_client):
            exit_code, stdout = module.run(
                [
                    "transcribe",
                    "--file",
                    str(audio_file),
                    "--upload-media-bin",
                    str(upload_bin),
                    "--progress",
                    "off",
                ]
            )

        payload = json.loads(stdout)
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["data"]["transcript"], "Hello world")
        self.assertEqual(
            payload["data"]["artifacts"]["transcript_url"],
            "https://storage.example/cache/transcript.txt",
        )
        self.assertEqual(fake_client.submissions[0]["media_url"], "https://storage.example/cache/audio.m4a")
        self.assertEqual(fake_client.submissions[0]["provider"], "local_transcription")
        self.assertTrue(fake_client.submissions[0]["diarize"])
        upload_argv = json.loads(argv_log.read_text(encoding="utf-8"))
        self.assertEqual(upload_argv[upload_argv.index("--storage-prefix") + 1], "cache")

    def test_missing_input_uses_usage_error_contract(self) -> None:
        module = load_client_module()

        exit_code, stdout = module.run(["transcribe", "--json"])

        payload = json.loads(stdout)
        self.assertEqual(exit_code, 2)
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["error"]["code"], "E_USAGE")
        self.assertEqual(payload["data"], None)


class _FakeApiClient:
    def __init__(self) -> None:
        self.submissions: list[dict[str, Any]] = []

    def submit_transcription(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.submissions.append(payload)
        return {"job_id": "TRANSCRIPTION_ARTIFACTS_test", "cached": False}

    def wait_for_job(
        self,
        job_id: str,
        *,
        progress_callback: Any = None,
    ) -> dict[str, Any]:
        return {
            "job_id": job_id,
            "status": "completed",
            "cached": False,
            "result": {
                "source_id": "source-123",
                "provider": "local_transcription",
                "text": "Hello world",
                "transcript_url": "https://storage.example/cache/transcript.txt",
                "words_url": "https://storage.example/cache/words.json",
                "sentences_url": "https://storage.example/cache/sentences.json",
            },
        }
