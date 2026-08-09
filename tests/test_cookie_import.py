"""Regression tests for consent-first Netscape cookies.txt imports."""

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


class CookieImportTests(unittest.TestCase):
    def test_netscape_cookie_summary_exposes_domains_but_not_values(self):
        from ggu_vdod.services.cookies import inspect_netscape_cookie_file

        with tempfile.TemporaryDirectory() as temp_dir:
            cookie_file = Path(temp_dir) / "cookies.txt"
            cookie_file.write_text(
                "# Netscape HTTP Cookie File\n"
                ".youtube.com\tTRUE\t/\tTRUE\t2147483647\tSID\tsecret-value\n"
                "#HttpOnly_.example.com\tTRUE\t/\tFALSE\t2147483647\tsession\tprivate-value\n",
                encoding="utf-8",
            )
            summary = inspect_netscape_cookie_file(cookie_file)

        self.assertEqual(summary["cookie_count"], 2)
        self.assertEqual(summary["domains"], ("example.com", "youtube.com"))
        self.assertNotIn("secret-value", repr(summary))

    def test_invalid_cookie_file_is_rejected(self):
        from ggu_vdod.services.cookies import inspect_netscape_cookie_file

        with tempfile.TemporaryDirectory() as temp_dir:
            cookie_file = Path(temp_dir) / "not-cookies.txt"
            cookie_file.write_text("not a Netscape cookie file", encoding="utf-8")
            with self.assertRaises(ValueError):
                inspect_netscape_cookie_file(cookie_file)

    def test_unremembered_cookie_path_is_not_saved(self):
        from ggu_vdod.ui.qt.application import create_qt_application
        from ggu_vdod.ui.qt.main_window import QtMainWindow

        application = create_qt_application([])
        window = QtMainWindow(settings={}, persist_settings=False)
        window.cookie_file_input.setText(r"C:\Temp\cookies.txt")
        window.remember_cookie_path_check.setChecked(False)
        self.assertEqual(window._settings_from_ui()["cookies_file"], "")
        self.assertEqual(window._settings_from_ui(include_cookie_file=True)["cookies_file"], r"C:\Temp\cookies.txt")
        window.remember_cookie_path_check.setChecked(True)
        self.assertEqual(window._settings_from_ui()["cookies_file"], r"C:\Temp\cookies.txt")
        window.close()
        application.processEvents()


if __name__ == "__main__":
    unittest.main()
