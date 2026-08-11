"""Regression coverage for the Qt download-error alert queue."""

import os
from pathlib import Path
import sys
import unittest


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))


class QtErrorAlertTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from ggu_vdod.ui.qt.application import create_qt_application

        cls.application = create_qt_application([])

    def test_worker_failure_is_turned_into_a_visible_specific_alert(self):
        from ggu_vdod.ui.qt.main_window import QtMainWindow

        window = QtMainWindow(settings={}, persist_settings=False)
        window._queue_error_alert(
            "https://www.youtube.com/watch?v=example",
            "HTTP Error 429: Too Many Requests",
        )
        self.application.processEvents()

        dialog = window._active_error_alert
        self.assertIsNotNone(dialog)
        self.assertTrue(dialog.isVisible())
        self.assertEqual(dialog.details.code, "ERR_RATE_LIMITED_429")
        self.assertIn("Rate Limited", dialog.windowTitle())

        dialog.accept()
        self.application.processEvents()
        window.close()


if __name__ == "__main__":
    unittest.main()
