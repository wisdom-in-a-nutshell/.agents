import contextlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

CLI_PATH = Path(__file__).resolve().parent.parent / 'cli.py'
SPEC = importlib.util.spec_from_file_location('reddit_cli_under_test', CLI_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f'Unable to load CLI module from {CLI_PATH}')
cli = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cli)


class RedditCommentCliTests(unittest.TestCase):
    def run_main(self, argv):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            exit_code = cli.main(argv)
        return exit_code, stdout.getvalue(), stderr.getvalue()

    def test_comment_dry_run_with_post_url_and_text_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            text_path = Path(tmpdir) / 'comment.md'
            text_path.write_text('hello from file\n')
            exit_code, stdout, stderr = self.run_main([
                'comment',
                '--post-url', 'https://reddit.com/r/test/comments/abc123/example/',
                '--text-file', str(text_path),
                '--dry-run',
            ])

        self.assertEqual(exit_code, 0)
        self.assertEqual(stderr, '')
        envelope = json.loads(stdout)
        self.assertEqual(envelope['status'], 'ok')
        self.assertEqual(envelope['command'], 'reddit comment')
        self.assertTrue(envelope['data']['dry_run'])
        self.assertEqual(
            envelope['data']['payload']['post_url'],
            'https://reddit.com/r/test/comments/abc123/example/',
        )
        self.assertEqual(envelope['data']['payload']['text'], 'hello from file')
        self.assertEqual(envelope['schema_version'], '1.0')

    def test_comment_dry_run_with_post_id_and_inline_text(self):
        exit_code, stdout, stderr = self.run_main([
            'comment',
            '--post-id', 'abc123',
            '--text', 'inline comment',
            '--dry-run',
        ])

        self.assertEqual(exit_code, 0)
        self.assertEqual(stderr, '')
        envelope = json.loads(stdout)
        self.assertEqual(envelope['data']['payload']['post_id'], 'abc123')
        self.assertEqual(envelope['data']['payload']['text'], 'inline comment')
        self.assertIsNone(envelope['data']['payload']['post_url'])

    def test_comment_dry_run_with_comment_url(self):
        exit_code, stdout, stderr = self.run_main([
            'comment',
            '--comment-url', 'https://reddit.com/r/test/comments/abc123/example/def456/',
            '--text', 'reply to a comment',
            '--dry-run',
        ])

        self.assertEqual(exit_code, 0)
        self.assertEqual(stderr, '')
        envelope = json.loads(stdout)
        self.assertEqual(
            envelope['data']['payload']['comment_url'],
            'https://reddit.com/r/test/comments/abc123/example/def456/',
        )
        self.assertEqual(envelope['data']['payload']['text'], 'reply to a comment')

    def test_comment_requires_text_or_text_file(self):
        exit_code, stdout, stderr = self.run_main([
            'comment',
            '--post-id', 'abc123',
        ])

        self.assertEqual(exit_code, 2)
        self.assertEqual(stdout, '')
        error = json.loads(stderr)
        self.assertEqual(error['status'], 'error')
        self.assertEqual(error['error']['code'], 'E_INVALID_INPUT')

    def test_comment_requires_post_target(self):
        exit_code, stdout, stderr = self.run_main([
            'comment',
            '--text', 'hello',
        ])

        self.assertEqual(exit_code, 2)
        self.assertEqual(stdout, '')
        error = json.loads(stderr)
        self.assertEqual(error['status'], 'error')
        self.assertEqual(error['error']['code'], 'E_INVALID_INPUT')

    def test_comment_live_success_uses_client_and_returns_comment_url(self):
        fake_client = mock.Mock()
        fake_client.add_comment.return_value = 'https://reddit.com/r/test/comments/abc123/example/def456/'
        fake_client_cls = mock.Mock(return_value=fake_client)

        with mock.patch.object(cli, 'seed_env_from_file'), \
             mock.patch.object(cli, 'require_runtime_dependencies'), \
             mock.patch.object(cli, '_load_praw_client', return_value=fake_client_cls):
            exit_code, stdout, stderr = self.run_main([
                'comment',
                '--post-id', 'abc123',
                '--text', 'hello live',
            ])

        self.assertEqual(exit_code, 0)
        self.assertEqual(stderr, '')
        fake_client.add_comment.assert_called_once_with(
            text='hello live',
            post_url=None,
            post_id='abc123',
            comment_url=None,
            comment_id=None,
        )
        envelope = json.loads(stdout)
        self.assertEqual(
            envelope['data']['comment']['url'],
            'https://reddit.com/r/test/comments/abc123/example/def456/',
        )

    def test_comment_live_success_can_reply_to_comment_id(self):
        fake_client = mock.Mock()
        fake_client.add_comment.return_value = 'https://reddit.com/r/test/comments/abc123/example/ghi789/'
        fake_client_cls = mock.Mock(return_value=fake_client)

        with mock.patch.object(cli, 'seed_env_from_file'), \
             mock.patch.object(cli, 'require_runtime_dependencies'), \
             mock.patch.object(cli, '_load_praw_client', return_value=fake_client_cls):
            exit_code, stdout, stderr = self.run_main([
                'comment',
                '--comment-id', 'def456',
                '--text', 'thanks for watching',
            ])

        self.assertEqual(exit_code, 0)
        self.assertEqual(stderr, '')
        fake_client.add_comment.assert_called_once_with(
            text='thanks for watching',
            post_url=None,
            post_id=None,
            comment_url=None,
            comment_id='def456',
        )
        envelope = json.loads(stdout)
        self.assertEqual(envelope['data']['parent_comment_id'], 'def456')
        self.assertEqual(
            envelope['data']['comment']['url'],
            'https://reddit.com/r/test/comments/abc123/example/ghi789/',
        )


if __name__ == '__main__':
    unittest.main()
