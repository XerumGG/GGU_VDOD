"""Unit tests for I18nService and multi-language translation engine."""

import unittest
from src.ggu_vdod.services.i18n import I18nService, t, SUPPORTED_LANGUAGES


class TestI18nService(unittest.TestCase):

    def setUp(self):
        self.service = I18nService()
        self.service.set_language("en", save_pref=False)

    def test_default_english_translation(self):
        self.assertEqual(t("home.download_btn"), "Start Download Queue")
        self.assertEqual(t("converter.title"), "Local FFmpeg Media Converter")

    def test_fallback_on_missing_key(self):
        self.assertEqual(t("nonexistent.key", default="Fallback"), "Fallback")
        self.assertEqual(t("nonexistent.key"), "nonexistent.key")

    def test_language_switching_hindi(self):
        self.service.set_language("hi", save_pref=False)
        self.assertEqual(t("home.download_btn"), "डाउनलोड शुरू करें")
        self.assertEqual(t("settings.save_btn"), "प्राथमिकताएं सहेजें")

    def test_language_switching_spanish(self):
        self.service.set_language("es", save_pref=False)
        self.assertEqual(t("home.download_btn"), "Iniciar Cola de Descarga")
        self.assertEqual(t("converter.title"), "Convertidor de Medios Local FFmpeg")

    def test_language_switching_arabic(self):
        self.service.set_language("ar", save_pref=False)
        self.assertEqual(t("home.download_btn"), "بدء قائمة التنزيل")

    def tearDown(self):
        self.service.set_language("en", save_pref=False)


if __name__ == "__main__":
    unittest.main()
