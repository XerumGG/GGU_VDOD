"""Persistent user settings with deliberately forgiving failure handling."""

import json
import os

from .paths import CONFIG_DIR, CONFIG_FILE


def load_config():
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as config_file:
            return json.load(config_file)
    except Exception:
        return {}


def save_config(data):
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as config_file:
            json.dump(data, config_file)
    except Exception:
        pass
