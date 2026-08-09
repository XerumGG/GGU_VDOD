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


def get_default_ffmpeg_path():
    r"""Return the default FFmpeg executable path (D:\GGU_VDOD\ffmpeg\ffmpeg.exe)."""
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(sys.executable)
        meipass = getattr(sys, "_MEIPASS", exe_dir)
        bundled_candidates = [
            os.path.join(exe_dir, "ffmpeg", "ffmpeg.exe"),
            os.path.join(exe_dir, "ffmpeg.exe"),
            os.path.join(meipass, "ffmpeg", "ffmpeg.exe"),
            os.path.join(meipass, "ffmpeg.exe"),
        ]
        for c in bundled_candidates:
            if os.path.exists(c):
                return c

    candidates = [
        r"D:\GGU_VDOD\ffmpeg\ffmpeg.exe",
        os.path.join(get_app_dir(), "ffmpeg", "ffmpeg.exe"),
        os.path.join(get_app_dir(), "dist", "GGU_VDOD", "ffmpeg", "ffmpeg.exe"),
        os.path.join(get_app_dir(), "dist", "GGU_VDOD", "ffmpeg.exe"),
    ]
    for candidate in candidates:
        if os.path.exists(candidate):
            return candidate

    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if exe and os.path.exists(exe):
            return exe
    except Exception:
        pass

    return r"D:\GGU_VDOD\ffmpeg\ffmpeg.exe"


CONFIG_DIR = get_config_dir()
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
