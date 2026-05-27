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


def run_cli(args, *, env=None, input_text=None, check=True):
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
        INSERT INTO subjects VALUES (1, 'Fiber appointment update'), (2, 'Random newsletter');
        INSERT INTO addresses VALUES (1, 'telekom@example.com', 'Telekom'), (2, 'news@example.com', 'News');
        INSERT INTO mailboxes VALUES (1, 'Inbox', 'imap://example/INBOX', 2, 1);
        INSERT INTO messages VALUES (101, '<fiber@example>', 101, 1, 1, 1779900000, 1779900000, 1, 0, 0, 1234);
        INSERT INTO messages VALUES (102, '<news@example>', 102, 2, 2, 1779800000, 1779800000, 1, 1, 0, 900);
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
        Content-Type: text/plain; charset=utf-8

        The technician appointment is confirmed.
        Please be home.
        """).replace("\n", "\r\n").encode()
    (msg_dir / "101.emlx").write_bytes(str(len(raw)).encode() + b"\n" + raw + b"\n<?xml version='1.0'?><plist></plist>")
    return mail_root, db


class DobbyMailTests(unittest.TestCase):
    def test_fast_search_and_get(self):
        with tempfile.TemporaryDirectory() as d:
            mail_root, db = make_fixture(Path(d))
            proc, payload = run_cli(["search", "--query", "fiber", "--mail-root", str(mail_root), "--index-path", str(db), "--backend", "fast"])
            self.assertEqual(payload["status"], "ok")
            self.assertEqual(payload["data"]["backend"], "fast")
            self.assertEqual(len(payload["data"]["messages"]), 1)
            msg = payload["data"]["messages"][0]
            self.assertEqual(msg["id"], "fast:101")
            self.assertEqual(msg["subject"], "Fiber appointment update")

            proc, got = run_cli(["get", "--id", msg["id"], "--mail-root", str(mail_root), "--index-path", str(db), "--backend", "fast"])
            self.assertEqual(got["status"], "ok")
            self.assertIn("technician appointment", got["data"]["message"]["body_text"])
            self.assertEqual(got["data"]["message"]["attachments"], [])

    def test_mailboxes_fast(self):
        with tempfile.TemporaryDirectory() as d:
            mail_root, db = make_fixture(Path(d))
            _, payload = run_cli(["mailboxes", "--mail-root", str(mail_root), "--index-path", str(db), "--backend", "fast"])
            self.assertEqual(payload["data"]["mailboxes"][0]["name"], "Inbox")

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
                ["search", "--query", "anything", "--mail-root", str(Path(d) / "missing"), "--backend", "auto"],
                env={"DOBBY_MAIL_OSASCRIPT": str(mock)},
            )
            self.assertEqual(payload["status"], "ok")
            self.assertEqual(payload["data"]["backend"], "mail-app")
            self.assertTrue(payload["data"]["fallback_used"])
            self.assertIn("falling back", proc.stderr.lower())
            self.assertEqual(payload["data"]["warnings"][0]["code"], "E_MAIL_ROOT_NOT_FOUND")

    def test_draft_dry_run_and_send_requires_confirmation(self):
        _, payload = run_cli(["draft", "--to", "a@example.com", "--subject", "Hi", "--body", "Hello", "--dry-run"])
        self.assertEqual(payload["data"]["draft"]["state"], "would_create_unsent_draft")
        proc, err_payload = run_cli(["send", "--to", "a@example.com", "--subject", "Hi", "--body", "Hello", "--dry-run"], check=False)
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(err_payload["status"], "error")
        self.assertEqual(err_payload["error"]["code"], "E_SEND_CONFIRMATION_REQUIRED")


if __name__ == "__main__":
    unittest.main()
