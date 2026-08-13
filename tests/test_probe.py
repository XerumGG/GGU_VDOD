"""Unit tests for FFprobe media inspection service module."""

import unittest
from src.ggu_vdod.services.probe import (
    format_duration_seconds, get_ffprobe_binary_path, parse_fraction_fps, probe_media_file,
)


class TestFFprobeService(unittest.TestCase):
    """Test FFprobe binary path discovery and output parsing."""

    def test_ffprobe_binary_path(self):
        path = get_ffprobe_binary_path()
        self.assertIsNotNone(path)
        self.assertTrue(path.endswith("ffprobe.exe"))

    def test_parse_fraction_fps(self):
        self.assertEqual(parse_fraction_fps("60/1"), "60")
        self.assertEqual(parse_fraction_fps("30000/1001"), "29.97")
        self.assertEqual(parse_fraction_fps("0/0"), "—")

    def test_format_duration_seconds(self):
        self.assertEqual(format_duration_seconds(125), "02:05")
        self.assertEqual(format_duration_seconds(3665), "01:01:05")
        self.assertEqual(format_duration_seconds(None), "—")

    def test_parse_time_str_to_seconds(self):
        from src.ggu_vdod.services.probe import parse_time_str_to_seconds
        self.assertEqual(parse_time_str_to_seconds("10s"), 10.0)
        self.assertEqual(parse_time_str_to_seconds("180s"), 180.0)
        self.assertEqual(parse_time_str_to_seconds("1:30"), 90.0)
        self.assertEqual(parse_time_str_to_seconds("00:01:30"), 90.0)
        self.assertEqual(parse_time_str_to_seconds("1m30s"), 90.0)
        self.assertEqual(parse_time_str_to_seconds("2.5m"), 150.0)
        self.assertEqual(parse_time_str_to_seconds("90"), 90.0)
        self.assertIsNone(parse_time_str_to_seconds(""))
        self.assertIsNone(parse_time_str_to_seconds("invalid"))

    def test_probe_media_invalid_file(self):
        res = probe_media_file("non_existent_file_path_123.mp4")
        self.assertFalse(res.get("success"))
        self.assertIn("error", res)


if __name__ == "__main__":
    unittest.main()
