"""Regression coverage for native popup controls and package-update UI state."""

import os
from pathlib import Path
import sys
import tempfile
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

    def test_frozen_app_prepends_bundled_qt_directory(self):
        import ggu_vdod.ui.qt.application as qt_application

        with tempfile.TemporaryDirectory() as temp_dir:
            exe_dir = Path(temp_dir)
            qt_dir = exe_dir / "_internal" / "PySide6"
            shiboken_dir = exe_dir / "_internal" / "shiboken6"
            qt_dir.mkdir(parents=True)
            shiboken_dir.mkdir(parents=True)
            for name in ("Qt6Core.dll", "pyside6.abi3.dll"):
                (qt_dir / name).write_bytes(b"placeholder")
            (shiboken_dir / "shiboken6.abi3.dll").write_bytes(b"placeholder")
            fake_handle = object()
            fake_native_handles = []
            with patch.object(qt_application.sys, "frozen", True, create=True), \
                    patch.object(qt_application.sys, "executable", str(exe_dir / "GGU_VDOD.exe")), \
                    patch.object(qt_application.os, "add_dll_directory", return_value=fake_handle) as add_dll, \
                    patch.object(qt_application, "_load_native_library", side_effect=lambda path: fake_native_handles.append(path) or path) as win_dll, \
                    patch.dict(qt_application.os.environ, {"PATH": "existing-path"}, clear=False):
                before = len(qt_application._QT_DLL_HANDLES)
                qt_application._prepare_bundled_qt_dll_search_path()
                self.assertEqual(len(qt_application._QT_DLL_HANDLES), before + 3)
                self.assertEqual([call.args[0] for call in add_dll.call_args_list], [
                    str(exe_dir / "_internal"), str(shiboken_dir), str(qt_dir),
                ])
                self.assertEqual([Path(item).name for item in fake_native_handles], [
                    "shiboken6.abi3.dll", "Qt6Core.dll", "pyside6.abi3.dll",
                ])
                self.assertTrue(win_dll.call_count == 3)
                self.assertTrue(qt_application.os.environ["PATH"].startswith(str(qt_dir)))


if __name__ == "__main__":
    unittest.main()
