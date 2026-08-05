"""Tests for zoom constants, clamping, and key binding sequence resolution."""

from pathlib import Path
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from ggu_vdod.core.constants import (
    ZOOM_DEFAULT_PERCENT,
    ZOOM_MAX_PERCENT,
    ZOOM_MIN_PERCENT,
    clamp_zoom_percent,
)


class ZoomAndBindingTests(unittest.TestCase):
    def test_zoom_constants_bounds(self):
        self.assertEqual(ZOOM_MIN_PERCENT, 80)
        self.assertEqual(ZOOM_MAX_PERCENT, 140)

    def test_clamp_zoom_percent(self):
        self.assertEqual(clamp_zoom_percent(50), 80)
        self.assertEqual(clamp_zoom_percent(80), 80)
        self.assertEqual(clamp_zoom_percent(100), 100)
        self.assertEqual(clamp_zoom_percent(140), 140)
        self.assertEqual(clamp_zoom_percent(200), 140)
        self.assertEqual(clamp_zoom_percent("invalid"), ZOOM_DEFAULT_PERCENT)


if __name__ == "__main__":
    unittest.main()
