"""Crash report writer: app version, OS, last action, sanitized settings, traceback."""

import os
import platform
import sys
import threading
import time
import traceback


def _crash_dir():
    from ..config.paths import get_config_dir
    path = os.path.join(get_config_dir(), "crashes")
    os.makedirs(path, exist_ok=True)
    return path


def write_crash_report(exc_type, exc_value, exc_tb):
    try:
        from ..core.version import DEVELOPMENT_BUILD_LABEL
        from ..auth.sanitizer import sanitize_log_text

        settings_json = "{}"
        try:
            from ..config.manager import settings_manager
            import json as _json
            settings_json = sanitize_log_text(_json.dumps(settings_manager.snapshot(), default=str))
        except Exception:
            pass

        body = "\n".join([
            "=== GGU_VDOD CRASH REPORT ===",
            f"time:     {time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"build:    {DEVELOPMENT_BUILD_LABEL}",
            f"os:       {platform.platform()} ({sys.platform})",
            f"python:   {sys.version.split()[0]}",
            f"settings: {settings_json}",
            "",
            "--- traceback ---",
            "".join(traceback.format_exception(exc_type, exc_value, exc_tb)),
        ])

        name = time.strftime("crash_%Y%m%d_%H%M%S") + ".txt"
        with open(os.path.join(_crash_dir(), name), "w", encoding="utf-8") as f:
            f.write(body)

        # Keep the newest 20 reports.
        files = sorted(f for f in os.listdir(_crash_dir()) if f.startswith("crash_"))
        for old in files[:-20]:
            try:
                os.remove(os.path.join(_crash_dir(), old))
            except OSError:
                pass
        return os.path.join(_crash_dir(), name)
    except Exception:
        return None


def install_crash_handlers():
    """Hook both main-thread and thread exceptions into crash reports."""

    previous = sys.excepthook

    def _hook(exc_type, exc_value, exc_tb):
        write_crash_report(exc_type, exc_value, exc_tb)
        if previous is not None:
            previous(exc_type, exc_value, exc_tb)

    sys.excepthook = _hook

    prev_thread = getattr(threading, "excepthook", None)
    if prev_thread is None:
        return

    def _thread_hook(args):
        if args.exc_type not in (SystemExit, KeyboardInterrupt):
            write_crash_report(args.exc_type, args.exc_value, args.exc_traceback)
        prev_thread(args)

    threading.excepthook = _thread_hook
