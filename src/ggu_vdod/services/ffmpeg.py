"""FFmpeg discovery independent from the window and download workflow."""

import os
import shutil
import sys

from ..config.paths import get_app_dir


def find_ffmpeg():
    """Best-effort auto-detection of a usable ffmpeg executable."""
    candidates = []
    which_result = shutil.which("ffmpeg")
    if which_result:
        candidates.append(which_result)

    executable_names = ["ffmpeg.exe", "ffmpeg"] if sys.platform == "win32" else ["ffmpeg"]
    app_dir = get_app_dir()
    for executable_name in executable_names:
        candidates.extend([
            os.path.join(app_dir, "ffmpeg", "bin", executable_name),
            os.path.join(app_dir, "ffmpeg", executable_name),
            os.path.join(app_dir, executable_name),
        ])
    if sys.platform == "win32":
        candidates.extend([
            r"C:\ffmpeg\bin\ffmpeg.exe",
            r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
            r"C:\Program Files (x86)\ffmpeg\bin\ffmpeg.exe",
        ])
    elif sys.platform == "darwin":
        candidates.extend(["/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg"])
    else:
        candidates.extend(["/usr/bin/ffmpeg", "/usr/local/bin/ffmpeg"])

    for candidate in candidates:
        if candidate and os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return ""
