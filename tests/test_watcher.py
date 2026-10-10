"""通知・保存の境界を確認する。ネット接続や実際のメール送信は行わない。"""
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

import watcher
from sources.common import Job, matches


def job(job_id="new", title="WordPressサイト制作", summary=""):
    return Job("crowdworks", job_id, title, "https://example.com/jobs/1", summary=summary)


class WatcherTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.state_file = Path(self.temp.name) / "state" / "seen.json"
        self.enterContext(patch.object(watcher, "STATE_FILE", self.state_file))
        self.enterContext(patch.object(watcher, "load_dotenv"))
        self.mail = self.enterContext(patch.object(watcher, "mail"))
        self.drafts = self.enterContext(patch.object(watcher, "make_drafts", return_value={}))
        self.enterContext(contextlib.redirect_stdout(io.StringIO()))
        self.enterContext(contextlib.redirect_stderr(io.StringIO()))

    def run_check(self, results=None, errors=None, args=()):
        with patch.object(watcher, "collect", return_value=(results or {}, errors or {})), \
             patch("sys.argv", ["watcher.py", *args]):
            return watcher.main()

    def seed(self, count=0):
        watcher.save_state({"seen": {"crowdworks": ["old"]},
                            "fail_count": {"crowdworks": count}})

    def test_first_run_registers_without_email(self):
        self.assertEqual(self.run_check({"crowdworks": [job()]}), 0)
        self.mail.assert_not_called()
        self.assertEqual(watcher.load_state()["seen"]["crowdworks"], ["new"])

    def test_new_job_sent_once(self):
        self.seed()
        results = {"crowdworks": [job("old"), job()]}
        self.run_check(results)
        self.run_check(results)
        self.mail.assert_called_once()
        self.assertIn("新着案件", self.mail.call_args.args[0])
        self.assertEqual(watcher.load_state()["seen"]["crowdworks"], ["old", "new"])

    def test_failed_email_preserves_state_for_retry(self):
        self.seed()
        before = self.state_file.read_bytes()
        self.mail.side_effect = RuntimeError("SMTP unavailable")
        with self.assertRaises(RuntimeError):
            self.run_check({"crowdworks": [job()]})
        self.assertEqual(self.state_file.read_bytes(), before)

    def test_dry_run_never_sends_or_saves(self):
        self.seed()
        before = self.state_file.read_bytes()
        self.assertEqual(self.run_check({"crowdworks": [job()]}, args=["--dry-run"]), 0)
        self.mail.assert_not_called()
        self.drafts.assert_not_called()
        self.assertEqual(self.state_file.read_bytes(), before)

    def test_dry_run_reports_fetch_failure(self):
        self.assertEqual(self.run_check(errors={"crowdworks": "403"}, args=["--dry-run"]), 1)
        self.assertFalse(self.state_file.exists())
        self.mail.assert_not_called()

    def test_test_email_does_not_save(self):
        self.seed()
        before = self.state_file.read_bytes()
        self.run_check({"crowdworks": [job()]}, args=["--test", "1"])
        self.mail.assert_called_once()
        self.assertTrue(self.mail.call_args.args[0].startswith("【テスト】"))
        self.assertEqual(self.state_file.read_bytes(), before)

    def test_invalid_test_count_cannot_trigger_normal_run(self):
        for args in (["--test", "0"], ["--test", "-1"], ["--test", "1", "--dry-run"]):
            with self.subTest(args=args), self.assertRaises(SystemExit) as error:
                self.run_check(args=args)
            self.assertEqual(error.exception.code, 2)
        self.mail.assert_not_called()
        self.assertFalse(self.state_file.exists())

    def test_failure_alert_once_then_recovery_resets(self):
        self.seed(2)
        self.run_check(errors={"crowdworks": "403"})
        self.run_check(errors={"crowdworks": "403"})
        self.mail.assert_called_once()
        self.assertEqual(watcher.load_state()["fail_count"]["crowdworks"], 4)
        self.run_check({"crowdworks": [job("old")]})
        self.assertEqual(watcher.load_state()["fail_count"]["crowdworks"], 0)

    def test_failed_site_does_not_block_other_site(self):
        self.seed()
        self.run_check({"crowdworks": [job()]}, {"mamaworks": "unavailable"})
        self.mail.assert_called_once()
        state = watcher.load_state()
        self.assertEqual(state["fail_count"]["mamaworks"], 1)
        self.assertIn("new", state["seen"]["crowdworks"])

    def test_atomic_save_preserves_old_file_on_replace_failure(self):
        self.seed()
        before = self.state_file.read_bytes()
        with patch.object(Path, "replace", side_effect=OSError("disk error")):
            with self.assertRaises(OSError):
                watcher.save_state({"seen": {}, "fail_count": {}})
        self.assertEqual(self.state_file.read_bytes(), before)
        self.assertEqual(list(self.state_file.parent.glob("*.tmp")), [])
        json.loads(before)


class MatchingTests(unittest.TestCase):
    def setUp(self):
        self.config = yaml.safe_load((watcher.ROOT / "config.yaml").read_text(encoding="utf-8"))

    def matches(self, title, summary=""):
        return matches(job(title=title, summary=summary), self.config["keywords"], self.config["exclude"])

    def test_full_width_keyword(self):
        self.assertTrue(self.matches("ＷｏｒｄＰｒｅｓｓサイト制作"))
        self.assertTrue(self.matches("ＬＰ制作をお願いします"))

    def test_writing_jobs_excluded(self):
        self.assertFalse(self.matches("WordPressの記事制作"))
        self.assertFalse(self.matches("WordPress ライティング継続依頼"))
        self.assertFalse(self.matches("ホームページ制作の営業パートナー募集"))

    def test_description_mention_does_not_exclude_design_job(self):
        self.assertTrue(self.matches("WordPressサイト制作", "ライティングは別担当です"))


if __name__ == "__main__":
    unittest.main()
