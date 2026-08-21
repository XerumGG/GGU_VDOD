"""Unit tests for Phase 2 PySide6 Account & Session UI components."""

from pathlib import Path
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from PySide6.QtWidgets import QApplication
from ggu_vdod.ui.qt.account_panel import AccountSessionWidget, AddCredentialDialog
from ggu_vdod.ui.qt.main_window import QtMainWindow

app = QApplication.instance() or QApplication(sys.argv)


class QtAccountPanelTests(unittest.TestCase):
    def test_account_session_widget_instantiation(self):
        widget = AccountSessionWidget()
        try:
            self.assertIsNotNone(widget.table)
            self.assertEqual(widget.table.columnCount(), 5)
        finally:
            widget.close()


    def test_main_window_has_account_tab(self):
        window = QtMainWindow()
        try:
            self.assertTrue(hasattr(window, "main_tab_widget"))
            self.assertTrue(hasattr(window, "account_widget"))
            self.assertGreaterEqual(window.main_tab_widget.count(), 2)
        finally:
            window.close()


if __name__ == "__main__":
    unittest.main()
