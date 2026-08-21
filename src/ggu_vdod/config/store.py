"""Persistent user settings with deliberately forgiving failure handling."""

import hashlib
import json
import os
import time

from .paths import CONFIG_DIR, CONFIG_FILE

# Settings that define a distinct output artifact. A re-download with the same
# values produces an identical file, so matching fingerprints mean duplicates.
_FINGERPRINT_KEYS = (
    "format", "output_format", "quality", "exact_format_id", "video_codec",
    "video_bitrate", "conversion_resolution", "frame_rate", "sample_rate",
    "channels", "start_time", "end_time", "filename_pattern",
)


def compute_settings_fingerprint(settings: dict) -> str:
    """Return a stable short hash of everything that shapes the output file."""
    payload = {key: str(settings.get(key) or "") for key in _FINGERPRINT_KEYS}
    raw = json.dumps(payload, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _atomic_write_json(path, data):
    """Write JSON via a temp file + os.replace so crashes never corrupt the file."""
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_path, path)


def _timestamp_now():
    return time.strftime("%Y-%m-%d %H:%M")


def load_config():
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as config_file:
            return json.load(config_file)
    except Exception:
        return {}


def save_config(data):
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        _atomic_write_json(CONFIG_FILE, data)
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


def add_history_entry(url, title="", format_type="", status="Completed", fingerprint=""):
    try:
        history = load_history()
        # Remove duplicate if exists
        history = [item for item in history if item.get("url") != url]
        history.insert(0, {
            "url": url,
            "title": title or url,
            "format": format_type,
            "status": status,
            "fingerprint": fingerprint,
            "timestamp": _timestamp_now(),
        })
        # Keep latest 500 entries
        history = history[:500]
        os.makedirs(CONFIG_DIR, exist_ok=True)
        _atomic_write_json(HISTORY_FILE, history)
    except Exception:
        pass


def update_history_entry(url, status, title="", format_type="", fingerprint=""):
    """Update the status of an existing queue item without duplicating it."""
    try:
        history = load_history()
        for item in history:
            if item.get("url") == url:
                item["status"] = status
                if title:
                    item["title"] = title
                if format_type:
                    item["format"] = format_type
                if fingerprint:
                    item["fingerprint"] = fingerprint
                break
        else:
            history.insert(0, {
                "url": url,
                "title": title or url,
                "format": format_type,
                "status": status,
                "fingerprint": fingerprint,
                "timestamp": _timestamp_now(),
            })
        os.makedirs(CONFIG_DIR, exist_ok=True)
        _atomic_write_json(HISTORY_FILE, history[:500])
    except Exception:
        pass


def clear_history():
    try:
        if os.path.exists(HISTORY_FILE):
            os.remove(HISTORY_FILE)
    except Exception:
        pass
