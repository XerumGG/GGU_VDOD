"""Regression coverage: disk guard, integrity gate, history paths, crash reports, recovery report."""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from ggu_vdod.download.engine import DownloadEngine  # noqa: E402
from ggu_vdod.config import store as history_store  # noqa: E402
from ggu_vdod.core.version import DEVELOPMENT_BUILD_LABEL  # noqa: E402
from ggu_vdod.services.crash import install_crash_handlers, write_crash_report  # noqa: E402


class DiskGuardTests(unittest.TestCase):
    def test_sufficient_space_returns_empty_message(self):
        self.assertEqual(DownloadEngine._disk_guard_message(10_000_000_000, 5_000_000_000), "")

    def test_insufficient_space_mentions_problem_and_sizes(self):
        msg = DownloadEngine._disk_guard_message(100_000_000, 500_000_000)
        self.assertIn("insufficient disk space", msg)
        self.assertIn("need", msg)


class IntegrityGateTests(unittest.TestCase):
    def setUp(self):
        self.engine = DownloadEngine({})

    def test_missing_file_raises_integrity_error(self):
        with self.assertRaises(ValueError) as ctx:
            self.engine._verify_integrity(os.path.join(tempfile.gettempdir(), "ggu_does_not_exist_9x.mp4"))
        self.assertIn("media integrity check failed", str(ctx.exception))

    def test_empty_string_target_raises(self):
        with self.assertRaises(ValueError):
            self.engine._verify_integrity("")

    def test_placeholder_sized_file_raises(self):
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as handle:
            handle.write(b"\x00" * 1024)
            tiny = handle.name
        try:
            with self.assertRaises(ValueError) as ctx:
                self.engine._verify_integrity(tiny)
            self.assertIn("media integrity check failed", str(ctx.exception))
        finally:
            os.remove(tiny)

    def test_full_sized_file_passes_gate(self):
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as handle:
            handle.write(os.urandom(64 * 1024))
            big = handle.name
        try:
            self.engine._verify_integrity(big)  # probe failure on garbage must not fail good size
        finally:
            os.remove(big)


class LastResultResetTests(unittest.TestCase):
    def test_failed_item_clears_stale_last_result(self):
        engine = DownloadEngine({})
        engine.last_result = {"output_dir": "old", "final_file": "old.mp4"}

        def boom(url, settings):
            raise RuntimeError("HTTP Error 404: Not Found")

        with mock.patch.object(engine, "process_url", side_effect=boom):
            ok = engine._download_with_retries("https://example.com/v")
        self.assertFalse(ok)
        self.assertEqual(engine.last_result, {})


class MissingLibraryQueueTests(unittest.TestCase):
    def test_run_queue_reports_failure_without_yt_dlp(self):
        errors = []
        engine = DownloadEngine({}, log=lambda m: None, error=lambda u, m: errors.append((u, m)))
        with mock.patch("ggu_vdod.download.engine.load_yt_dlp", return_value=None):
            success, failed = engine.run_queue(["https://example.com/a", "https://example.com/b"])
        self.assertEqual((success, failed), (0, 2))
        self.assertTrue(errors and "yt-dlp" in errors[0][1])


class HistoryPathPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        patcher = mock.patch.multiple(
            history_store,
            HISTORY_FILE=os.path.join(self.tmp.name, "history.json"),
            CONFIG_DIR=self.tmp.name,
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.tmp.cleanup)

    def test_add_and_update_persist_output_paths(self):
        history_store.add_history_entry(
            "https://example.com/v", title="V", format_type="video",
            status="Queued", output_dir="D:\\Out", final_file="D:\\Out\\v.mp4",
        )
        item = history_store.load_history()[0]
        self.assertEqual(item["output_dir"], "D:\\Out")
        self.assertEqual(item["final_file"], "D:\\Out\\v.mp4")

        history_store.update_history_entry(
            "https://example.com/v", "Completed",
            fingerprint="fp1", output_dir="E:\\New", final_file="E:\\New\\v.mkv",
        )
        item = history_store.load_history()[0]
        self.assertEqual(item["status"], "Completed")
        self.assertEqual(item["fingerprint"], "fp1")
        self.assertEqual(item["final_file"], "E:\\New\\v.mkv")

    def test_update_skips_blank_paths(self):
        history_store.add_history_entry(
            "https://example.com/keep", title="K", format_type="audio",
            status="Completed", output_dir="D:\\Keep", final_file="D:\\Keep\\k.mp3",
        )
        history_store.update_history_entry("https://example.com/keep", "Failed or cancelled")
        item = history_store.load_history()[0]
        self.assertEqual(item["output_dir"], "D:\\Keep")


class CrashReportTests(unittest.TestCase):
    def test_report_contains_build_and_traceback(self):
        install_crash_handlers()  # must not raise (regression: missing threading import)
        try:
            raise ZeroDivisionError("intentional test crash")
        except ZeroDivisionError:
            path = write_crash_report(*sys.exc_info())
        self.assertTrue(path and os.path.isfile(path))
        with open(path, "r", encoding="utf-8") as f:
            body = f.read()
        self.assertIn(DEVELOPMENT_BUILD_LABEL, body)
        self.assertIn("ZeroDivisionError", body)


class RecoveryReportQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from ggu_vdod.ui.qt.application import create_qt_application

        cls.application = create_qt_application([])

    def test_failure_tracking_and_recovery_report(self):
        from ggu_vdod.ui.qt.main_window import QtMainWindow

        window = QtMainWindow(settings={}, persist_settings=False)
        try:
            window._queue_error_alert(
                "https://www.youtube.com/watch?v=matrix",
                "ERROR: HTTP Error 429: Too Many Requests",
            )
            self.assertEqual(len(window._failed_this_run), 1)

            report = window._write_recovery_report()
            self.assertTrue(report and os.path.isfile(report))
            with open(report, "r", encoding="utf-8") as f:
                body = f.read()
            self.assertIn("RECOVERY REPORT", body)
            self.assertIn("watch?v=matrix", body)
            self.assertIn("ERR_RATE_LIMITED_429", body)
        finally:
            window.close()


if __name__ == "__main__":
    unittest.main()
