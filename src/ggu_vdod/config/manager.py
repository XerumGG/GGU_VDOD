"""Central settings manager: one place owns defaults, access, and persistence.

Every consumer reads defaults from ``default_settings()`` instead of scattering
literals across the UI, so adding a new preference means touching this module
only. Dependencies point inward: config never imports UI code.
"""

from copy import deepcopy

from ..core.constants import (
    DEFAULT_KEY_BINDINGS, SCROLL_SPEED_DEFAULT, ZOOM_DEFAULT_PERCENT,
)
from .paths import get_default_output_dir
from .store import load_config, save_config


def default_settings() -> dict:
    """Return a fresh copy of the canonical default settings."""
    return {
        # Download behavior
        "format": "video",
        "quality": "Best available",
        "output_format": "MP4",
        "output_dir": get_default_output_dir(),
        "single_only": True,
        "exact_format_id": "",
        "clean_sidecars": True,
        # Tools & network
        "ffmpeg_path": "",
        "cookies_browser": "None",
        "cookies_file": "",
        "remember_cookie_file": False,
        "proxy": "",
        # Media options
        "embed_subtitles": False,
        "auto_subtitles": False,
        "subtitle_langs": "en.*",
        "embed_metadata": True,
        "embed_thumbnail": False,
        "live_start_from_beginning": False,
        # Local conversion
        "video_codec": "Auto",
        "video_bitrate": "",
        "conversion_resolution": "Source",
        "frame_rate": "Source",
        "sample_rate": "Source",
        "channels": "Source",
        "compression_level": "Auto",
        "start_time": "",
        "end_time": "",
        "filename_pattern": "",
        # Appearance & input
        "zoom_percent": ZOOM_DEFAULT_PERCENT,
        "font_family": "Segoe UI",
        "font_size": 10,
        "theme_name": "Dark",
        "theme_colors": None,
        "key_bindings": dict(DEFAULT_KEY_BINDINGS),
        "scroll_speed": SCROLL_SPEED_DEFAULT,
        # App state
        "language": "en",
        "last_update_check": 0,
    }


class SettingsManager:
    """Loads user settings over the defaults and persists changes atomically."""

    def __init__(self):
        self._data = default_settings()
        try:
            stored = load_config()
        except Exception:
            stored = {}
        if isinstance(stored, dict):
            self._data.update(stored)

    def get(self, key, default=None):
        """Return a setting value; falls back to the canonical default."""
        if key in self._data:
            return self._data[key]
        return default_settings().get(key, default)

    def set(self, key, value):
        self._data[key] = value

    def update(self, values: dict):
        self._data.update(values)

    def snapshot(self) -> dict:
        """Deep-enough copy safe to hand to UI code that mutates it."""
        snap = dict(self._data)
        for key, value in snap.items():
            if isinstance(value, dict):
                snap[key] = dict(value)
        return snap

    def replace(self, data: dict):
        """Adopt a full settings dict (merged over defaults) and persist it."""
        merged = default_settings()
        if isinstance(data, dict):
            merged.update(data)
        self._data = merged
        self.save()

    def save(self):
        try:
            save_config(self._data)
        except Exception:
            pass


settings_manager = SettingsManager()
