"""Headless safety checks for the parallel PySide6 interface."""

import os
from pathlib import Path
import sys
import unittest


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))


class QtShellTests(unittest.TestCase):
    def test_qt_shell_builds_and_switches_media_format_options(self):
        from ggu_vdod.ui.qt.application import create_qt_application
        from ggu_vdod.ui.qt.main_window import QtMainWindow
        from ggu_vdod.core.version import DEVELOPMENT_BUILD_LABEL

        application = create_qt_application([])
        window = QtMainWindow(settings={}, persist_settings=False)
        self.assertEqual(window.windowTitle(), "GGU_VDOD")
        self.assertTrue(window.video_radio.isChecked())
        self.assertEqual(window.output_format_combo.currentText(), "MP4")
        self.assertEqual(window.transfer_status.version_label.text(), DEVELOPMENT_BUILD_LABEL)
        window.audio_radio.setChecked(True)
        self.assertEqual(window.output_format_combo.currentText(), "MP3")
        window.close()
        application.processEvents()


if __name__ == "__main__":
    unittest.main()
