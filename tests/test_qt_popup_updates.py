"""Regression coverage for native popup controls and package-update UI state."""

import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))


class QtPopupAndUpdateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from ggu_vdod.ui.qt.application import create_qt_application

        cls.application = create_qt_application([])

    def test_custom_dialogs_receive_native_minimize_maximize_and_close_controls(self):
        from PySide6.QtCore import Qt
        from ggu_vdod.ui.qt.dialogs import KeyBindingsDialog

        dialog = KeyBindingsDialog()
        dialog.show()
        self.application.processEvents()
        flags = dialog.windowFlags()
        self.assertTrue(flags & Qt.WindowType.WindowMinimizeButtonHint)
        self.assertTrue(flags & Qt.WindowType.WindowMaximizeButtonHint)
        self.assertTrue(flags & Qt.WindowType.WindowCloseButtonHint)
        self.assertTrue(dialog.isSizeGripEnabled())
        dialog.close()

    def test_update_button_enables_only_for_supported_available_updates(self):
        from ggu_vdod.ui.qt.dialogs import UpdateCheckDialog

        with patch.object(UpdateCheckDialog, "_check_versions"):
            dialog = UpdateCheckDialog()
        dialog._populate_results([
            ("curl_cffi", "dependency", "0.15.0", "0.16.0", "Update available"),
            ("FFmpeg", "binary", "Ready", "Latest Build", "Ready"),
        ])
        self.assertTrue(dialog.update_btn.isEnabled())
        self.assertIn("1 available", dialog.update_btn.text())
        dialog.close()


if __name__ == "__main__":
    unittest.main()
