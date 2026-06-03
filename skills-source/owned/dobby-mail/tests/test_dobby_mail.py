#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import base64
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import textwrap
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
    payload = json.loads(proc.stdout)
    return proc, payload


def make_fixture(tmp: Path) -> tuple[Path, Path]:
    mail_root = tmp / "Mail"
    vroot = mail_root / "V10"
    data = vroot / "MailData"
    data.mkdir(parents=True)
    db = data / "Envelope Index"
    conn = sqlite3.connect(db)
    conn.executescript(
        """
        CREATE TABLE subjects (ROWID INTEGER PRIMARY KEY, subject TEXT);
        CREATE TABLE addresses (ROWID INTEGER PRIMARY KEY, address TEXT, comment TEXT);
        CREATE TABLE mailboxes (ROWID INTEGER PRIMARY KEY, display_name TEXT, url TEXT, total_count INTEGER, unread_count INTEGER);
        CREATE TABLE messages (
          ROWID INTEGER PRIMARY KEY,
          message_id TEXT,
          document_id INTEGER,
          subject INTEGER,
          sender INTEGER,
          date_received INTEGER,
          date_sent INTEGER,
          mailbox INTEGER,
          read INTEGER,
          flags INTEGER,
          size INTEGER
        );
        INSERT INTO subjects VALUES (1, 'Fiber appointment update'), (2, 'Random newsletter'), (3, 'Other account alert');
        INSERT INTO addresses VALUES (1, 'telekom@example.com', 'Telekom'), (2, 'news@example.com', 'News'), (3, 'other@example.com', 'Other');
        INSERT INTO mailboxes VALUES (1, 'Inbox', 'imap://example/INBOX', 2, 1), (2, 'Inbox', 'imap://other/INBOX', 1, 0);
        INSERT INTO messages VALUES (101, '<fiber@example>', 101, 1, 1, 1779900000, 1779900000, 1, 0, 0, 1234);
        INSERT INTO messages VALUES (102, '<news@example>', 102, 2, 2, 1779800000, 1779800000, 1, 1, 0, 900);
        INSERT INTO messages VALUES (103, '<other@example>', 103, 3, 3, 1779700000, 1779700000, 2, 1, 0, 700);
        """
    )
    conn.commit(); conn.close()
    msg_dir = vroot / "account.mbox" / "INBOX.mbox" / "Messages"
    msg_dir.mkdir(parents=True)
    raw = textwrap.dedent("""\
        From: Telekom <telekom@example.com>
        To: Adi <adi@example.com>
        Subject: Fiber appointment update
        Message-ID: <fiber@example>
        Date: Wed, 27 May 2026 10:00:00 +0000
        MIME-Version: 1.0
        Content-Type: multipart/mixed; boundary="BOUNDARY"

        --BOUNDARY
        Content-Type: text/plain; charset=utf-8

        The technician appointment is confirmed.
        Please be home.

        --BOUNDARY
        Content-Type: text/plain; name="note.txt"
        Content-Disposition: attachment; filename="note.txt"

        Attachment body.
        --BOUNDARY--
        """).replace("\n", "\r\n").encode()
    (msg_dir / "101.emlx").write_bytes(str(len(raw)).encode() + b"\n" + raw + b"\n<?xml version='1.0'?><plist></plist>")
    return mail_root, db


def write_gmail_mock(path: Path, responses: list[dict]) -> Path:
    path.write_text(json.dumps({"responses": responses}, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def gmail_body(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode("utf-8")).decode("ascii").rstrip("=")


class DobbyMailTests(unittest.TestCase):
    def test_gmail_search_and_get_are_primary(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            mock = write_gmail_mock(
                tmp / "gmail-mock.json",
                [
                    {
                        "method": "GET",
                        "path_contains": "messages?q=fiber",
                        "response": {"messages": [{"id": "m1", "threadId": "t1"}]},
                    },
                    {
                        "method": "GET",
                        "path_contains": "messages/m1?format=metadata",
                        "response": {
                            "id": "m1",
                            "threadId": "t1",
                            "labelIds": ["INBOX", "UNREAD"],
                            "snippet": "The technician appointment is confirmed.",
                            "internalDate": "1800000000000",
                            "payload": {
                                "headers": [
                                    {"name": "From", "value": "Telekom <telekom@example.com>"},
                                    {"name": "To", "value": "Adi <adi@example.com>"},
                                    {"name": "Subject", "value": "Fiber appointment update"},
                                    {"name": "Message-ID", "value": "<fiber@example>"},
                                ]
                            },
                        },
                    },
                    {
                        "method": "GET",
                        "path_contains": "messages/m1?format=full",
                        "response": {
                            "id": "m1",
                            "threadId": "t1",
                            "labelIds": ["INBOX"],
                            "snippet": "The technician appointment is confirmed.",
                            "internalDate": "1800000000000",
                            "payload": {
                                "mimeType": "multipart/mixed",
                                "headers": [
                                    {"name": "From", "value": "Telekom <telekom@example.com>"},
                                    {"name": "To", "value": "Adi <adi@example.com>"},
                                    {"name": "Subject", "value": "Fiber appointment update"},
                                    {"name": "Message-ID", "value": "<fiber@example>"},
                                ],
                                "parts": [
                                    {"mimeType": "text/plain", "body": {"data": gmail_body("The technician appointment is confirmed.")}},
                                    {"mimeType": "text/plain", "filename": "note.txt", "body": {"attachmentId": "att1", "size": 16}},
                                ],
                            },
                        },
                    },
                    {
                        "method": "GET",
                        "path_contains": "messages/m1/attachments/att1",
                        "response": {"data": gmail_body("Attachment body.")},
                    },
                ],
            )
            env = {"DOBBY_MAIL_DEFAULT_ACCOUNT": "adi@example.com", "DOBBY_GMAIL_API_MOCK_FILE": str(mock)}
            _, payload = run_cli(["search", "--query", "fiber"], env=env)
            self.assertEqual(payload["status"], "ok")
            self.assertEqual(payload["data"]["backend"], "gmail-api")
            self.assertEqual(payload["data"]["messages"][0]["id"], "gmail-message:m1")
            self.assertEqual(payload["data"]["messages"][0]["subject"], "Fiber appointment update")

            _, got = run_cli(["get", "--id", "gmail-message:m1"], env=env)
            self.assertEqual(got["data"]["backend"], "gmail-api")
            self.assertIn("technician appointment", got["data"]["message"]["body_text"])
            self.assertEqual(got["data"]["message"]["attachments"][0]["attachment_id"], "att1")

            out = tmp / "attachments"
            _, att = run_cli(["attachments", "--id", "gmail-message:m1", "--out-dir", str(out)], env=env)
            self.assertEqual(att["data"]["backend"], "gmail-api")
            self.assertEqual(att["data"]["attachments"][0]["filename"], "note.txt")
            self.assertEqual(Path(att["data"]["attachments"][0]["path"]).read_text(), "Attachment body.")

    def test_gmail_history_baseline_and_incremental(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            mock = write_gmail_mock(
                tmp / "gmail-history-mock.json",
                [
                    {
                        "method": "GET",
                        "path": "profile",
                        "response": {"emailAddress": "adi@example.com", "historyId": "100", "messagesTotal": 10, "threadsTotal": 8},
                    },
                    {
                        "method": "GET",
                        "path_contains": "history?startHistoryId=100",
                        "response": {"historyId": "101", "history": [{"messagesAdded": [{"message": {"id": "m2", "threadId": "t2"}}]}]},
                    },
                ],
            )
            env = {"DOBBY_MAIL_DEFAULT_ACCOUNT": "adi@example.com", "DOBBY_GMAIL_API_MOCK_FILE": str(mock)}
            _, baseline = run_cli(["history"], env=env)
            self.assertEqual(baseline["data"]["mode"], "baseline")
            self.assertEqual(baseline["data"]["history_id"], "100")

            _, poll = run_cli(["history", "--since", "100"], env=env)
            self.assertEqual(poll["data"]["mode"], "incremental")
            self.assertEqual(poll["data"]["added_message_ids"], ["m2"])

    def test_fast_search_and_get(self):
        with tempfile.TemporaryDirectory() as d:
            mail_root, db = make_fixture(Path(d))
            proc, payload = run_cli(["search", "--all-accounts", "--query", "fiber", "--mail-root", str(mail_root), "--index-path", str(db), "--backend", "fast"])
            self.assertEqual(payload["status"], "ok")
            self.assertEqual(payload["data"]["backend"], "fast")
            self.assertEqual(len(payload["data"]["messages"]), 1)
            msg = payload["data"]["messages"][0]
            self.assertEqual(msg["id"], "fast:101")
            self.assertEqual(msg["subject"], "Fiber appointment update")

            proc, got = run_cli(["get", "--all-accounts", "--id", msg["id"], "--mail-root", str(mail_root), "--index-path", str(db), "--backend", "fast"])
            self.assertEqual(got["status"], "ok")
            self.assertIn("technician appointment", got["data"]["message"]["body_text"])
            self.assertEqual(got["data"]["message"]["attachments"][0]["filename"], "note.txt")

    def test_mailboxes_fast(self):
        with tempfile.TemporaryDirectory() as d:
            mail_root, db = make_fixture(Path(d))
            _, payload = run_cli(["mailboxes", "--all-accounts", "--mail-root", str(mail_root), "--index-path", str(db), "--backend", "fast"])
            self.assertEqual(payload["data"]["mailboxes"][0]["name"], "Inbox")

    def test_default_account_required_and_filters_fast_reads(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            mail_root, db = make_fixture(tmp)
            proc, err = run_cli(
                ["search", "--query", "fiber", "--mail-root", str(mail_root), "--index-path", str(db), "--backend", "fast"],
                env={"DOBBY_MAIL_DEFAULT_ACCOUNT": ""},
                cwd=d,
                check=False,
            )
            self.assertNotEqual(proc.returncode, 0)
            self.assertEqual(err["error"]["code"], "E_DEFAULT_ACCOUNT_REQUIRED")

            _, payload = run_cli(
                ["recent", "--limit", "10", "--mail-root", str(mail_root), "--index-path", str(db), "--backend", "fast"],
                env={"DOBBY_MAIL_DEFAULT_ACCOUNT": "example"},
                cwd=d,
            )
            subjects = {msg["subject"] for msg in payload["data"]["messages"]}
            self.assertIn("Fiber appointment update", subjects)
            self.assertNotIn("Other account alert", subjects)

    def test_explicit_legacy_mail_app_backend_warning(self):
        with tempfile.TemporaryDirectory() as d:
            mock = Path(d) / "osascript-mock"
            mock.write_text(
                "#!/usr/bin/env python3\n"
                "import json\n"
                "print(json.dumps({'messages':[{'id':'mail:1','backend':'mail-app','subject':'Fallback result','sender':'a@example.com'}], 'scope':'inbox'}))\n"
            )
            mock.chmod(0o755)
            proc, payload = run_cli(
                ["search", "--all-accounts", "--query", "anything", "--mail-root", str(Path(d) / "missing"), "--backend", "mail-app"],
                env={"DOBBY_MAIL_OSASCRIPT": str(mock)},
            )
            self.assertEqual(payload["status"], "ok")
            self.assertEqual(payload["data"]["backend"], "mail-app")
            self.assertFalse(payload["data"]["fallback_used"])
            self.assertIn("legacy apple", proc.stderr.lower())
            self.assertEqual(payload["data"]["warnings"][0]["code"], "W_LEGACY_APPLE_BACKEND")

    def test_draft_dry_run_and_send_requires_confirmation(self):
        _, payload = run_cli(["draft", "--to", "a@example.com", "--subject", "Hi", "--body", "Hello", "--dry-run"], env={"DOBBY_MAIL_DEFAULT_FROM": "default@example.com"})
        self.assertEqual(payload["data"]["draft"]["state"], "would_create_unsent_draft")
        self.assertFalse(payload["data"]["draft"]["visible"])
        proc, err_payload = run_cli(["send", "--to", "a@example.com", "--subject", "Hi", "--body", "Hello", "--dry-run"], env={"DOBBY_MAIL_DEFAULT_FROM": "default@example.com"}, check=False)
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(err_payload["status"], "error")
        self.assertEqual(err_payload["error"]["code"], "E_SEND_CONFIRMATION_REQUIRED")

    def test_gmail_write_backend_is_explicit_and_does_not_need_auth_for_dry_run(self):
        env = {
            "DOBBY_MAIL_DEFAULT_ACCOUNT": "writer@example.com",
            "DOBBY_MAIL_DEFAULT_FROM": "default@example.com",
        }
        _, payload = run_cli(["draft", "--to", "a@example.com", "--subject", "Hi", "--body", "Hello", "--write-backend", "gmail-api", "--dry-run"], env=env)
        self.assertEqual(payload["data"]["backend"], "gmail-api")
        self.assertEqual(payload["data"]["gmail_account"], "writer@example.com")
        self.assertEqual(payload["data"]["draft"]["sender"], "default@example.com")

        with tempfile.TemporaryDirectory() as d:
            proc, err = run_cli(
                ["draft", "--to", "a@example.com", "--subject", "Hi", "--body", "Hello", "--write-backend", "gmail-api"],
                env={**env, "DOBBY_GMAIL_OAUTH_CLIENT_FILE": str(Path(d) / "missing-client.json")},
                check=False,
            )
            self.assertEqual(proc.returncode, 3)
            self.assertEqual(err["error"]["code"], "E_GMAIL_CLIENT_SECRET_MISSING")

    def test_gmail_auth_is_not_allowed_with_no_input(self):
        proc, payload = run_cli(["gmail-auth", "--account", "writer@example.com", "--no-input"], check=False)
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(payload["error"]["code"], "E_GMAIL_AUTH_INTERACTIVE")

    def test_no_open_or_show_draft_interface(self):
        proc = subprocess.run([str(CLI), "open", "--help"], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        self.assertNotEqual(proc.returncode, 0)

        draft_help = subprocess.run([str(CLI), "draft", "--help"], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        self.assertEqual(draft_help.returncode, 0)
        self.assertNotIn("--show", draft_help.stdout)
        self.assertNotIn("--hidden", draft_help.stdout)


    def test_default_sender_from_env_and_workspace_dotenv(self):
        _, payload = run_cli(["draft", "--to", "a@example.com", "--subject", "Hi", "--body", "Hello", "--dry-run"], env={"DOBBY_MAIL_DEFAULT_FROM": "default@example.com"})
        self.assertEqual(payload["data"]["draft"]["sender"], "default@example.com")

        _, explicit = run_cli(["draft", "--to", "a@example.com", "--subject", "Hi", "--body", "Hello", "--sender", "explicit@example.com", "--dry-run"], env={"DOBBY_MAIL_DEFAULT_FROM": "default@example.com"})
        self.assertEqual(explicit["data"]["draft"]["sender"], "explicit@example.com")

        with tempfile.TemporaryDirectory() as d:
            Path(d, ".env").write_text("DOBBY_MAIL_DEFAULT_FROM=workspace@example.com\n")
            _, dotenv_payload = run_cli(["draft", "--to", "a@example.com", "--subject", "Hi", "--body", "Hello", "--dry-run"], env={"DOBBY_MAIL_DEFAULT_FROM": ""}, cwd=d)
            self.assertEqual(dotenv_payload["data"]["draft"]["sender"], "workspace@example.com")

    def test_default_sender_required_without_fallback(self):
        with tempfile.TemporaryDirectory() as d:
            proc, payload = run_cli(
                ["draft", "--to", "a@example.com", "--subject", "Hi", "--body", "Hello", "--dry-run"],
                env={"DOBBY_MAIL_DEFAULT_FROM": ""},
                cwd=d,
                check=False,
            )
            self.assertNotEqual(proc.returncode, 0)
            self.assertEqual(payload["error"]["code"], "E_DEFAULT_FROM_REQUIRED")

    def test_export_and_attachments(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            mail_root, db = make_fixture(tmp)
            out = tmp / "out"
            _, payload = run_cli(["export", "--all-accounts", "--id", "fast:101", "--out-dir", str(out), "--raw", "--mail-root", str(mail_root), "--index-path", str(db), "--backend", "fast"])
            self.assertEqual(payload["status"], "ok")
            kinds = {item["kind"] for item in payload["data"]["written"]}
            self.assertTrue({"metadata_json", "body_text", "raw_eml"}.issubset(kinds))
            self.assertTrue((out / "message-101.txt").exists())
            _, att = run_cli(["attachments", "--all-accounts", "--id", "fast:101", "--out-dir", str(out / "att"), "--mail-root", str(mail_root), "--index-path", str(db), "--backend", "fast"])
            self.assertEqual(att["status"], "ok")
            self.assertEqual(att["data"]["attachments"][0]["filename"], "note.txt")
            self.assertTrue(Path(att["data"]["attachments"][0]["path"]).exists())

    def test_mutation_commands_require_confirmation_and_dry_run(self):
        proc, payload = run_cli(["mark-read", "--id", "mail:1"], check=False)
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(payload["error"]["code"], "E_MARK_CONFIRMATION_REQUIRED")
        _, ok = run_cli(["mark-read", "--id", "mail:1", "--unread", "--confirm-mark", "--dry-run"])
        self.assertEqual(ok["data"]["changed"]["read_status"], False)
        proc, flag_err = run_cli(["flag", "--id", "mail:1"], check=False)
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(flag_err["error"]["code"], "E_FLAG_CONFIRMATION_REQUIRED")

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
