"""Unit tests for Phase 4 temporary cookie database wiper helpers."""

from pathlib import Path
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from ggu_vdod.services.cookies import get_temp_cookies_dir, purge_all_temporary_cookie_files


class CookieWiperTests(unittest.TestCase):
    def test_temp_cookies_dir_and_purge(self):
        tmp_dir = get_temp_cookies_dir()
        self.assertTrue(tmp_dir.exists())

        test_file = tmp_dir / "dummy_cookies.sqlite"
        test_file.write_text("dummy database content", encoding="utf-8")
        self.assertTrue(test_file.exists())

        purged_count = purge_all_temporary_cookie_files()
        self.assertGreaterEqual(purged_count, 1)
        self.assertFalse(test_file.exists())


if __name__ == "__main__":
    unittest.main()
