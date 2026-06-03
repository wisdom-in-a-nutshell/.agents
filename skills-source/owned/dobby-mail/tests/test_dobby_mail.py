#!/usr/bin/env python3
from __future__ import annotations

import base64
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "dobby-mail"


def run_cli(args, *, env=None, input_text=None, check=True, cwd=None):
    merged = os.environ.copy()
    if env:
        merged.update(env)
    proc = subprocess.run(
        [str(CLI), *args],
        input=input_text,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=merged,
        cwd=cwd,
        check=False,
    )
    if check and proc.returncode != 0:
        raise AssertionError(f"command failed {proc.returncode}\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}")
    payload = json.loads(proc.stdout) if proc.stdout.strip().startswith("{") else {}
    return proc, payload


def write_gmail_mock(path: Path, responses: list[dict]) -> Path:
    path.write_text(json.dumps({"responses": responses}, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def b64url_text(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode("utf-8")).decode("ascii").rstrip("=")


def b64url_bytes(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def metadata_response(message_id: str = "m1", *, subject: str = "Fiber appointment update") -> dict:
    return {
        "id": message_id,
        "threadId": "t1",
        "labelIds": ["INBOX", "UNREAD"],
        "snippet": "The technician appointment is confirmed.",
        "internalDate": "1800000000000",
        "historyId": "90",
        "payload": {
            "headers": [
                {"name": "From", "value": "Telekom <telekom@example.com>"},
                {"name": "To", "value": "Adi <adi@example.com>"},
                {"name": "Subject", "value": subject},
                {"name": "Date", "value": "Wed, 27 May 2026 10:00:00 +0000"},
                {"name": "Message-ID", "value": "<fiber@example>"},
            ]
        },
    }


def full_response(message_id: str = "m1", *, subject: str = "Fiber appointment update") -> dict:
    return {
        "id": message_id,
        "threadId": "t1",
        "labelIds": ["INBOX"],
        "snippet": "The technician appointment is confirmed.",
        "internalDate": "1800000000000",
        "historyId": "91",
        "sizeEstimate": 2048,
        "payload": {
            "mimeType": "multipart/mixed",
            "headers": [
                {"name": "From", "value": "Telekom <telekom@example.com>"},
                {"name": "To", "value": "Adi <adi@example.com>"},
                {"name": "Subject", "value": subject},
                {"name": "Date", "value": "Wed, 27 May 2026 10:00:00 +0000"},
                {"name": "Message-ID", "value": "<fiber@example>"},
            ],
            "parts": [
                {"mimeType": "text/plain", "body": {"data": b64url_text("The technician appointment is confirmed.\nPlease be home.")}},
                {"mimeType": "text/plain", "filename": "note.txt", "body": {"attachmentId": "att1", "size": 16}},
            ],
        },
    }


def gmail_env(tmp: Path, mock: Path, *, account: str = "adi@example.com") -> dict[str, str]:
    return {
        "DOBBY_MAIL_DEFAULT_ACCOUNT": account,
        "DOBBY_MAIL_DEFAULT_FROM": account,
        "DOBBY_GMAIL_API_MOCK_FILE": str(mock),
        "DOBBY_MAIL_CACHE_PATH": str(tmp / "cache.sqlite"),
        "DOBBY_GMAIL_OAUTH_CLIENT_FILE": str(tmp / "missing-client.json"),
    }


class DobbyMailTests(unittest.TestCase):
    def test_gmail_search_get_and_cache_hit(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            mock = write_gmail_mock(
                tmp / "gmail-mock.json",
                [
                    {"method": "GET", "path_contains": "messages?q=fiber", "response": {"messages": [{"id": "m1", "threadId": "t1"}]}},
                    {"method": "GET", "path_contains": "messages/m1?format=metadata", "response": metadata_response()},
                    {"method": "GET", "path_contains": "messages/m1?format=full", "response": full_response()},
                ],
            )
            env = gmail_env(tmp, mock)

            _, search = run_cli(["search", "--query", "fiber"], env=env)
            self.assertEqual(search["status"], "ok")
            self.assertEqual(search["data"]["backend"], "gmail-api")
            self.assertEqual(search["data"]["messages"][0]["id"], "gmail-message:m1")
            self.assertEqual(search["data"]["messages"][0]["subject"], "Fiber appointment update")
            self.assertTrue(Path(search["data"]["cache"]["path"]).exists())

            _, got = run_cli(["get", "--id", "gmail-message:m1"], env=env)
            self.assertEqual(got["data"]["backend"], "gmail-api")
            self.assertIn("technician appointment", got["data"]["message"]["body_text"])
            self.assertEqual(got["data"]["message"]["attachments"][0]["attachment_id"], "att1")
            self.assertFalse(got["data"]["cache"]["hit"])

            # Prove the second body read is served from SQLite, not Gmail.
            write_gmail_mock(tmp / "gmail-mock.json", [])
            _, cached = run_cli(["get", "--id", "m1"], env=env)
            self.assertTrue(cached["data"]["cache"]["hit"])
            self.assertTrue(cached["data"]["message"]["cache"]["hit"])
            self.assertIn("Please be home", cached["data"]["message"]["body_text"])

            proc, refresh = run_cli(["get", "--id", "m1", "--refresh"], env=env, check=False)
            self.assertEqual(proc.returncode, 4)
            self.assertEqual(refresh["error"]["code"], "E_GMAIL_API_MOCK_MISS")

    def test_gmail_history_and_sync_state_cache(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            mock = write_gmail_mock(
                tmp / "gmail-history-mock.json",
                [
                    {"method": "GET", "path": "profile", "response": {"emailAddress": "adi@example.com", "historyId": "100", "messagesTotal": 10, "threadsTotal": 8}},
                    {"method": "GET", "path_contains": "history?startHistoryId=100", "response": {"historyId": "101", "history": [{"messagesAdded": [{"message": {"id": "m2", "threadId": "t2"}}]}]}},
                    {"method": "GET", "path_contains": "messages/m2?format=metadata", "response": metadata_response("m2", subject="New inbound item")},
                ],
            )
            env = gmail_env(tmp, mock)

            _, baseline = run_cli(["history"], env=env)
            self.assertEqual(baseline["data"]["mode"], "baseline")
            self.assertEqual(baseline["data"]["history_id"], "100")

            _, status = run_cli(["cache-status"], env=env)
            self.assertEqual(status["data"]["cache"]["history_id"], "100")
            self.assertEqual(status["data"]["cache"]["cached_messages"], 0)

            _, poll = run_cli(["history", "--since", "100", "--fetch"], env=env)
            self.assertEqual(poll["data"]["mode"], "incremental")
            self.assertEqual(poll["data"]["added_message_ids"], ["m2"])
            self.assertEqual(poll["data"]["messages"][0]["subject"], "New inbound item")

            _, updated = run_cli(["cache-status"], env=env)
            self.assertEqual(updated["data"]["cache"]["history_id"], "101")
            self.assertEqual(updated["data"]["cache"]["cached_messages"], 1)
            self.assertEqual(updated["data"]["cache"]["email_address"], "adi@example.com")

    def test_sync_requires_cache_and_can_create_baseline(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            mock = write_gmail_mock(tmp / "gmail-sync-mock.json", [{"method": "GET", "path": "profile", "response": {"emailAddress": "adi@example.com", "historyId": "200", "messagesTotal": 11, "threadsTotal": 9}}])
            env = gmail_env(tmp, mock)

            proc, no_cache = run_cli(["sync", "--no-cache"], env=env, check=False)
            self.assertEqual(proc.returncode, 2)
            self.assertEqual(no_cache["error"]["code"], "E_CACHE_REQUIRED")

            _, sync = run_cli(["sync", "--reset"], env=env)
            self.assertEqual(sync["data"]["state"], "baseline_created")
            self.assertEqual(sync["data"]["history_id"], "200")

    def test_export_and_attachments_are_gmail_only(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            raw_eml = b"From: Telekom <telekom@example.com>\r\nSubject: Fiber appointment update\r\n\r\nBody\r\n"
            mock = write_gmail_mock(
                tmp / "gmail-export-mock.json",
                [
                    {"method": "GET", "path_contains": "messages/m1?format=full", "response": full_response()},
                    {"method": "GET", "path_contains": "messages/m1?format=raw", "response": {"id": "m1", "raw": b64url_bytes(raw_eml)}},
                    {"method": "GET", "path_contains": "messages/m1/attachments/att1", "response": {"data": b64url_text("Attachment body.")}},
                ],
            )
            env = gmail_env(tmp, mock)
            out = tmp / "out"

            _, exported = run_cli(["export", "--id", "gmail-message:m1", "--out-dir", str(out), "--raw"], env=env)
            self.assertEqual(exported["data"]["backend"], "gmail-api")
            kinds = {item["kind"] for item in exported["data"]["written"]}
            self.assertTrue({"metadata_json", "body_text", "raw_eml"}.issubset(kinds))
            self.assertEqual((out / "message-m1.eml").read_bytes(), raw_eml)

            _, att = run_cli(["attachments", "--id", "m1", "--out-dir", str(out / "att")], env=env)
            self.assertEqual(att["data"]["attachments"][0]["filename"], "note.txt")
            self.assertEqual(Path(att["data"]["attachments"][0]["path"]).read_text(), "Attachment body.")

    def test_draft_dry_run_and_send_requires_confirmation(self):
        env = {"DOBBY_MAIL_DEFAULT_ACCOUNT": "writer@example.com", "DOBBY_MAIL_DEFAULT_FROM": "default@example.com"}
        _, draft = run_cli(["draft", "--to", "a@example.com", "--subject", "Hi", "--body", "Hello", "--dry-run"], env=env)
        self.assertEqual(draft["data"]["draft"]["state"], "would_create_unsent_draft")
        self.assertFalse(draft["data"]["draft"]["visible"])
        self.assertEqual(draft["data"]["gmail_account"], "writer@example.com")

        proc, err_payload = run_cli(["send", "--to", "a@example.com", "--subject", "Hi", "--body", "Hello", "--dry-run"], env=env, check=False)
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(err_payload["error"]["code"], "E_SEND_CONFIRMATION_REQUIRED")

        _, send = run_cli(["send", "--to", "a@example.com", "--subject", "Hi", "--body", "Hello", "--confirm-send", "--dry-run"], env=env)
        self.assertEqual(send["data"]["sent"]["state"], "would_send")

    def test_draft_create_needs_auth_but_dry_run_does_not(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            env = {
                "DOBBY_MAIL_DEFAULT_ACCOUNT": "writer@example.com",
                "DOBBY_MAIL_DEFAULT_FROM": "default@example.com",
                "DOBBY_GMAIL_OAUTH_CLIENT_FILE": str(tmp / "missing-client.json"),
            }
            _, dry = run_cli(["draft", "--to", "a@example.com", "--subject", "Hi", "--body", "Hello", "--dry-run"], env=env)
            self.assertEqual(dry["data"]["backend"], "gmail-api")

            proc, err = run_cli(["draft", "--to", "a@example.com", "--subject", "Hi", "--body", "Hello"], env=env, check=False)
            self.assertEqual(proc.returncode, 3)
            self.assertEqual(err["error"]["code"], "E_GMAIL_CLIENT_SECRET_MISSING")

    def test_gmail_auth_is_not_allowed_with_no_input(self):
        proc, payload = run_cli(["gmail-auth", "--account", "writer@example.com", "--no-input"], check=False)
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(payload["error"]["code"], "E_GMAIL_AUTH_INTERACTIVE")

    def test_no_apple_or_show_draft_interface(self):
        proc, payload = run_cli(["mailboxes"], check=False)
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(payload["error"]["code"], "E_INVALID_USAGE")

        proc, payload = run_cli(["search", "--query", "fiber", "--backend", "fast"], env={"DOBBY_MAIL_DEFAULT_ACCOUNT": "adi@example.com"}, check=False)
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(payload["error"]["code"], "E_INVALID_USAGE")

        draft_help = subprocess.run([str(CLI), "draft", "--help"], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        self.assertEqual(draft_help.returncode, 0)
        self.assertNotIn("--show", draft_help.stdout)
        self.assertNotIn("--hidden", draft_help.stdout)
        self.assertNotIn("--write-backend", draft_help.stdout)

    def test_default_sender_from_env_and_workspace_dotenv(self):
        env = {"DOBBY_MAIL_DEFAULT_ACCOUNT": "writer@example.com", "DOBBY_MAIL_DEFAULT_FROM": "default@example.com"}
        _, payload = run_cli(["draft", "--to", "a@example.com", "--subject", "Hi", "--body", "Hello", "--dry-run"], env=env)
        self.assertEqual(payload["data"]["draft"]["sender"], "default@example.com")

        _, explicit = run_cli(["draft", "--to", "a@example.com", "--subject", "Hi", "--body", "Hello", "--sender", "explicit@example.com", "--dry-run"], env=env)
        self.assertEqual(explicit["data"]["draft"]["sender"], "explicit@example.com")

        with tempfile.TemporaryDirectory() as d:
            Path(d, ".env").write_text("DOBBY_MAIL_DEFAULT_ACCOUNT=workspace@example.com\nDOBBY_MAIL_DEFAULT_FROM=workspace@example.com\n")
            _, dotenv_payload = run_cli(["draft", "--to", "a@example.com", "--subject", "Hi", "--body", "Hello", "--dry-run"], env={"DOBBY_MAIL_DEFAULT_ACCOUNT": "", "DOBBY_MAIL_DEFAULT_FROM": ""}, cwd=d)
            self.assertEqual(dotenv_payload["data"]["gmail_account"], "workspace@example.com")
            self.assertEqual(dotenv_payload["data"]["draft"]["sender"], "workspace@example.com")

    def test_default_sender_required_without_fallback(self):
        with tempfile.TemporaryDirectory() as d:
            proc, payload = run_cli(
                ["draft", "--to", "a@example.com", "--subject", "Hi", "--body", "Hello", "--dry-run"],
                env={"DOBBY_MAIL_DEFAULT_ACCOUNT": "writer@example.com", "DOBBY_MAIL_DEFAULT_FROM": ""},
                cwd=d,
                check=False,
            )
            self.assertNotEqual(proc.returncode, 0)
            self.assertEqual(payload["error"]["code"], "E_DEFAULT_FROM_REQUIRED")

    def test_gmail_mutation_commands_are_confirmed_and_dry_run_without_auth(self):
        env = {"DOBBY_MAIL_DEFAULT_ACCOUNT": "writer@example.com"}
        proc, payload = run_cli(["gmail-trash", "--gmail-id", "abc123"], env=env, check=False)
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(payload["error"]["code"], "E_GMAIL_MUTATION_CONFIRMATION_REQUIRED")

        _, archive = run_cli(["gmail-archive", "--gmail-id", "abc123", "--confirm-mutate", "--dry-run"], env=env)
        self.assertEqual(archive["data"]["backend"], "gmail-api")
        self.assertEqual(archive["data"]["gmail_account"], "writer@example.com")
        self.assertEqual(archive["data"]["target"]["gmail_id"], "abc123")
        self.assertEqual(archive["data"]["changed"]["remove_label_ids"], ["INBOX"])
        self.assertEqual(archive["data"]["changed"]["state"], "would_archive")

        _, spam = run_cli(["gmail-spam", "--id", "gmail-message:def456", "--confirm-mutate", "--dry-run"], env=env)
        self.assertEqual(spam["data"]["target"]["gmail_id"], "def456")
        self.assertEqual(spam["data"]["changed"]["add_label_ids"], ["SPAM"])
        self.assertEqual(spam["data"]["changed"]["remove_label_ids"], ["INBOX"])

        _, unread = run_cli(["gmail-mark-read", "--gmail-id", "abc123", "--unread", "--confirm-mutate", "--dry-run"], env=env)
        self.assertEqual(unread["data"]["changed"]["add_label_ids"], ["UNREAD"])

    def test_gmail_filters_are_safe_and_explicit(self):
        env = {"DOBBY_MAIL_DEFAULT_ACCOUNT": "writer@example.com"}
        proc, missing = run_cli(["gmail-filter", "--from", "noise@example.com", "--action", "trash", "--dry-run"], env=env, check=False)
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(missing["error"]["code"], "E_GMAIL_MUTATION_CONFIRMATION_REQUIRED")

        _, payload = run_cli(
            ["gmail-filter", "--from", "noise@example.com", "--action", "trash", "--confirm-mutate", "--dry-run"],
            env=env,
        )
        self.assertEqual(payload["data"]["filter"]["criteria"]["from"], "noise@example.com")
        self.assertEqual(payload["data"]["filter"]["action"]["addLabelIds"], ["TRASH"])
        self.assertEqual(payload["data"]["filter"]["action"]["removeLabelIds"], ["INBOX"])
        self.assertFalse(payload["data"]["applies_to_existing_messages"])

        _, block = run_cli(["gmail-block-sender", "--from", "noise@example.com", "--confirm-mutate", "--dry-run"], env=env)
        self.assertEqual(block["data"]["action"], "created_sender_trash_filter")
        self.assertEqual(block["data"]["filter"]["action"]["addLabelIds"], ["TRASH"])


if __name__ == "__main__":
    unittest.main()
