"""Regression coverage for the centralized Qt theme and typography policy."""

import os
from pathlib import Path
import sys
import unittest


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))


class QtThemeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from ggu_vdod.ui.qt.application import create_qt_application

        cls.application = create_qt_application([])

    def test_invalid_theme_fields_fall_back_to_safe_dark_values(self):
        from ggu_vdod.ui.qt.theme import DEFAULT_THEME, normalize_theme

        colors = normalize_theme({"accent": "not-a-color", "text": "#ABCDEF"})
        self.assertEqual(colors["accent"], DEFAULT_THEME["accent"])
        self.assertEqual(colors["text"], "#abcdef")
        self.assertEqual(colors["panel_background"], DEFAULT_THEME["panel_background"])

    def test_theme_dialog_reset_restores_dark_defaults(self):
        from ggu_vdod.ui.qt.dialogs import ThemePreferencesDialog
        from ggu_vdod.ui.qt.theme import DEFAULT_THEME

        dialog = ThemePreferencesDialog({"accent": "#123456"})
        dialog._reset_theme()
        name, colors = dialog.get_theme_settings()
        self.assertEqual(name, "Dark")
        self.assertEqual(colors, DEFAULT_THEME)
        dialog.close()

    def test_window_applies_saved_theme_and_proportional_font_scale(self):
        from ggu_vdod.ui.qt.main_window import QtMainWindow

        window = QtMainWindow(
            settings={
                "theme_colors": {"accent": "#123456", "window_background": "#050505"},
                "font_family": "Segoe UI",
                "font_size": 12,
                "zoom_percent": 120,
            },
            persist_settings=False,
        )
        colors = self.application.property("ggu_theme")
        self.assertEqual(colors["accent"], "#123456")
        self.assertEqual(colors["window_background"], "#050505")
        self.assertEqual(self.application.font().pointSize(), 14)
        self.assertEqual(window.log_box.objectName(), "logBox")
        window.close()


if __name__ == "__main__":
    unittest.main()
