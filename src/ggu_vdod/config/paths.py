"""Filesystem locations used by the application."""

import os
import sys

from ..core.constants import APP_NAME


def get_config_dir():
    """Return a per-user configuration directory on the current OS."""
    if sys.platform == "win32":
        base = os.getenv("LOCALAPPDATA") or os.path.expanduser("~\\AppData\\Local")
    elif sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support")
    else:
        base = os.getenv("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return os.path.join(base, APP_NAME)


def get_default_output_dir():
    """Choose a writable, conventional downloads folder."""
    downloads = os.path.join(os.path.expanduser("~"), "Downloads")
    if os.path.isdir(downloads):
        return os.path.join(downloads, APP_NAME)
    return os.path.join(os.path.expanduser("~"), APP_NAME)


def get_app_dir():
    """Return the executable directory, or the repository root in source mode."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))


CONFIG_DIR = get_config_dir()
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
