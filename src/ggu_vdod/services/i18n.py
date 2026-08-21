"""Internationalization (i18n) and localization service for GGU_VDOD."""

import json
import os
import re
from pathlib import Path
from PySide6.QtCore import QObject, Signal, QLocale, Qt
from PySide6.QtWidgets import QApplication

SUPPORTED_LANGUAGES = {
    "Auto": "Auto-Detect System",
    "en": "English",
    "es": "Español",
    "fr": "Français",
    "de": "Deutsch",
    "hi": "हिन्दी (Hindi)",
    "bn": "বাংলা (Bengali)",
    "zh": "中文 (Chinese)",
    "ja": "日本語 (Japanese)",
    "ru": "Русский (Russian)",
    "pt": "Português",
    "ar": "العربية (Arabic)",
}

RTL_LANGUAGES = {"ar", "he", "fa", "ur"}

LOCALES_DIR = Path(__file__).parent.parent / "locales"


class I18nService(QObject):
    """Centralized translation manager with Qt signal emission."""

    language_changed = Signal(str)

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, parent=None):
        if hasattr(self, "_initialized") and self._initialized:
            return
        super().__init__(parent)
        self._initialized = True
        self._active_code = "en"
        self._translations = {}
        self._load_saved_language()

    def _load_saved_language(self):
        from ..config.manager import settings_manager
        saved_lang = settings_manager.get("language", "en")
        self.set_language(saved_lang, save_pref=False)

    def detect_system_language(self) -> str:
        """Detect system language code using PySide6 QLocale."""
        try:
            sys_locale = QLocale.system().name()  # e.g., 'en_US', 'hi_IN', 'es_ES', 'ar_SA'
            lang_code = sys_locale.split("_")[0].lower()
            if lang_code in SUPPORTED_LANGUAGES and lang_code != "Auto":
                return lang_code
        except Exception:
            pass
        return "en"

    def get_active_language(self) -> str:
        return self._active_code

    def set_language(self, lang_code: str, save_pref: bool = True):
        """Set active language code, load JSON catalog, update RTL layout, and emit signal."""
        if lang_code == "Auto":
            target_code = self.detect_system_language()
        else:
            target_code = lang_code if lang_code in SUPPORTED_LANGUAGES else "en"

        self._active_code = target_code
        self._load_translations(target_code)

        if save_pref:
            from ..config.manager import settings_manager
            settings_manager.set("language", lang_code)
            settings_manager.save()

        # Update Qt Application layout direction for RTL languages like Arabic
        app = QApplication.instance()
        if app:
            if target_code in RTL_LANGUAGES:
                app.setLayoutDirection(Qt.RightToLeft)
            else:
                app.setLayoutDirection(Qt.LeftToRight)

        self.language_changed.emit(target_code)

    def _load_translations(self, lang_code: str):
        self._translations = {}
        # First load master English as baseline
        en_path = LOCALES_DIR / "en.json"
        if en_path.exists():
            try:
                with open(en_path, "r", encoding="utf-8") as f:
                    self._translations = json.load(f)
            except Exception:
                pass

        if lang_code == "en":
            return

        lang_path = LOCALES_DIR / f"{lang_code}.json"
        if lang_path.exists():
            try:
                with open(lang_path, "r", encoding="utf-8") as f:
                    target_dict = json.load(f)
                    self._merge_dicts(self._translations, target_dict)
            except Exception:
                pass

    def _merge_dicts(self, base: dict, override: dict):
        for k, v in override.items():
            if isinstance(v, dict) and k in base and isinstance(base[k], dict):
                self._merge_dicts(base[k], v)
            else:
                base[k] = v

    def translate(self, key_path: str, default: str = None, **kwargs) -> str:
        """Look up nested dot-separated key (e.g. 'home.download') and format placeholders."""
        parts = key_path.split(".")
        current = self._translations
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                current = None
                break

        if current is None or not isinstance(current, str):
            res = default if default is not None else key_path
        else:
            res = current

        if kwargs:
            try:
                res = res.format(**kwargs)
            except Exception:
                pass

        return res


# Global singleton instance & convenient shorthand translate function
i18n = I18nService()


def t(key_path: str, default: str = None, **kwargs) -> str:
    return i18n.translate(key_path, default=default, **kwargs)
