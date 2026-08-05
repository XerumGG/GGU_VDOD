"""Smoke tests for the structural migration.

These tests deliberately avoid creating a GUI window or performing network
downloads. They verify that the source package and compatibility launcher stay
connected while implementation is extracted in follow-up commits.
"""

from pathlib import Path
import sys
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))


class ProjectLayoutTests(unittest.TestCase):
    def test_application_entry_point_imports(self):
        from ggu_vdod.app import main

        self.assertTrue(callable(main))

    def test_main_window_is_in_ui_package(self):
        from ggu_vdod.ui import QtMainWindow

        self.assertTrue(issubclass(QtMainWindow, object))

    def test_expected_source_packages_exist(self):
        for relative_path in (
            "core/__init__.py",
            "config/__init__.py",
            "download/__init__.py",
            "conversion/__init__.py",
            "preview/__init__.py",
            "plugins/__init__.py",
            "services/__init__.py",
            "ui/__init__.py",
        ):
            self.assertTrue((SOURCE_ROOT / "ggu_vdod" / relative_path).is_file())


if __name__ == "__main__":
    unittest.main()
