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
            json.dump(data, config_file, indent=2)
    except Exception:
        pass


HISTORY_FILE = os.path.join(CONFIG_DIR, "history.json")


def load_history():
    try:
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return []


def add_history_entry(url, title="", format_type="", status="Completed"):
    try:
        history = load_history()
        # Remove duplicate if exists
        history = [item for item in history if item.get("url") != url]
        history.insert(0, {
            "url": url,
            "title": title or url,
            "format": format_type,
            "status": status,
            "timestamp": os.getenv("LOCAL_TIME") or "Recently",
        })
        # Keep latest 500 entries
        history = history[:500]
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2)
    except Exception:
        pass


def clear_history():
    try:
        if os.path.exists(HISTORY_FILE):
            os.remove(HISTORY_FILE)
    except Exception:
        pass

