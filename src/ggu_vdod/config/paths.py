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


def get_default_ffmpeg_dir():
    """Return the FFmpeg & FFprobe directory, searching bundled/repo/PATH locations."""
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(sys.executable)
        meipass = getattr(sys, "_MEIPASS", exe_dir)
        for folder in [
            os.path.join(exe_dir, "ffmpeg"),
            exe_dir,
            os.path.join(meipass, "ffmpeg"),
            meipass,
        ]:
            if os.path.isdir(folder) and (
                os.path.exists(os.path.join(folder, "ffmpeg.exe"))
                or os.path.exists(os.path.join(folder, "ffprobe.exe"))
            ):
                return folder

    # Check relative to the repository / app root (portable).
    repo_ffmpeg = os.path.join(get_app_dir(), "ffmpeg")
    if os.path.isdir(repo_ffmpeg) and os.path.exists(os.path.join(repo_ffmpeg, "ffmpeg.exe")):
        return repo_ffmpeg
    import shutil
    ffmpeg_on_path = shutil.which("ffmpeg")
    if ffmpeg_on_path:
        path_dir = os.path.dirname(os.path.abspath(ffmpeg_on_path))
        if os.path.exists(os.path.join(path_dir, "ffmpeg.exe")):
            return path_dir
    # Fallback: return the expected repo-relative directory even if it doesn't
    # exist yet — callers check for existence before using it.
    return repo_ffmpeg


def get_default_ffmpeg_path():
    """Return default FFmpeg binary path, searching bundled/repo/PATH locations."""
    dir_path = get_default_ffmpeg_dir()
    exe = os.path.join(dir_path, "ffmpeg.exe")
    if os.path.exists(exe):
        return exe

    try:
        import imageio_ffmpeg
        imageio_exe = imageio_ffmpeg.get_ffmpeg_exe()
        if imageio_exe and os.path.exists(imageio_exe):
            return imageio_exe
    except Exception:
        pass

    # Return the expected repo-relative path as a last resort.
    return os.path.join(get_app_dir(), "ffmpeg", "ffmpeg.exe")


def get_default_ffprobe_path():
    """Return default FFprobe binary path, searching bundled/repo/PATH locations."""
    dir_path = get_default_ffmpeg_dir()
    exe = os.path.join(dir_path, "ffprobe.exe")
    if os.path.exists(exe):
        return exe
    return os.path.join(get_app_dir(), "ffmpeg", "ffprobe.exe")


def get_default_qjs_path():
    """Return default QuickJS binary path (qjs.exe) for solving YouTube JavaScript challenges."""
    app_root = get_app_dir()
    for folder in [
        get_default_ffmpeg_dir(),
        os.path.join(app_root, "ffmpeg"),
        os.path.join(app_root, "bin"),
    ]:
        if folder and os.path.isdir(folder):
            exe = os.path.join(folder, "qjs.exe")
            if os.path.exists(exe):
                return exe
    import shutil
    return shutil.which("qjs") or shutil.which("quickjs")


CONFIG_DIR = get_config_dir()
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
