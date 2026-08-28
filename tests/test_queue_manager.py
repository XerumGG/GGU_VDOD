"""Regression coverage: queue manager (item hooks, playlist expansion, queue panel UI, import/export helpers)."""

import os
import sys
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from ggu_vdod.download.engine import DownloadEngine, expand_playlist_urls  # noqa: E402


class ItemStartedHookTests(unittest.TestCase):
    def test_run_queue_reports_item_start_events(self):
        started = []

        class HookedEngine(DownloadEngine):
            def _on_item_started(self, url, index, total):
                started.append((url, index, total))

            def process_url(self, url, settings):
                pass  # immediate success

        engine = HookedEngine({}, log=lambda m: None)
        success, failed = engine.run_queue(["u1", "u2"])
        self.assertEqual((success, failed), (2, 0))
        self.assertEqual(started, [("u1", 1, 2), ("u2", 2, 2)])


class _FakeYDL:
    def __init__(self, options):
        self.options = options

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def extract_info(self, url, download=False):
        if "playlist" in url:
            return {
                "_type": "playlist",
                "entries": [
                    {"title": "Ep1", "url": "https://site/watch/1"},
                    {"title": "Ep2", "url": "https://site/watch/2"},
                    {"title": "Ep1 again", "url": "https://site/watch/1"},
                ],
            }
        if "broken" in url:
            raise RuntimeError("boom")
        return {"_type": "video"}


class _FakeYTDLP:
    YoutubeDL = _FakeYDL


class PlaylistExpansionTests(unittest.TestCase):
    def run_expand(self, urls):
        import ggu_vdod.download.engine as engine_module
        original = engine_module.yt_dlp
        engine_module.yt_dlp = _FakeYTDLP
        try:
            return expand_playlist_urls(urls, log=lambda m: None)
        finally:
            engine_module.yt_dlp = original

    def test_playlist_expands_with_titles_and_deduplicates(self):
        pairs = self.run_expand(["https://site/playlist"])
        self.assertEqual(
            pairs,
            [("Ep1", "https://site/watch/1"), ("Ep2", "https://site/watch/2")],
        )

    def test_single_urls_pass_through_with_empty_title(self):
        self.assertEqual(
            self.run_expand(["https://site/watch/9"]),
            [("", "https://site/watch/9")],
        )

    def test_failed_expansion_keeps_original_url(self):
        self.assertEqual(self.run_expand(["https://site/broken"]), [("", "https://site/broken")])

    def test_mixed_batch(self):
        pairs = self.run_expand(["https://site/watch/9", "https://site/playlist"])
        self.assertEqual(
            [url for _t, url in pairs],
            ["https://site/watch/9", "https://site/watch/1", "https://site/watch/2"],
        )
        self.assertEqual(pairs[0][0], "")

    def test_prefers_webpage_url_and_rebuilds_youtube_id(self):
        import ggu_vdod.download.engine as engine_module

        class FakeYDL:
            def __init__(self, _options):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def extract_info(self, _url, download=False):
                return {
                    "_type": "playlist",
                    "entries": [
                        {"title": "Web page", "url": "wrong", "webpage_url": "https://site/watch/1"},
                        {"title": "YouTube ID", "url": "abc123", "ie_key": "Youtube"},
                    ],
                }

        class FakeModule:
            YoutubeDL = FakeYDL

        original = engine_module.yt_dlp
        engine_module.yt_dlp = FakeModule
        try:
            pairs = expand_playlist_urls(["https://site/playlist"])
        finally:
            engine_module.yt_dlp = original
        self.assertEqual(
            pairs,
            [
                ("Web page", "https://site/watch/1"),
                ("YouTube ID", "https://www.youtube.com/watch?v=abc123"),
            ],
        )


class QueuePanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from ggu_vdod.ui.qt.application import create_qt_application

        cls.application = create_qt_application([])

    def setUp(self):
        from ggu_vdod.ui.qt.main_window import QtMainWindow

        self.window = QtMainWindow(settings={}, persist_settings=False)

    def tearDown(self):
        self.window.close()

    def test_reset_populates_rows(self):
        self.window._queue_reset([("", "https://a/1"), ("Title B", "https://b/2")])
        table = self.window.queue_table
        self.assertEqual(table.rowCount(), 2)
        self.assertEqual(table.item(0, 2).text(), "Queued")
        self.assertEqual(table.item(1, 1).text(), "Title B")
        self.assertTrue(self.window.queue_clear_btn.isEnabled())
        self.assertFalse(self.window.queue_retry_btn.isEnabled())

    def test_lifecycle_updates_rows_and_retry_button(self):
        self.window._queue_reset([("", "https://a/1"), ("", "https://b/2")])
        self.window._on_queue_item_started("https://a/1", 1, 2)
        self.assertEqual(self.window.queue_table.item(0, 2).text(), "Downloading")

        self.window._on_queue_progress(
            {"item_index": 1, "progress": 55.0, "download_rate": "2 MB/s", "eta": "0:30"}
        )
        self.assertEqual(self.window.queue_table.item(0, 3).text(), "55%")
        self.assertEqual(self.window.queue_table.item(0, 4).text(), "2 MB/s")
        self.assertEqual(self.window.queue_table.item(0, 5).text(), "0:30")

        self.window._on_queue_item_finished("https://a/1", True, "video")
        self.assertEqual(self.window.queue_table.item(0, 2).text(), "Completed")

        self.window._on_queue_item_finished("https://b/2", False, "video")
        self.assertEqual(self.window.queue_table.item(1, 2).text(), "Failed")

        self.window._on_queue_completed(1, 1)
        self.assertTrue(self.window.queue_retry_btn.isEnabled())

    def test_retry_failed_requeues_only_failed_urls(self):
        self.window._queue_reset([("", "https://a/1"), ("", "https://b/2"), ("", "https://c/3")])
        self.window._on_queue_item_finished("https://a/1", True, "video")
        self.window._on_queue_item_finished("https://b/2", False, "video")
        self.window._on_queue_item_finished("https://c/3", False, "video")

        with mock.patch.object(self.window, "_start_download") as start:
            self.window._retry_failed_from_queue()

        start.assert_called_once()
        self.assertEqual(
            self.window.url_text.toPlainText().splitlines(),
            ["https://b/2", "https://c/3"],
        )

    def test_completed_run_marks_queued_rows_skipped(self):
        self.window._queue_reset([("", "https://a/1"), ("", "https://b/2")])
        self.window._on_queue_item_started("https://a/1", 1, 2)
        self.window._on_queue_item_finished("https://a/1", True, "video")
        self.window._on_queue_completed(1, 0)
        self.assertEqual(self.window.queue_table.item(1, 2).text(), "Skipped")


class WorkerPlaylistModeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from ggu_vdod.ui.qt.application import create_qt_application

        cls.application = create_qt_application([])

    def test_single_only_does_not_expand_playlist(self):
        from ggu_vdod.ui.qt import main_window as qt_main

        worker = qt_main.QtDownloadWorker(
            ["https://site/watch/1?list=abc"],
            {"single_only": True},
        )
        with mock.patch.object(qt_main, "expand_playlist_urls") as expand, \
                mock.patch.object(worker.engine, "run_queue", return_value=(1, 0)):
            worker.run()
        expand.assert_not_called()

    def test_unchecked_single_only_expands_playlist(self):
        from ggu_vdod.ui.qt import main_window as qt_main

        worker = qt_main.QtDownloadWorker(
            ["https://site/playlist"],
            {"single_only": False},
        )
        with mock.patch.object(
            qt_main,
            "expand_playlist_urls",
            return_value=[("Episode", "https://site/watch/1")],
        ) as expand, mock.patch.object(worker.engine, "run_queue", return_value=(1, 0)) as run_queue:
            worker.run()
        expand.assert_called_once()
        run_queue.assert_called_once_with(["https://site/watch/1"])

    def test_unexpected_worker_error_still_completes_queue(self):
        from ggu_vdod.ui.qt import main_window as qt_main

        worker = qt_main.QtDownloadWorker(["https://site/watch/1"], {"single_only": True})
        errors = []
        completed = []
        worker.error_occurred.connect(lambda url, message: errors.append((url, message)))
        worker.queue_completed.connect(lambda success, failed: completed.append((success, failed)))
        with mock.patch.object(worker.engine, "run_queue", side_effect=RuntimeError("boom")):
            worker.run()
        self.assertEqual(errors, [("", "boom")])
        self.assertEqual(completed, [(0, 1)])


class ExtractUrlsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from ggu_vdod.ui.qt.application import create_qt_application

        cls.application = create_qt_application([])

    def test_extracts_from_csv_and_text_and_deduplicates(self):
        from ggu_vdod.ui.qt.main_window import QtMainWindow

        text = (
            "name,url,notes\n"
            "ep1,https://site/watch/1?q=a,good\n"
            "ep2,https://site/watch/2,\n"
            "bare www.example.com/page. link\n"
            "dup https://site/watch/1?q=a again\n"
        )
        urls = QtMainWindow._extract_urls_from_text(text)
        self.assertEqual(
            urls,
            [
                "https://site/watch/1?q=a",
                "https://site/watch/2",
                "www.example.com/page",
            ],
        )


if __name__ == "__main__":
    unittest.main()
