"""No-network behavior checks for the shared media preview service."""

from pathlib import Path
import sys
import unittest
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))


class _FakeYoutubeDL:
    received_options = None
    received_url = None

    def __init__(self, options):
        type(self).received_options = options

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def extract_info(self, url, download=False):
        type(self).received_url = url
        self.assertFalse(download)
        return {
            "title": "Example video",
            "uploader": "Example creator",
            "duration": 90,
            "height": 1080,
            "extractor_key": "Youtube",
            "thumbnails": [{"url": "https://example.invalid/thumb.jpg", "width": 1280, "height": 720}],
        }

    def assertFalse(self, value):
        if value:
            raise AssertionError("The preview service must not download media")


class PreviewServiceTests(unittest.TestCase):
    @patch("ggu_vdod.preview.service.download_thumbnail_bytes", return_value=b"thumbnail-bytes")
    @patch("ggu_vdod.preview.service.yt_dlp.YoutubeDL", _FakeYoutubeDL)
    def test_fetch_preview_uses_selected_playlist_video_without_download(self, _thumbnail):
        from ggu_vdod.preview.service import fetch_preview

        preview = fetch_preview(
            "https://www.youtube.com/watch?v=tI-GAeBx0YM&list=RDabc&index=13"
        )

        self.assertEqual(_FakeYoutubeDL.received_url, "https://www.youtube.com/watch?v=tI-GAeBx0YM")
        self.assertTrue(_FakeYoutubeDL.received_options["noplaylist"])
        self.assertEqual(preview["title"], "Example video")
        self.assertEqual(preview["details"], "Example creator  •  1:30  •  1080p")
        self.assertEqual(preview["source"], "YouTube")
        self.assertEqual(preview["thumbnail_data"], b"thumbnail-bytes")


if __name__ == "__main__":
    unittest.main()
