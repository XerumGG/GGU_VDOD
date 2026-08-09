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

    def test_every_advertised_audio_extension_has_conversion_arguments(self):
        from ggu_vdod.conversion.options import audio_conversion_args
        from ggu_vdod.core.constants import AUDIO_FORMAT_EXTENSIONS

        settings = {
            "quality": "320 kbps (Best)",
            "sample_rate": "Source",
            "channels": "Source",
            "compression_level": "Auto",
        }
        for extension in AUDIO_FORMAT_EXTENSIONS.values():
            with self.subTest(extension=extension):
                args = audio_conversion_args(settings, extension)
                self.assertIn("-vn", args)
                self.assertIn("-c:a", args)

    def test_opus_uses_a_supported_sample_rate_and_alac_uses_m4a(self):
        from ggu_vdod.conversion.options import audio_conversion_args
        from ggu_vdod.core.constants import AUDIO_FORMAT_EXTENSIONS

        opus_args = audio_conversion_args({
            "quality": "320 kbps (Best)", "sample_rate": "44100",
            "channels": "Source", "compression_level": "Auto", "output_format": "Opus",
        }, "opus")
        alac_args = audio_conversion_args({
            "quality": "320 kbps (Best)", "sample_rate": "Source",
            "channels": "Source", "compression_level": "Auto", "output_format": "ALAC",
        }, AUDIO_FORMAT_EXTENSIONS["ALAC"])
        self.assertEqual(opus_args[opus_args.index("-ar") + 1], "48000")
        self.assertEqual(AUDIO_FORMAT_EXTENSIONS["ALAC"], "m4a")
        self.assertEqual(alac_args[alac_args.index("-c:a") + 1], "alac")


if __name__ == "__main__":
    unittest.main()
