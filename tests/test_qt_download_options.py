"""Regression coverage for Qt settings restoration and yt-dlp option construction."""

import os
from pathlib import Path
import sys
import tempfile
import unittest


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))


class QtDownloadOptionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from ggu_vdod.ui.qt.application import create_qt_application

        cls.application = create_qt_application([])

    def test_audio_preferences_restore_the_audio_controls(self):
        from ggu_vdod.ui.qt.main_window import QtMainWindow

        window = QtMainWindow(settings={
            "format": "audio",
            "quality": "320 kbps (Best)",
            "output_format": "MP3",
        }, persist_settings=False)
        self.assertFalse(window.video_radio.isChecked())
        self.assertTrue(window.audio_radio.isChecked())
        self.assertEqual(window.quality_combo.currentText(), "320 kbps (Best)")
        self.assertEqual(window.output_format_combo.currentText(), "MP3")
        window.close()

    def test_saved_zoom_shortcut_and_scroll_speed_are_applied(self):
        from PySide6.QtGui import QAction
        from ggu_vdod.ui.qt.main_window import QtMainWindow

        window = QtMainWindow(settings={
            "key_bindings": {"zoom_in": "None", "zoom_out": "Ctrl + -", "zoom_reset": "Ctrl + 0"},
            "scroll_speed": 4,
        }, persist_settings=False)
        actions = {action.text(): action for action in window.findChildren(QAction)}
        self.assertEqual(actions["Zoom in"].shortcuts(), [])
        self.assertEqual(window.content_scroll.verticalScrollBar().singleStep(), 48)
        window.close()

    def test_video_quality_requests_the_exact_height_before_fallback(self):
        import ggu_vdod.ui.qt.main_window as module

        captured = []

        class FakeYDL:
            def __init__(self, options):
                self.options = options
                self.params = options
                self.postprocessors = []
                captured.append(self)

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def add_post_processor(self, postprocessor):
                self.postprocessors.append(postprocessor)

            def extract_info(self, _url, download=False):
                self.download = download
                return {"requested_formats": [{"format_id": "401", "height": 2160, "resolution": "3840x2160", "ext": "webm", "vcodec": "av01"}]}

        class FakeYTDLP:
            YoutubeDL = FakeYDL

        import ggu_vdod.download.engine as engine_module
        original_ytdlp = engine_module.yt_dlp
        engine_module.yt_dlp = FakeYTDLP
        try:
            with tempfile.TemporaryDirectory() as output_dir:
                settings = self._settings(output_dir, quality="2160p (4K)", output_format="MP4")
                worker = module.QtDownloadWorker(["https://example.invalid/video"], settings)
                worker._process_single_url("https://example.invalid/video", settings)
            self.assertIn("bestvideo[height=2160]", captured[0].options["format"])
            self.assertIn("bestvideo[height<=2160]", captured[0].options["format"])
            self.assertTrue(captured[0].download)
        finally:
            engine_module.yt_dlp = original_ytdlp

    def test_audio_targets_use_the_generic_ffmpeg_converter(self):
        import ggu_vdod.ui.qt.main_window as module
        from ggu_vdod.conversion.options import FFmpegCustomAudioConvertPP

        captured = []

        class FakeYDL:
            def __init__(self, options):
                self.options = options
                self.params = options
                self.postprocessors = []
                captured.append(self)

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def add_post_processor(self, postprocessor):
                self.postprocessors.append(postprocessor)

            def extract_info(self, _url, download=False):
                return {"requested_formats": [{"format_id": "251", "ext": "webm", "vcodec": "none", "acodec": "opus"}]}

        class FakeYTDLP:
            YoutubeDL = FakeYDL

        import ggu_vdod.download.engine as engine_module
        original_ytdlp = engine_module.yt_dlp
        engine_module.yt_dlp = FakeYTDLP
        try:
            with tempfile.TemporaryDirectory() as output_dir:
                settings = self._settings(output_dir, format_type="audio", quality="320 kbps (Best)", output_format="WMA")
                worker = module.QtDownloadWorker(["https://example.invalid/audio"], settings)
                worker._process_single_url("https://example.invalid/audio", settings)
            self.assertEqual(captured[0].options["format"], "bestaudio/best")
            self.assertTrue(any(isinstance(item, FFmpegCustomAudioConvertPP) for item in captured[0].postprocessors))
        finally:
            engine_module.yt_dlp = original_ytdlp

    @staticmethod
    def _settings(output_dir, format_type="video", quality="Best available", output_format="MP4"):
        return {
            "format": format_type,
            "quality": quality,
            "output_format": output_format,
            "output_dir": output_dir,
            "ffmpeg_path": "",
            "single_only": True,
            "filename_pattern": "",
            "cookies_browser": "None",
            "cookies_file": "",
            "proxy": "",
            "embed_subtitles": False,
            "auto_subtitles": False,
            "subtitle_langs": "en.*",
            "embed_metadata": False,
            "embed_thumbnail": False,
            "live_start_from_beginning": False,
            "exact_format_id": "",
            "video_codec": "Auto",
            "video_bitrate": "",
            "conversion_resolution": "Source",
            "frame_rate": "Source",
            "sample_rate": "Source",
            "channels": "Source",
            "compression_level": "Auto",
            "clean_sidecars": False,
        }


if __name__ == "__main__":
    unittest.main()
