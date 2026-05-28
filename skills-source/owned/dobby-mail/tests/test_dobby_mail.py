#!/usr/bin/env python3
from __future__ import annotations

import json
import os
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


class DobbyMailTests(unittest.TestCase):
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

    def test_explicit_fallback_warning(self):
        with tempfile.TemporaryDirectory() as d:
            mock = Path(d) / "osascript-mock"
            mock.write_text(
                "#!/usr/bin/env python3\n"
                "import json\n"
                "print(json.dumps({'messages':[{'id':'mail:1','backend':'mail-app','subject':'Fallback result','sender':'a@example.com'}], 'scope':'inbox'}))\n"
            )
            mock.chmod(0o755)
            proc, payload = run_cli(
                ["search", "--all-accounts", "--query", "anything", "--mail-root", str(Path(d) / "missing"), "--backend", "auto"],
                env={"DOBBY_MAIL_OSASCRIPT": str(mock)},
            )
            self.assertEqual(payload["status"], "ok")
            self.assertEqual(payload["data"]["backend"], "mail-app")
            self.assertTrue(payload["data"]["fallback_used"])
            self.assertIn("falling back", proc.stderr.lower())
            self.assertEqual(payload["data"]["warnings"][0]["code"], "E_MAIL_ROOT_NOT_FOUND")

    def test_draft_dry_run_and_send_requires_confirmation(self):
        _, payload = run_cli(["draft", "--to", "a@example.com", "--subject", "Hi", "--body", "Hello", "--dry-run"], env={"DOBBY_MAIL_DEFAULT_FROM": "default@example.com"})
        self.assertEqual(payload["data"]["draft"]["state"], "would_create_unsent_draft")
        proc, err_payload = run_cli(["send", "--to", "a@example.com", "--subject", "Hi", "--body", "Hello", "--dry-run"], env={"DOBBY_MAIL_DEFAULT_FROM": "default@example.com"}, check=False)
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(err_payload["status"], "error")
        self.assertEqual(err_payload["error"]["code"], "E_SEND_CONFIRMATION_REQUIRED")


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


if __name__ == "__main__":
    unittest.main()
