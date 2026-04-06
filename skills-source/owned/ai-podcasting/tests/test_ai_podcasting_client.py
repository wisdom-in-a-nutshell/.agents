import importlib.util
import sys
from pathlib import Path
import unittest


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


if __name__ == "__main__":
  unittest.main()
