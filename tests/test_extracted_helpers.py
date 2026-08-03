"""Behavior checks for the first extracted, non-GUI modules."""

from pathlib import Path
import sys
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))


class ExtractedHelperTests(unittest.TestCase):
    def test_playlist_url_is_reduced_to_selected_video(self):
        from ggu_vdod.preview.metadata import preview_target_url, youtube_video_id

        url = "https://www.youtube.com/watch?v=tI-GAeBx0YM&list=RDabc&index=13"
        self.assertEqual(youtube_video_id(url), "tI-GAeBx0YM")
        self.assertEqual(preview_target_url(url), "https://www.youtube.com/watch?v=tI-GAeBx0YM")

    def test_conversion_defaults_remain_stable(self):
        from ggu_vdod.conversion.options import audio_conversion_args, video_conversion_args

        video_settings = {
            "video_codec": "Auto",
            "conversion_resolution": "Source",
            "frame_rate": "Source",
            "video_bitrate": "",
        }
        audio_settings = {
            "quality": "320 kbps (Best)",
            "sample_rate": "Source",
            "channels": "Source",
            "compression_level": "Auto",
        }
        self.assertEqual(video_conversion_args(video_settings, "mp4"), [])
        self.assertEqual(
            audio_conversion_args(audio_settings, "mp3"),
            ["-vn", "-c:a", "libmp3lame", "-b:a", "320k"],
        )


if __name__ == "__main__":
    unittest.main()
