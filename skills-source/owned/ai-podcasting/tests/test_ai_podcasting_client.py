import importlib.util
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
MODULE_PATH = SCRIPTS_DIR / "ai_podcasting_client.py"

if str(SCRIPTS_DIR) not in sys.path:
  sys.path.insert(0, str(SCRIPTS_DIR))

SPEC = importlib.util.spec_from_file_location("ai_podcasting_client", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
  raise RuntimeError(f"Failed to load module spec for {MODULE_PATH}")

client = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(client)


class BuildTextPreviewTests(unittest.TestCase):
  def test_build_text_preview_strips_html_and_truncates(self) -> None:
    preview = client.build_text_preview("<p>Hello <strong>world</strong>&nbsp;again</p>", limit=12)

    self.assertEqual(preview["preview"], "Hello wor...")
    self.assertEqual(preview["length"], 17)


class ResolveOutputModeTests(unittest.TestCase):
  def test_resolve_output_mode_defaults_to_json(self) -> None:
    args = SimpleNamespace(json=False, human=False, plain=False)

    self.assertEqual(client.resolve_output_mode(args), "json")


class AuthHeaderTests(unittest.TestCase):
  def test_build_aip_auth_headers_reads_secret_file(self) -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
      secret_path = Path(tmpdir) / "api-key"
      secret_path.write_text("frontend-secret\n", encoding="utf-8")

      with mock.patch.dict(os.environ, {"AIPODCASTING_API_KEY_FILE": str(secret_path)}, clear=True):
        self.assertEqual(
          client.build_aip_auth_headers(),
          {"Authorization": "Bearer frontend-secret"},
        )

  def test_build_aip_auth_headers_uses_env_fallback(self) -> None:
    with mock.patch.dict(os.environ, {"AIPODCASTING_API_KEY": "frontend-env-secret"}, clear=True):
      self.assertEqual(
        client.build_aip_auth_headers(),
        {"Authorization": "Bearer frontend-env-secret"},
      )


class NormalizeEpisodeItemTests(unittest.TestCase):
  def test_normalize_episode_item_exposes_rich_summary_fields(self) -> None:
    item = {
      "source_id": "ep-123",
      "show": "TCR",
      "title": " Final title ",
      "thumbnailText": " Final thumbnail ",
      "needsGuestReview": True,
      "files": {
        "main": {
          "raw": " https://example.com/raw.mp3 ",
          "edited": " https://example.com/edited.mp3 ",
          "descript": " https://example.com/descript ",
        },
        "episode_outro": {"edited": " https://example.com/outro.mp3 "},
      },
      "submission": {
        "title": " Submission title ",
        "thumbnailText": " Draft thumbnail ",
        "showNotes": "<p>Hello <strong>world</strong>&nbsp;from notes</p>",
        "assetUrls": [" https://example.com/asset-1 ", "", None],
        "introTranscript": " Intro transcript ",
        "titleInspiration": " Big idea ",
        "editorInstructions": " Please cut the intro ",
        "customNewsletterDraftUrl": " https://ghost.example.com/ghost/#/editor/post/summary123 ",
        "guests": [
          {"name": " Ada Lovelace ", "email": " ada@example.com "},
          {"name": " "},
        ],
      },
      "production": {
        "editorNotes": " Tighten the opening. ",
        "priority": " high ",
        "editorName": " Sam ",
        "duration": 123.5,
        "tags": [" ai ", " podcast "],
      },
      "publishing": {
        "status": " To Publish ",
        "scheduledDate": "2026-04-01T10:00:00",
        "platforms": [
          {
            "name": " YouTube ",
            "url": " https://youtube.example/video ",
            "status": " queued ",
          }
        ],
        "currentJob": {
          "jobId": " job-1 ",
          "startedAt": "2026-03-31T09:00:00",
        },
      },
      "billing": {"consumed_hours": 2.5, "is_cross_post": False},
      "processed_assets": {
        "clips": [" clip-1 "],
        "transcript_html_url": " https://example.com/transcript.html ",
      },
      "deliverables": {
        "media": {
          "video": {"main": {"url": " https://example.com/video.mp4 "}},
        },
        "thumbnails": {
          "video": {
            "url": " https://example.com/video-thumb.png ",
            "design_source_url": " https://example.com/video-thumb.fig ",
            "variants": [
              {
                "url": " https://example.com/video-thumb-alt.png ",
                "source": " manual ",
              }
            ],
          },
          "audio": {"url": " https://example.com/audio-thumb.png "},
        },
        "links": {"newsletter": " https://example.com/newsletter "},
        "social": {
          "clip_ids": [" clip-1 "],
          "clip_urls": [" https://example.com/clips/1 "],
        },
      },
      "artwork": {
        "videoThumbnailUrl": " https://example.com/artwork-video.png ",
        "audioThumbnailUrl": " https://example.com/artwork-audio.png ",
      },
      "ads": {"midRollTimes": [" 00:10:00 "]},
      "shownotes": {"mainDescriptionHtml": "<p>Main description</p>"},
      "created_at": "2026-03-30T00:00:00",
      "updated_at": "2026-03-31T00:00:00",
    }

    normalized = client.normalize_episode_item(item)

    self.assertEqual(normalized["source_id"], "ep-123")
    self.assertEqual(normalized["status"], "To Publish")
    self.assertEqual(normalized["thumbnailText"], "Final thumbnail")
    self.assertEqual(normalized["submissionTitle"], "Submission title")
    self.assertTrue(normalized["needsGuestReview"])
    self.assertEqual(normalized["assetUrls"], ["https://example.com/asset-1"])
    self.assertEqual(
      normalized["copy"]["showNotesPreview"],
      "Hello world from notes",
    )
    self.assertEqual(normalized["copy"]["introTranscriptPreview"], "Intro transcript")
    self.assertEqual(normalized["copy"]["editorInstructionsPreview"], "Please cut the intro")
    self.assertEqual(
      normalized["customNewsletterDraftUrl"],
      "https://ghost.example.com/ghost/#/editor/post/summary123",
    )
    self.assertEqual(normalized["copy"]["editorNotesPreview"], "Tighten the opening.")
    self.assertEqual(normalized["production"]["priority"], "high")
    self.assertEqual(normalized["production"]["editorName"], "Sam")
    self.assertEqual(normalized["production"]["duration"], 123.5)
    self.assertEqual(normalized["production"]["tags"], ["ai", "podcast"])
    self.assertEqual(
      normalized["publishing"]["platforms"],
      [
        {
          "name": "YouTube",
          "url": "https://youtube.example/video",
          "status": "queued",
        }
      ],
    )
    self.assertEqual(
      normalized["publishing"]["currentJob"],
      {"jobId": "job-1", "startedAt": "2026-03-31T09:00:00"},
    )
    self.assertEqual(
      normalized["files"]["main"],
      {
        "raw": "https://example.com/raw.mp3",
        "edited": "https://example.com/edited.mp3",
        "descript": "https://example.com/descript",
      },
    )
    self.assertEqual(
      normalized["artwork"]["videoThumbnailUrl"],
      "https://example.com/artwork-video.png",
    )
    self.assertEqual(
      normalized["artwork"]["videoThumbnailVariants"],
      [
        {
          "url": "https://example.com/video-thumb-alt.png",
          "source": "manual",
        }
      ],
    )
    self.assertEqual(normalized["ads"], {"midRollTimes": ["00:10:00"]})
    self.assertEqual(
      normalized["shownotes"],
      {"mainDescriptionPreview": "Main description", "mainDescriptionLength": 16},
    )
    self.assertNotIn("billing", normalized)
    self.assertNotIn("raw_episode", normalized)

  def test_normalize_episode_item_include_raw_preserves_upstream_payload(self) -> None:
    item = {
      "source_id": "ep-raw",
      "show": "TCR",
      "title": "Raw episode",
      "submission": {},
      "production": {},
      "publishing": {"status": "To Publish"},
      "files": {"main": {"raw": "https://example.com/raw.mp3"}},
    }

    normalized = client.normalize_episode_item(item, include_raw=True)

    self.assertEqual(normalized["source_id"], "ep-raw")
    self.assertEqual(normalized["raw_episode"]["source_id"], "ep-raw")
    self.assertNotIn("billing", normalized["raw_episode"])


class RunListEpisodesTests(unittest.TestCase):
  def test_run_list_episodes_sorts_newest_first_before_limit(self) -> None:
    args = SimpleNamespace(
      publication_state="published",
      start_date="",
      end_date="",
      limit=1,
      include_raw=False,
      dry_run=False,
      timeout_seconds=30.0,
    )
    body = {
      "items": [
        {
          "source_id": "ep-older",
          "show": "TCR",
          "title": "Older published episode",
          "submission": {},
          "production": {},
          "publishing": {"status": "Published", "publishedDate": "2025-01-01T10:00:00"},
          "files": {"main": {"raw": "https://example.com/older.mp3"}},
        },
        {
          "source_id": "ep-newer",
          "show": "TCR",
          "title": "Newer published episode",
          "submission": {},
          "production": {},
          "publishing": {"status": "Published", "publishedDate": "2025-02-01T10:00:00"},
          "files": {"main": {"raw": "https://example.com/newer.mp3"}},
        },
      ]
    }

    with mock.patch.object(client, "request_json", return_value=body):
      data = client.run_list_episodes(args)

    self.assertEqual(data["count"], 1)
    self.assertEqual(data["matched_count"], 2)
    self.assertEqual(data["items"][0]["source_id"], "ep-newer")

  def test_run_list_episodes_filters_published_items(self) -> None:
    args = SimpleNamespace(
      publication_state="published",
      start_date="2026-01-01",
      end_date="2026-01-31",
      limit=50,
      include_raw=False,
      dry_run=False,
      timeout_seconds=30.0,
    )
    body = {
      "items": [
        {
          "source_id": "ep-published",
          "show": "TCR",
          "title": "Published episode",
          "submission": {},
          "production": {},
          "publishing": {"status": "Published"},
          "files": {"main": {"raw": "https://example.com/published.mp3"}},
        },
        {
          "source_id": "ep-unpublished",
          "show": "TCR",
          "title": "Unpublished episode",
          "submission": {},
          "production": {},
          "publishing": {"status": "To Publish"},
          "files": {"main": {"raw": "https://example.com/unpublished.mp3"}},
        },
      ]
    }

    with mock.patch.object(client, "request_json", return_value=body) as request_json:
      data = client.run_list_episodes(args)

    request_json.assert_called_once()
    self.assertEqual(request_json.call_args.args[0], "GET")
    self.assertIn("includePublished=true", request_json.call_args.args[1])
    self.assertIn("startDate=2026-01-01", request_json.call_args.args[1])
    self.assertIn("endDate=2026-01-31", request_json.call_args.args[1])
    self.assertEqual(data["count"], 1)
    self.assertEqual(data["matched_count"], 1)
    self.assertEqual(data["filters"]["publication_state"], "published")
    self.assertEqual(data["items"][0]["source_id"], "ep-published")

  def test_run_list_episodes_filters_unpublished_items(self) -> None:
    args = SimpleNamespace(
      publication_state="unpublished",
      start_date="",
      end_date="",
      limit=50,
      include_raw=False,
      dry_run=False,
      timeout_seconds=30.0,
    )
    body = {
      "items": [
        {
          "source_id": "ep-published",
          "show": "TCR",
          "title": "Published episode",
          "submission": {},
          "production": {},
          "publishing": {"status": "Published"},
          "files": {"main": {"raw": "https://example.com/published.mp3"}},
        },
        {
          "source_id": "ep-backlog",
          "show": "TCR",
          "title": "Backlog episode",
          "submission": {},
          "production": {},
          "publishing": {"status": "Backlog"},
          "files": {"main": {"raw": "https://example.com/backlog.mp3"}},
        },
      ]
    }

    with mock.patch.object(client, "request_json", return_value=body) as request_json:
      data = client.run_list_episodes(args)

    request_json.assert_called_once()
    self.assertIn("includePublished=false", request_json.call_args.args[1])
    self.assertEqual(data["count"], 1)
    self.assertEqual(data["matched_count"], 1)
    self.assertEqual(data["filters"]["publication_state"], "unpublished")
    self.assertEqual(data["items"][0]["source_id"], "ep-backlog")


class SubmitAndIntroDryRunTests(unittest.TestCase):
  def test_validate_submit_payload_rejects_main_mp3(self) -> None:
    with self.assertRaises(client.ClientError) as error_context:
      client.validate_submit_payload(
        {
          "show": "TCR",
          "mainEpisodeFile": "https://example.com/exported-audio.mp3?download=1",
        }
      )

    self.assertEqual(error_context.exception.code, "E_VALIDATION")
    self.assertIn("cannot be an MP3 link", error_context.exception.message)

  def test_normalize_intro_copy_payload_maps_newsletter_draft_alias(self) -> None:
    payload, upload_records = client.normalize_intro_copy_payload(
      {"ghostNewsletterDraftUrl": " https://ghost.example.com/p/custom-draft "},
      timeout_seconds=30.0,
      dry_run=True,
    )

    self.assertEqual(upload_records, [])
    self.assertEqual(
      payload["customNewsletterDraftUrl"],
      "https://ghost.example.com/p/custom-draft",
    )

  def test_run_submit_episode_dry_run_uses_expected_request_shape(self) -> None:
    args = SimpleNamespace(
      payload_file=str(ROOT / "references" / "submit-episode.example.json"),
      dry_run=True,
      timeout_seconds=30.0,
    )

    data = client.run_submit_episode(args)

    self.assertTrue(data["dry_run"])
    self.assertEqual(data["request"]["method"], "POST")
    self.assertEqual(data["request"]["url"], "https://app.aipodcast.ing/api/episodes/submit")
    self.assertEqual(data["request"]["payload"]["show"], "TCR")
    self.assertEqual(
      data["request"]["payload"]["files"]["main"]["raw"],
      "https://example.com/path/to/main-episode-file.mp4",
    )
    self.assertNotIn("mainEpisodeFile", data["request"]["payload"])
    self.assertEqual(
      len(data["request"]["payload"]["deliverables"]["thumbnails"]["options"]),
      2,
    )
    self.assertEqual(
      data["request"]["payload"]["customNewsletterDraftUrl"],
      "https://ghost.example.com/ghost/#/editor/post/submit123",
    )

  def test_run_update_intro_copy_dry_run_uses_expected_request_shape(self) -> None:
    args = SimpleNamespace(
      source_id="ep-123",
      payload_file=str(ROOT / "references" / "update-intro-copy-tcr.example.json"),
      dry_run=True,
      timeout_seconds=30.0,
    )

    data = client.run_update_intro_copy(args)

    self.assertTrue(data["dry_run"])
    self.assertEqual(data["request"]["method"], "PATCH")
    self.assertEqual(
      data["request"]["url"],
      "https://app.aipodcast.ing/api/episodes/ep-123/intro",
    )
    self.assertEqual(
      data["request"]["payload"]["title"],
      "Final publish-ready episode title",
    )
    self.assertEqual(
      data["request"]["payload"]["deliverables"]["thumbnails"]["video"]["url"],
      "https://example.com/path/to/video-thumbnail-16x9-primary.png",
    )
    self.assertEqual(
      data["request"]["payload"]["files"]["episode_outro"]["edited"],
      "https://example.com/path/to/outro-music.mp3",
    )
    self.assertEqual(
      data["request"]["payload"]["customNewsletterDraftUrl"],
      "https://ghost.example.com/ghost/#/editor/post/intro123",
    )


if __name__ == "__main__":
  unittest.main()
