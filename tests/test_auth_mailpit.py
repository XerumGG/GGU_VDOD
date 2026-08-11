"""Unit tests for Phase 3 Mailpit integration, domain allowlist, and Test Inbox widget."""

from pathlib import Path
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from PySide6.QtWidgets import QApplication
from ggu_vdod.auth.mailpit import MailpitClient, is_staging_domain
from ggu_vdod.ui.qt.main_window import QtMainWindow
from ggu_vdod.ui.qt.test_inbox import MailpitTestInboxWidget

app = QApplication.instance() or QApplication(sys.argv)


class MailpitIntegrationTests(unittest.TestCase):
    def test_staging_domain_allowlist_validation(self):
        self.assertTrue(is_staging_domain("localhost"))
        self.assertTrue(is_staging_domain("127.0.0.1"))
        self.assertTrue(is_staging_domain("app.staging.local"))
        self.assertTrue(is_staging_domain("api.test"))
        self.assertTrue(is_staging_domain("server.dev"))
        self.assertFalse(is_staging_domain("untrusted-public-site.com"))

    def test_mailpit_client_instantiation(self):
        client = MailpitClient("http://localhost:8025")
        self.assertEqual(client.base_url, "http://localhost:8025")

    def test_mailpit_test_inbox_widget_instantiation(self):
        widget = MailpitTestInboxWidget()
        try:
            self.assertIsNotNone(widget.table)
            self.assertEqual(widget.table.columnCount(), 4)
        finally:
            widget.close()

    def test_main_window_has_three_tabs(self):
        window = QtMainWindow()
        try:
            self.assertTrue(hasattr(window, "test_inbox_widget"))
            self.assertEqual(window.main_tab_widget.count(), 3)
        finally:
            window.close()


if __name__ == "__main__":
    unittest.main()
