from __future__ import annotations

import importlib.util
import json
import contextlib
import io
from pathlib import Path
from typing import Any
from unittest.mock import patch

from tests.control_plane.support import REPO_ROOT, TempDirTestCase, write_text

SCRIPT_PATH = REPO_ROOT / "skills-source/owned/media-toolkit/scripts/media_toolkit.py"


def load_client_module() -> Any:
    spec = importlib.util.spec_from_file_location(
        "media_toolkit_skill_client",
        SCRIPT_PATH,
    )
    if spec is None or spec.loader is None:
        raise AssertionError("Unable to load media toolkit skill client.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class MediaToolkitTranscriptionTests(TempDirTestCase):
    def test_transcribe_local_file_uses_artifact_job_path(self) -> None:
        module = load_client_module()
        audio_file = write_text(self.temp_path / "audio.m4a", "audio")
        fake_client = _FakeApiClient()

        def fake_upload(
            file_path: str,
            *,
            storage_prefix: str,
            destination_prefix: str,
        ) -> dict[str, Any]:
            self.assertEqual(Path(file_path), audio_file)
            self.assertEqual(storage_prefix, "cache")
            self.assertEqual(destination_prefix, "local-transcription")
            return {
                "file_path": str(audio_file),
                "file_name": "audio.m4a",
                "storage_prefix": storage_prefix,
                "destination_path": "cache/local-transcription/audio.m4a",
                "content_sha256": "abc123",
                "cached": False,
                "url": "https://storage.example/cache/audio.m4a",
            }

        with (
            patch.object(module, "upload_local_file", side_effect=fake_upload),
            patch.object(module, "_build_api_client", return_value=fake_client),
        ):
            exit_code, stdout = module.run(
                [
                    "transcribe",
                    "--file",
                    str(audio_file),
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
        self.assertNotIn("result", payload["data"])
        self.assertEqual(fake_client.submissions[0][0], "/media/transcribe/artifacts")
        self.assertEqual(
            fake_client.submissions[0][1],
            {
                "media_url": "https://storage.example/cache/audio.m4a",
                "channel_name": "MISC",
                "use_cache": True,
                "provider": "local_transcription",
                "diarize": True,
                "identify_speakers": False,
                "speaker_identification_context": None,
                "force_speaker_identification": False,
            },
        )

    def test_transcribe_help_hides_old_provider_and_cache_knobs(self) -> None:
        module = load_client_module()

        stdout_buffer = io.StringIO()
        with contextlib.redirect_stdout(stdout_buffer):
            exit_code, stdout = module.run(["transcribe", "--help"])

        help_text = stdout or stdout_buffer.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertNotIn("--provider", help_text)
        self.assertNotIn("--use-cache", help_text)
        self.assertNotIn("--no-use-cache", help_text)
        self.assertNotIn("--diarize", help_text)
        self.assertIn("--identify-speakers", help_text)
        self.assertIn("--speaker-identification-context", help_text)
        self.assertIn("--force-speaker-identification", help_text)


class _FakeApiClient:
    def __init__(self) -> None:
        self.submissions: list[tuple[str, dict[str, Any]]] = []

    def submit_job(self, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        self.submissions.append((endpoint, payload))
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
                "word_count": 2,
                "sentence_count": 1,
                "transcript_url": "https://storage.example/cache/transcript.txt",
                "words_url": "https://storage.example/cache/words.json",
                "sentences_url": "https://storage.example/cache/sentences.json",
            },
        }

    def fetch_text(self, url: str) -> str:
        if url != "https://storage.example/cache/transcript.txt":
            raise AssertionError(f"Unexpected transcript URL: {url}")
        return "Hello world"
