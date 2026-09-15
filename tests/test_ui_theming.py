"""Regression coverage: theme-driven surfaces, mnemonic-free tabs, layout guards."""

import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))


class ThemeSurfaceTests(unittest.TestCase):
    def test_media_background_present_in_defaults_and_presets(self):
        from ggu_vdod.ui.qt.theme import THEME_PRESETS, normalize_theme

        self.assertIn("media_background", normalize_theme(None))
        for name, preset in THEME_PRESETS.items():
            normalized = normalize_theme(preset)
            self.assertRegex(normalized["media_background"], r"^#[0-9a-f]{6}$", name)

    def test_eight_digit_hex_folds_to_qss_safe_six_digits(self):
        from ggu_vdod.ui.qt.theme import is_valid_theme_color, normalize_theme

        self.assertTrue(is_valid_theme_color("#f5f5f699"))
        self.assertTrue(is_valid_theme_color("#f5f5f6"))
        self.assertFalse(is_valid_theme_color("not-a-color"))
        colors = normalize_theme({"log_background": "#f5f5f699"})
        self.assertEqual(colors["log_background"], "#f5f5f6")
        # Every normalized value must be QSS-parseable.
        import re
        for key, value in normalize_theme(None).items():
            self.assertRegex(value, r"^#[0-9a-f]{6}$", key)


class MainWindowThemingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from ggu_vdod.ui.qt.application import create_qt_application

        cls.application = create_qt_application([])

    def _make_window(self):
        from ggu_vdod.ui.qt.main_window import QtMainWindow

        return QtMainWindow(settings={}, persist_settings=False)

    def test_tab_titles_have_no_mnemonic_markers(self):
        window = self._make_window()
        try:
            for index in range(window.main_tab_widget.count()):
                self.assertNotIn("&", window.main_tab_widget.tabText(index))
        finally:
            window.close()

    def test_preview_surface_uses_theme_object_name(self):
        window = self._make_window()
        try:
            self.assertEqual(window.preview_image.objectName(), "previewImage")
            self.assertNotIn("background", window.preview_image.styleSheet())
            self.assertTrue(window.subtitle_lbl.wordWrap())
            self.assertTrue(window.preview_title.wordWrap())
            self.assertGreaterEqual(window.batch_counter_lbl.minimumWidth(), 60)
        finally:
            window.close()

    def test_corner_buttons_cannot_clip_their_text(self):
        window = self._make_window()
        try:
            for button in (window.uninstall_btn, window.update_btn):
                self.assertGreaterEqual(
                    button.minimumWidth(), button.sizeHint().width()
                )
        finally:
            window.close()

    def test_mailpit_preview_box_uses_theme_object_name(self):
        window = self._make_window()
        try:
            box = window.test_inbox_widget.preview_box
            self.assertEqual(box.objectName(), "mailContent")
            self.assertNotIn("#111", box.styleSheet())
        finally:
            window.close()


class HelpDialogThemingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from ggu_vdod.ui.qt.application import create_qt_application

        cls.application = create_qt_application([])

    def test_help_surfaces_follow_live_theme(self):
        from PySide6.QtWidgets import QTextBrowser
        from ggu_vdod.ui.qt.dialogs import HelpCenterDialog
        from ggu_vdod.ui.qt.theme import normalize_theme

        dialog = HelpCenterDialog()
        try:
            palette = HelpCenterDialog._doc_palette()
            self.assertIn(palette["accent"], dialog.tabs.styleSheet())
            for browser in dialog.findChildren(QTextBrowser):
                html = browser.toHtml()
                for dead in ("#141414", "#0a0a0a", "#e2e2e2", "#a7a7a7", "#cccccc"):
                    self.assertNotIn(dead, html)
            # Accent + text roles must appear in the rendered guide.
            first = dialog.findChildren(QTextBrowser)[0].toHtml()
            self.assertIn(palette["accent"].lower(), first.lower())
        finally:
            dialog.close()


if __name__ == "__main__":
    unittest.main()
