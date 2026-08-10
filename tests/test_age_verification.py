from pathlib import Path
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from PySide6.QtWidgets import QApplication, QDialog

from ggu_vdod.auth.sanitizer import is_adult_or_age_restricted_url
from ggu_vdod.ui.qt.dialogs import AgeVerificationDialog, AgeGateAuthDialog
from ggu_vdod.ui.qt.main_window import QtMainWindow

app = QApplication.instance() or QApplication([])


class AgeVerificationTests(unittest.TestCase):
    """Test suite verifying 18+ adult URL detection and age gate dialogs."""

    def test_adult_url_detection(self):
        self.assertTrue(is_adult_or_age_restricted_url("https://example.com/video?age-gate=true"))
        self.assertTrue(is_adult_or_age_restricted_url("http://staging.local/18+content"))
        self.assertTrue(is_adult_or_age_restricted_url("https://restricted.site/nsfw"))
        self.assertFalse(is_adult_or_age_restricted_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ"))
        self.assertFalse(is_adult_or_age_restricted_url("https://vimeo.com/76979871"))
        self.assertFalse(is_adult_or_age_restricted_url(""))

    def test_age_verification_dialog_builds(self):
        dlg = AgeVerificationDialog("https://example.com/video?age-gate=true")
        self.assertEqual(dlg.windowTitle(), "Age Verification Required (18+)")
        dlg.close()

    def test_age_gate_auth_dialog_choices(self):
        dlg = AgeGateAuthDialog("example.com")
        self.assertEqual(dlg.user_action, "guest")
        dlg._on_cookies_chosen()
        self.assertEqual(dlg.user_action, "cookies")
        dlg._on_sessions_chosen()
        self.assertEqual(dlg.user_action, "account_sessions")
        dlg._on_mailpit_chosen()
        self.assertEqual(dlg.user_action, "mailpit")
        dlg.close()

    def test_main_window_filters_unconfirmed_adult_urls(self):
        window = QtMainWindow(settings={}, persist_settings=False)
        urls = ["https://www.youtube.com/watch?v=dQw4w9WgXcQ"]
        result = window._handle_age_verification(urls)
        self.assertEqual(result, urls)
        window.close()


if __name__ == "__main__":
    unittest.main()
