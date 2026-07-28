"""
GGU_VDOD
A simple dark-themed desktop app to download videos as MP4 or audio as MP3.

Auto-resumes downloads that get interrupted (e.g. internet drops mid-download)
instead of starting over from scratch, and auto-detects an ffmpeg.exe on the
system so most people don't have to configure anything.

Requires (installed automatically by build.bat, or manually via pip):
    - yt-dlp

Also requires ffmpeg to be installed on the system (see README.md).
"""

import os
import sys
import json
import io
import re
import time
import queue
import socket
import shutil
import subprocess
import urllib.request
import traceback
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext

try:
    import yt_dlp
except ImportError:
    _root = tk.Tk()
    _root.withdraw()
    messagebox.showerror(
        "Missing dependency",
        "yt-dlp is not installed.\n\n"
        "Open a command prompt and run:\n\n"
        "    pip install yt-dlp\n\n"
        "Then restart this app."
    )
    sys.exit(1)

try:
    from PIL import Image, ImageTk
except ImportError:
    Image = None
    ImageTk = None


APP_NAME = "GGU_VDOD"

def get_config_dir():
    """Return a per-user config directory on Windows, macOS, or Linux."""
    if sys.platform == "win32":
        base = os.getenv("LOCALAPPDATA") or os.path.expanduser("~\\AppData\\Local")
    elif sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support")
    else:
        base = os.getenv("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return os.path.join(base, APP_NAME)


def get_default_output_dir():
    """Choose a writable, conventional downloads folder for the current OS."""
    downloads = os.path.join(os.path.expanduser("~"), "Downloads")
    if os.path.isdir(downloads):
        return os.path.join(downloads, APP_NAME)
    return os.path.join(os.path.expanduser("~"), APP_NAME)


CONFIG_DIR = get_config_dir()
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")

VIDEO_QUALITIES = ["Best available", "2160p (4K)", "1440p (2K)", "1080p", "720p", "480p", "360p"]
AUDIO_QUALITIES = ["320 kbps (Best)", "256 kbps", "192 kbps", "128 kbps"]
COOKIE_BROWSERS = ["None", "Chrome", "Edge", "Firefox", "Brave", "Opera", "Vivaldi", "Safari"]

HEIGHT_MAP = {
    "2160p (4K)": 2160,
    "1440p (2K)": 1440,
    "1080p": 1080,
    "720p": 720,
    "480p": 480,
    "360p": 360,
}

BITRATE_MAP = {
    "320 kbps (Best)": "320",
    "256 kbps": "256",
    "192 kbps": "192",
    "128 kbps": "128",
}

MAX_RETRIES = 999999  # effectively unlimited - keep retrying until internet comes back
RETRY_WAIT_SECONDS = 5
CONNECTIVITY_ENDPOINTS = (
    ("1.1.1.1", 53),
    ("8.8.8.8", 53),
    ("www.youtube.com", 443),
)

# ---------------------------------------------------------- Dark theme -----
BG = "#1e1e1e"
BG_PANEL = "#252526"
BG_ENTRY = "#2d2d2e"
BG_LOG = "#121212"
FG = "#e6e6e6"
FG_MUTED = "#9a9a9a"
FG_LOG = "#d4d4d4"
BORDER = "#3c3c3c"
ACCENT = "#e5484d"
ACCENT_ACTIVE = "#c53f43"
SUCCESS = "#57c26a"
WARNING = "#e5b84d"
SCROLL_SPEED_MIN = 1
SCROLL_SPEED_MAX = 6
SCROLL_SPEED_DEFAULT = 1
PREVIEW_WIDTH = 420
PREVIEW_HEIGHT = 236


def clamp_scroll_speed(value):
    try:
        value = int(value)
    except (TypeError, ValueError):
        value = SCROLL_SPEED_DEFAULT
    return max(SCROLL_SPEED_MIN, min(SCROLL_SPEED_MAX, value))


class UndoEntry(tk.Entry):
    """Entry widget with portable undo/redo support."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self._history = [self.get()]
        self._history_index = 0
        self._internal_edit = False
        self.bind("<KeyRelease>", self._capture_edit, add="+")
        self.bind("<<Cut>>", self._capture_after_virtual_edit, add="+")
        self.bind("<<Paste>>", self._capture_after_virtual_edit, add="+")
        self.bind("<FocusIn>", self._sync_external_value, add="+")

    def _sync_external_value(self, _event=None):
        current = self.get()
        if current != self._history[self._history_index]:
            self._history = [current]
            self._history_index = 0

    def _capture_after_virtual_edit(self, _event=None):
        self.after_idle(self._capture_edit)

    def _capture_edit(self, _event=None):
        if self._internal_edit:
            return
        current = self.get()
        if current == self._history[self._history_index]:
            return
        if self._history_index < len(self._history) - 1:
            self._history = self._history[:self._history_index + 1]
        self._history.append(current)
        self._history_index += 1

    def _restore_history_value(self, index):
        self._internal_edit = True
        try:
            self.delete(0, "end")
            self.insert(0, self._history[index])
        finally:
            self._internal_edit = False

    def edit_undo(self):
        self._sync_external_value()
        if self._history_index > 0:
            self._history_index -= 1
            self._restore_history_value(self._history_index)

    def edit_redo(self):
        self._sync_external_value()
        if self._history_index < len(self._history) - 1:
            self._history_index += 1
            self._restore_history_value(self._history_index)


def format_rate(bytes_per_second):
    """Format a transfer rate using compact units suitable for the status bar."""
    if not bytes_per_second:
        return "0 B/s"
    value = float(bytes_per_second)
    for unit in ("B/s", "KB/s", "MB/s", "GB/s"):
        if value < 1024 or unit == "GB/s":
            return f"{value:.1f} {unit}"
        value /= 1024


def format_bytes(byte_count):
    """Format a byte count for compact progress information."""
    if not byte_count:
        return "0 B"
    value = float(byte_count)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{value:.1f} {unit}"
        value /= 1024


class Tooltip:
    """Small animated help popup shown when the pointer rests over a widget."""

    def __init__(self, widget, text, delay_ms=300):
        self.widget = widget
        self.text = text
        self.delay_ms = delay_ms
        self.window = None
        self.show_after_id = None
        self.fade_id = None
        widget.bind("<Enter>", self._on_enter, add="+")
        widget.bind("<Leave>", self._on_leave, add="+")

    def _on_enter(self, _event=None):
        self._cancel_timer("show_after_id")
        self._cancel_timer("fade_id")
        self.show_after_id = self.widget.after(self.delay_ms, self._show)

    def _on_leave(self, _event=None):
        self._cancel_timer("show_after_id")
        if self.window is not None:
            self._fade_out()

    def _cancel_timer(self, attribute):
        timer_id = getattr(self, attribute)
        if timer_id is not None:
            try:
                self.widget.after_cancel(timer_id)
            except tk.TclError:
                pass
            setattr(self, attribute, None)

    def _show(self):
        self.show_after_id = None
        if self.window is not None:
            self._fade_in()
            return
        try:
            window = tk.Toplevel(self.widget)
            window.overrideredirect(True)
            window.attributes("-topmost", True)
            window.configure(bg="#101010")
            label = tk.Label(
                window, text=self.text, justify="left", wraplength=360,
                bg="#101010", fg="#f4f4f4", padx=12, pady=8,
                relief="solid", bd=1, highlightthickness=1,
                highlightbackground="#555555", font=("Segoe UI", 10),
            )
            label.pack()
            window.update_idletasks()
            x = self.widget.winfo_rootx()
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + 8
            screen_w = self.widget.winfo_screenwidth()
            popup_w = window.winfo_reqwidth()
            if x + popup_w > screen_w - 8:
                x = max(8, screen_w - popup_w - 8)
            window.geometry(f"+{x}+{y}")
            self.window = window
            try:
                window.attributes("-alpha", 0.0)
            except tk.TclError:
                pass
            self._fade_in()
        except tk.TclError:
            self.window = None

    def _fade_in(self, alpha=0.0):
        if self.window is None or not self.window.winfo_exists():
            return
        alpha = min(alpha + 0.12, 1.0)
        try:
            self.window.attributes("-alpha", alpha)
        except tk.TclError:
            alpha = 1.0
        if alpha < 1.0:
            self.fade_id = self.widget.after(18, self._fade_in, alpha)

    def _fade_out(self, alpha=1.0):
        if self.window is None:
            return
        self._cancel_timer("fade_id")
        alpha -= 0.16
        if alpha <= 0.0:
            try:
                self.window.destroy()
            except tk.TclError:
                pass
            self.window = None
            return
        try:
            self.window.attributes("-alpha", alpha)
        except tk.TclError:
            alpha = 0.0
        self.fade_id = self.widget.after(18, self._fade_out, alpha)


def get_app_dir():
    """Folder the running exe (or script) lives in - used to look for a bundled ffmpeg."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def find_ffmpeg():
    """Best-effort auto-detect of ffmpeg so most people never have to set it manually."""
    candidates = []

    which_result = shutil.which("ffmpeg")
    if which_result:
        candidates.append(which_result)

    app_dir = get_app_dir()
    executable_names = ["ffmpeg.exe", "ffmpeg"] if sys.platform == "win32" else ["ffmpeg"]
    for executable_name in executable_names:
        candidates += [
            os.path.join(app_dir, "ffmpeg", "bin", executable_name),
            os.path.join(app_dir, "ffmpeg", executable_name),
            os.path.join(app_dir, executable_name),
        ]
    if sys.platform == "win32":
        candidates += [
            r"C:\ffmpeg\bin\ffmpeg.exe",
            r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
            r"C:\Program Files (x86)\ffmpeg\bin\ffmpeg.exe",
        ]
    elif sys.platform == "darwin":
        candidates += ["/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg"]
    else:
        candidates += ["/usr/bin/ffmpeg", "/usr/local/bin/ffmpeg"]
    for c in candidates:
        if c and os.path.isfile(c) and os.access(c, os.X_OK):
            return c
    return ""


def load_config():
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_config(data):
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except Exception:
        pass


def is_internet_up(timeout=3):
    for host, port in CONNECTIVITY_ENDPOINTS:
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True
        except OSError:
            continue
    return False


class _ConnectionLostError(Exception):
    """Raised internally when we detect the internet dropped mid-download."""
    pass


_CONNECTION_ERROR_HINTS = (
    "urlopen error", "timed out", "connection reset", "connection aborted",
    "network is unreachable", "temporary failure in name resolution",
    "failed to establish a new connection", "remote end closed connection",
    "getaddrinfo failed", "10054", "10060", "10061",
)


def _looks_like_connection_error(err):
    text = str(err).lower()
    return any(hint in text for hint in _CONNECTION_ERROR_HINTS)


def explain_download_error(err):
    """Turn common extractor failures into actionable, user-facing messages."""
    text = str(err)
    lower = text.lower()
    if "drm" in lower or "encrypted" in lower:
        return "DRM-protected content cannot be downloaded by this app."
    if "members-only" in lower or "member only" in lower or "private video" in lower:
        return "This content requires account access. Select browser cookies or a cookies.txt file."
    if "sign in" in lower or "login" in lower or "age-restricted" in lower:
        return "This content requires sign-in or age verification. Select valid browser cookies or a cookies.txt file."
    if "not available in your country" in lower or "geo" in lower or "region" in lower:
        return "This content is region-restricted. Configure an appropriate proxy if you are authorized to access it."
    if "confirm you're not a bot" in lower or "captcha" in lower or "robot" in lower:
        return "The site requested bot verification. Try again later with valid browser cookies and an updated yt-dlp."
    if "live" in lower and "not currently available" in lower:
        return "This live stream is not currently available to the extractor."
    return text


def _looks_like_cookie_database_error(err):
    text = str(err).lower()
    return (("could not copy" in text and "cookie" in text)
            or "cookie database" in text)


def _looks_like_subtitle_rate_limit(err):
    text = str(err).lower()
    return "subtitle" in text and ("429" in text or "too many requests" in text)


class GGUVDODApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_NAME)
        self.configure(bg=BG)

        # Open at 1920x1080 (auto-shrinks to fit the screen if the monitor is smaller),
        # centered, and resizable/maximizable from there.
        target_w, target_h = 1920, 1080
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        win_w = min(target_w, screen_w)
        win_h = min(target_h, screen_h)
        pos_x = max((screen_w - win_w) // 2, 0)
        pos_y = max((screen_h - win_h) // 2, 0)
        self.geometry(f"{win_w}x{win_h}+{pos_x}+{pos_y}")
        self.minsize(900, 650)

        config = load_config()

        self.format_var = tk.StringVar(value="video")
        self.quality_var = tk.StringVar(value=VIDEO_QUALITIES[0])
        self.output_var = tk.StringVar(value=config.get("output_dir") or get_default_output_dir())
        self.ffmpeg_var = tk.StringVar(value=config.get("ffmpeg_path") or find_ffmpeg())
        self.playlist_var = tk.BooleanVar(value=True)  # True = only download this video, not the whole playlist
        self.browser_var = tk.StringVar(value=config.get("cookies_browser", "None"))
        self.cookies_file_var = tk.StringVar(value=config.get("cookies_file", ""))
        self.proxy_var = tk.StringVar(value=config.get("proxy", ""))
        self.subtitles_var = tk.BooleanVar(value=config.get("subtitles", False))
        self.auto_subtitles_var = tk.BooleanVar(value=config.get("auto_subtitles", True))
        self.subtitle_langs_var = tk.StringVar(value=config.get("subtitle_languages", "en.*"))
        self.embed_metadata_var = tk.BooleanVar(value=config.get("embed_metadata", True))
        self.embed_thumbnail_var = tk.BooleanVar(value=config.get("embed_thumbnail", False))
        self.live_from_start_var = tk.BooleanVar(value=config.get("live_from_start", False))
        self.format_id_var = tk.StringVar(value=config.get("format_id", ""))

        self._cancel_requested = False
        self._download_settings = None
        self._playlist_seen = set()
        self._last_update_check = config.get("last_update_check", 0)
        self._tooltips = []
        self._failed_count = 0
        self.scroll_speed_var = tk.IntVar(value=clamp_scroll_speed(config.get("scroll_speed", SCROLL_SPEED_DEFAULT)))
        self._scroll_target = None
        self._scroll_animation_id = None
        self.preview_title_var = tk.StringVar(value="Paste a link to preview it")
        self.preview_details_var = tk.StringVar(value="Title, thumbnail, duration, uploader, and platform will appear here.")
        self.preview_status_var = tk.StringVar(value="Waiting for a link")
        self._preview_after_id = None
        self._preview_token = 0
        self._preview_photo = None
        self._supported_platform_lines = None
        self.download_status_var = tk.StringVar(value="Ready")
        self.download_rate_var = tk.StringVar(value="0 B/s")
        self.upload_rate_var = tk.StringVar(value="0 B/s")
        self.progress_summary_var = tk.StringVar(value="0%")
        self.transfer_summary_var = tk.StringVar(value="0 B / 0 B")
        self.eta_var = tk.StringVar(value="—")

        # Thread-safe UI update queue. The download worker thread NEVER touches
        # Tk widgets directly - it only pushes (callable, args) here, and a
        # periodic poll on the main thread drains it. This is what makes the
        # log panel and progress bar update reliably.
        self._ui_queue = queue.Queue()

        self._setup_style()
        self._build_ui()
        self._build_menu_bar()
        self._update_ffmpeg_status()

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.report_callback_exception = self._handle_tk_exception

        self.after(100, self._drain_queue)
        self.after(50, self._apply_windows_dark_titlebar)
        self.after(1500, self._auto_update_check)

    # ------------------------------------------------------------ styling --
    def _setup_style(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure("TCombobox",
                         fieldbackground=BG_ENTRY, background=BG_PANEL, foreground=FG,
                         arrowcolor=FG, bordercolor=BORDER, lightcolor=BG_ENTRY, darkcolor=BG_ENTRY,
                         selectbackground=BG_ENTRY, selectforeground=FG)
        style.map("TCombobox",
                  fieldbackground=[("readonly", BG_ENTRY)],
                  selectbackground=[("readonly", BG_ENTRY)],
                  selectforeground=[("readonly", FG)],
                  foreground=[("readonly", FG)])

        style.configure("TProgressbar",
                         troughcolor=BG_PANEL, background=ACCENT, bordercolor=BG_PANEL,
                         lightcolor=ACCENT, darkcolor=ACCENT)

        # Dropdown listbox popup isn't a ttk widget - themed via option database.
        self.option_add("*TCombobox*Listbox.background", BG_ENTRY)
        self.option_add("*TCombobox*Listbox.foreground", FG)
        self.option_add("*TCombobox*Listbox.selectBackground", ACCENT)
        self.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")

    def _apply_windows_dark_titlebar(self):
        if sys.platform != "win32":
            return
        try:
            import ctypes
            hwnd = ctypes.windll.user32.GetParent(self.winfo_id())
            DWMWA_USE_IMMERSIVE_DARK_MODE = 20
            value = ctypes.c_int(1)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, ctypes.byref(value), ctypes.sizeof(value)
            )
        except Exception:
            pass

    # ------------------------------------------------------- widget helpers --
    def _label(self, parent, **kwargs):
        kwargs.setdefault("bg", parent.cget("bg") if isinstance(parent, (tk.Frame, tk.LabelFrame)) else BG)
        kwargs.setdefault("fg", FG)
        kwargs.setdefault("font", ("Segoe UI", 11))
        return tk.Label(parent, **kwargs)

    def _add_tooltip(self, widget, text):
        self._tooltips.append(Tooltip(widget, text))
        return widget

    def _add_context_menu(self, widget):
        widget.bind("<Button-3>", self._show_context_menu, add="+")
        widget.bind("<Control-z>", lambda event: self._edit_action(event, "undo"), add="+")
        widget.bind("<Control-y>", lambda event: self._edit_action(event, "redo"), add="+")
        widget.bind("<Control-Shift-Z>", lambda event: self._edit_action(event, "redo"), add="+")
        widget.bind("<Control-Alt-Z>", lambda event: self._edit_action(event, "redo"), add="+")
        return widget

    def _edit_action(self, event, action):
        try:
            if action == "undo":
                event.widget.edit_undo()
            else:
                event.widget.edit_redo()
        except tk.TclError:
            pass
        return "break"

    def _show_context_menu(self, event):
        widget = event.widget
        menu = tk.Menu(self, tearoff=False, bg=BG_PANEL, fg=FG,
                       activebackground=ACCENT, activeforeground="#ffffff")
        menu.add_command(label="Undo", accelerator="Ctrl+Z",
                         command=lambda: self._edit_action_for_widget(widget, "undo"))
        menu.add_command(label="Redo", accelerator="Ctrl+Y",
                         command=lambda: self._edit_action_for_widget(widget, "redo"))
        menu.add_separator()
        menu.add_command(label="Cut", command=lambda: widget.event_generate("<<Cut>>"))
        menu.add_command(label="Copy", command=lambda: widget.event_generate("<<Copy>>"))
        menu.add_command(label="Paste", command=lambda: widget.event_generate("<<Paste>>"))
        menu.add_separator()
        menu.add_command(label="Select all", command=lambda: widget.event_generate("<<SelectAll>>"))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _edit_action_for_widget(self, widget, action):
        try:
            if action == "undo":
                widget.edit_undo()
            else:
                widget.edit_redo()
        except tk.TclError:
            pass

    def _frame(self, parent, **kwargs):
        kwargs.setdefault("bg", BG)
        return tk.Frame(parent, **kwargs)

    def _labelframe(self, parent, text, **kwargs):
        kwargs.setdefault("bg", BG_PANEL)
        kwargs.setdefault("fg", FG_MUTED)
        kwargs.setdefault("font", ("Segoe UI", 11, "bold"))
        kwargs.setdefault("relief", "flat")
        kwargs.setdefault("bd", 1)
        kwargs.setdefault("highlightbackground", BORDER)
        kwargs.setdefault("highlightthickness", 1)
        return tk.LabelFrame(parent, text=text, **kwargs)

    def _entry(self, parent, textvariable, **kwargs):
        kwargs.setdefault("bg", BG_ENTRY)
        kwargs.setdefault("fg", FG)
        kwargs.setdefault("insertbackground", FG)
        kwargs.setdefault("relief", "flat")
        kwargs.setdefault("bd", 0)
        kwargs.setdefault("highlightthickness", 1)
        kwargs.setdefault("highlightbackground", BORDER)
        kwargs.setdefault("highlightcolor", ACCENT)
        kwargs.setdefault("font", ("Segoe UI", 11))
        return self._add_context_menu(UndoEntry(parent, textvariable=textvariable, **kwargs))

    def _button(self, parent, text, command, primary=False, **kwargs):
        if primary:
            kwargs.setdefault("bg", ACCENT)
            kwargs.setdefault("activebackground", ACCENT_ACTIVE)
            kwargs.setdefault("fg", "#ffffff")
            kwargs.setdefault("activeforeground", "#ffffff")
            kwargs.setdefault("font", ("Segoe UI", 13, "bold"))
        else:
            kwargs.setdefault("bg", BG_ENTRY)
            kwargs.setdefault("activebackground", BORDER)
            kwargs.setdefault("fg", FG)
            kwargs.setdefault("activeforeground", FG)
            kwargs.setdefault("font", ("Segoe UI", 10))
        kwargs.setdefault("relief", "flat")
        kwargs.setdefault("bd", 0)
        kwargs.setdefault("highlightthickness", 0)
        kwargs.setdefault("cursor", "hand2")
        kwargs.setdefault("disabledforeground", FG_MUTED)
        return tk.Button(parent, text=text, command=command, **kwargs)

    def _radio(self, parent, **kwargs):
        kwargs.setdefault("bg", parent.cget("bg"))
        kwargs.setdefault("fg", FG)
        kwargs.setdefault("selectcolor", BG_ENTRY)
        kwargs.setdefault("activebackground", parent.cget("bg"))
        kwargs.setdefault("activeforeground", FG)
        kwargs.setdefault("font", ("Segoe UI", 11))
        kwargs.setdefault("highlightthickness", 0)
        return tk.Radiobutton(parent, **kwargs)

    def _check(self, parent, **kwargs):
        kwargs.setdefault("bg", parent.cget("bg"))
        kwargs.setdefault("fg", FG)
        kwargs.setdefault("selectcolor", BG_ENTRY)
        kwargs.setdefault("activebackground", parent.cget("bg"))
        kwargs.setdefault("activeforeground", FG)
        kwargs.setdefault("font", ("Segoe UI", 11))
        kwargs.setdefault("highlightthickness", 0)
        return tk.Checkbutton(parent, **kwargs)

    def _scrolled_text(self, parent, bg, fg, **kwargs):
        kwargs.setdefault("bg", bg)
        kwargs.setdefault("fg", fg)
        kwargs.setdefault("insertbackground", fg)
        kwargs.setdefault("relief", "flat")
        kwargs.setdefault("bd", 0)
        kwargs.setdefault("highlightthickness", 1)
        kwargs.setdefault("highlightbackground", BORDER)
        kwargs.setdefault("undo", True)
        kwargs.setdefault("maxundo", 1000)
        widget = scrolledtext.ScrolledText(parent, **kwargs)
        try:
            widget.vbar.configure(bg=BG_PANEL, troughcolor=BG, activebackground=BORDER,
                                   highlightthickness=0, bd=0, relief="flat")
        except Exception:
            pass
        return self._add_context_menu(widget)

    # ---------------------------------------------------------- UI build --
    def _build_ui(self):
        pad = {"padx": 24, "pady": 10}

        # Keep the transfer summary fixed at the bottom while the main content scrolls.
        self._build_status_bar()

        scroll_area = self._frame(self)
        scroll_area.pack(fill="both", expand=True)
        self.main_canvas = tk.Canvas(scroll_area, bg=BG, highlightthickness=0,
                                     yscrollincrement=1)
        main_scrollbar = ttk.Scrollbar(scroll_area, orient="vertical", command=self.main_canvas.yview)
        self.main_canvas.configure(yscrollcommand=main_scrollbar.set)
        self.main_canvas.pack(side="left", fill="both", expand=True)
        main_scrollbar.pack(side="right", fill="y")

        # Center column so the UI doesn't stretch edge-to-edge on a wide window.
        container = self._frame(self.main_canvas)
        canvas_window = self.main_canvas.create_window((0, 0), window=container, anchor="nw")
        container.bind("<Configure>", lambda _event: self.main_canvas.configure(
            scrollregion=self.main_canvas.bbox("all")))
        self.main_canvas.bind("<Configure>", lambda event: self.main_canvas.itemconfigure(
            canvas_window, width=max(event.width, 1200)))
        self.main_canvas.bind_all("<MouseWheel>", self._scroll_main, add="+")
        self.main_canvas.bind_all("<Button-4>", self._scroll_main, add="+")
        self.main_canvas.bind_all("<Button-5>", self._scroll_main, add="+")

        container.grid_columnconfigure(0, weight=1)
        container.grid_columnconfigure(1, weight=0, minsize=1200)
        container.grid_columnconfigure(2, weight=1)
        container.grid_rowconfigure(0, weight=1)

        content = self._frame(container)
        content.grid(row=0, column=1, sticky="nsew")

        title_label = self._label(content, text=APP_NAME, font=("Segoe UI", 28, "bold"))
        title_label.pack(pady=(26, 6))
        self._add_tooltip(title_label, "GGU_VDOD downloads video or audio from links you provide.")
        guide_label = self._label(content, text="Paste one or more video links below (one per line)",
                                  font=("Segoe UI", 12), fg=FG_MUTED)
        guide_label.pack()
        self._add_tooltip(guide_label, "Paste one link per line. You can download several links in one queue.")

        self.url_text = self._scrolled_text(content, BG_ENTRY, FG, height=5, wrap="word", font=("Segoe UI", 12))
        self.url_text.pack(fill="x", **pad)
        self._add_tooltip(self.url_text, "Enter the video, playlist, or live-stream URL you want to process.")
        self.url_text.bind("<<Modified>>", self._on_url_modified, add="+")
        self.url_text.edit_modified(False)

        preview_frame = self._labelframe(content, "Video preview", padx=16, pady=12)
        preview_frame.pack(fill="x", **pad)
        preview_row = self._frame(preview_frame, bg=BG_PANEL)
        preview_row.pack(fill="x")
        self.preview_image_label = tk.Label(
            preview_row, text="No preview", width=PREVIEW_WIDTH, height=PREVIEW_HEIGHT,
            bg=BG_ENTRY, fg=FG_MUTED, relief="flat", font=("Segoe UI", 10),
            anchor="center",
        )
        self.preview_image_label.pack(side="left", padx=(0, 16))
        preview_text = self._frame(preview_row, bg=BG_PANEL)
        preview_text.pack(side="left", fill="both", expand=True)
        preview_title = self._label(preview_text, textvariable=self.preview_title_var,
                                    bg=BG_PANEL, fg=FG, anchor="w",
                                    justify="left", wraplength=820,
                                    font=("Segoe UI", 14, "bold"))
        preview_title.pack(fill="x", pady=(4, 8))
        self._add_tooltip(preview_title, "The title and metadata are read from the first link in the box.")
        preview_details = self._label(preview_text, textvariable=self.preview_details_var,
                                      bg=BG_PANEL, fg=FG_MUTED, anchor="nw",
                                      justify="left", wraplength=820,
                                      font=("Segoe UI", 10))
        preview_details.pack(fill="x")
        preview_status = self._label(preview_text, textvariable=self.preview_status_var,
                                     bg=BG_PANEL, fg=FG_MUTED, anchor="w",
                                     font=("Segoe UI", 9))
        preview_status.pack(fill="x", pady=(10, 0))

        # Format + quality
        fmt_frame = self._labelframe(content, "Format", padx=16, pady=12)
        fmt_frame.pack(fill="x", **pad)

        video_radio = self._radio(fmt_frame, text="Video (MP4)", variable=self.format_var, value="video",
                                  command=self._toggle_format)
        video_radio.grid(row=0, column=0, sticky="w", padx=(0, 30))
        self._add_tooltip(video_radio, "Download video and save it as an MP4 when the available formats allow it.")
        audio_radio = self._radio(fmt_frame, text="Audio only (MP3)", variable=self.format_var, value="audio",
                                  command=self._toggle_format)
        audio_radio.grid(row=0, column=1, sticky="w")
        self._add_tooltip(audio_radio, "Extract the audio and convert it to an MP3 file using ffmpeg.")

        quality_label = self._label(fmt_frame, text="Quality:", bg=BG_PANEL)
        quality_label.grid(row=1, column=0, sticky="w", pady=(12, 0))
        self._add_tooltip(quality_label, "Choose the highest quality the app should try to use.")
        self.quality_combo = ttk.Combobox(fmt_frame, textvariable=self.quality_var, values=VIDEO_QUALITIES,
                                           state="readonly", width=22, font=("Segoe UI", 11))
        self.quality_combo.grid(row=1, column=1, sticky="w", pady=(12, 0))
        self._add_tooltip(self.quality_combo, "The final choice depends on the formats available for that specific link.")

        playlist_check = self._check(fmt_frame, text="Only download this video (ignore playlist)",
                                     variable=self.playlist_var)
        playlist_check.grid(row=2, column=0, columnspan=2, sticky="w", pady=(12, 0))
        self._add_tooltip(playlist_check, "When enabled, a playlist URL downloads only the selected video.")

        # Output folder
        out_frame = self._labelframe(content, "Save to", padx=16, pady=12)
        out_frame.pack(fill="x", **pad)
        out_row = self._frame(out_frame, bg=BG_PANEL)
        out_row.pack(fill="x")
        output_entry = self._entry(out_row, textvariable=self.output_var)
        output_entry.pack(side="left", fill="x", expand=True, ipady=4)
        self._add_tooltip(output_entry, "Files are saved in this folder. The folder is created if it does not exist.")
        output_browse = self._button(out_row, "Browse...", self._browse_output)
        output_browse.pack(side="left", padx=(10, 0))
        self._add_tooltip(output_browse, "Choose a folder where downloaded files should be saved.")

        # ffmpeg path (auto-detected by default; editable)
        ff_frame = self._labelframe(content, "ffmpeg location (auto-detected - change only if needed)",
                                     padx=16, pady=12)
        ff_frame.pack(fill="x", **pad)
        ff_row = self._frame(ff_frame, bg=BG_PANEL)
        ff_row.pack(fill="x")
        self._add_tooltip(ff_frame, "ffmpeg merges separate video and audio streams and creates MP3 files.")
        ffmpeg_entry = self._entry(ff_row, textvariable=self.ffmpeg_var)
        ffmpeg_entry.pack(side="left", fill="x", expand=True, ipady=4)
        self._add_tooltip(ffmpeg_entry, "Leave this path automatic, or select the ffmpeg executable manually.")
        ffmpeg_browse = self._button(ff_row, "Browse...", self._browse_ffmpeg)
        ffmpeg_browse.pack(side="left", padx=(10, 0))
        self._add_tooltip(ffmpeg_browse, "Find the ffmpeg executable on your computer.")
        self.ffmpeg_status_label = self._label(ff_frame, text="", bg=BG_PANEL, font=("Segoe UI", 9))
        self.ffmpeg_status_label.pack(anchor="w", pady=(8, 0))
        self.ffmpeg_var.trace_add("write", lambda *a: self._update_ffmpeg_status())

        # Authentication and output options
        options_frame = self._labelframe(content, "Authentication and output options", padx=16, pady=12)
        options_frame.pack(fill="x", **pad)

        auth_row = self._frame(options_frame, bg=BG_PANEL)
        auth_row.pack(fill="x", pady=(0, 8))
        browser_label = self._label(auth_row, text="Browser cookies:", bg=BG_PANEL)
        browser_label.pack(side="left")
        self._add_tooltip(browser_label, "Use cookies from a browser where you are already signed in.")
        browser_combo = ttk.Combobox(auth_row, textvariable=self.browser_var, values=COOKIE_BROWSERS,
                                     state="readonly", width=14, font=("Segoe UI", 11))
        browser_combo.pack(side="left", padx=(10, 20))
        self._add_tooltip(browser_combo, "Choose the browser whose active login should be used by yt-dlp.")
        cookies_label = self._label(auth_row, text="Cookies file:", bg=BG_PANEL)
        cookies_label.pack(side="left")
        self._add_tooltip(cookies_label, "Use a Netscape-format cookies.txt file when browser cookies are not enough.")
        cookies_entry = self._entry(auth_row, textvariable=self.cookies_file_var)
        cookies_entry.pack(side="left", fill="x", expand=True, padx=(10, 0), ipady=4)
        self._add_tooltip(cookies_entry, "Optional path to a cookies.txt file.")
        cookies_browse = self._button(auth_row, "Browse...", self._browse_cookies)
        cookies_browse.pack(side="left", padx=(10, 0))
        self._add_tooltip(cookies_browse, "Choose a cookies.txt file.")

        proxy_row = self._frame(options_frame, bg=BG_PANEL)
        proxy_row.pack(fill="x", pady=(0, 8))
        proxy_label = self._label(proxy_row, text="Proxy (optional):", bg=BG_PANEL)
        proxy_label.pack(side="left")
        self._add_tooltip(proxy_label, "A proxy can help with network routing or region restrictions when authorized.")
        proxy_entry = self._entry(proxy_row, textvariable=self.proxy_var)
        proxy_entry.pack(side="left", fill="x", expand=True, padx=(10, 10), ipady=4)
        self._add_tooltip(proxy_entry, "Enter a proxy such as http://user:pass@host:port or socks5://host:port.")
        proxy_hint = self._label(proxy_row, text="Example: http://user:pass@host:port", bg=BG_PANEL,
                                 fg=FG_MUTED, font=("Segoe UI", 9))
        proxy_hint.pack(side="left")
        self._add_tooltip(proxy_hint, "The proxy address should include its protocol and port.")
        update_button = self._button(proxy_row, "Check yt-dlp updates", self._check_for_updates)
        update_button.pack(side="right", padx=(10, 0))
        self._add_tooltip(update_button, "Check whether a newer yt-dlp version is available.")

        subtitle_row = self._frame(options_frame, bg=BG_PANEL)
        subtitle_row.pack(fill="x", pady=(0, 8))
        subtitles_check = self._check(subtitle_row, text="Download subtitles", variable=self.subtitles_var)
        subtitles_check.pack(side="left")
        self._add_tooltip(subtitles_check, "Download and embed subtitles when the source provides them.")
        auto_subtitles_check = self._check(subtitle_row, text="Include auto-generated", variable=self.auto_subtitles_var)
        auto_subtitles_check.pack(side="left", padx=(18, 0))
        self._add_tooltip(auto_subtitles_check, "Also accept captions generated automatically by the source.")
        languages_label = self._label(subtitle_row, text="Languages:", bg=BG_PANEL)
        languages_label.pack(side="left", padx=(18, 0))
        self._add_tooltip(languages_label, "Enter language codes separated by commas, for example en.*,hi.")
        languages_entry = self._entry(subtitle_row, textvariable=self.subtitle_langs_var, width=18)
        languages_entry.pack(side="left", padx=(8, 0), ipady=4)
        self._add_tooltip(languages_entry, "Choose subtitle languages using codes such as en.*, hi, or all.")
        metadata_check = self._check(subtitle_row, text="Embed metadata", variable=self.embed_metadata_var)
        metadata_check.pack(side="left", padx=(18, 0))
        self._add_tooltip(metadata_check, "Add the title, artist, and other available information to the media file.")
        thumbnail_check = self._check(subtitle_row, text="Embed thumbnail", variable=self.embed_thumbnail_var)
        thumbnail_check.pack(side="left", padx=(18, 0))
        self._add_tooltip(thumbnail_check, "Use the source thumbnail as the media cover image when supported.")
        live_check = self._check(subtitle_row, text="Live: start from beginning", variable=self.live_from_start_var)
        live_check.pack(side="left", padx=(18, 0))
        self._add_tooltip(live_check, "For supported live streams, ask yt-dlp to capture from the beginning.")

        format_row = self._frame(options_frame, bg=BG_PANEL)
        format_row.pack(fill="x")
        format_label = self._label(format_row, text="Exact format ID(s) (optional):", bg=BG_PANEL)
        format_label.pack(side="left")
        self._add_tooltip(format_label, "Leave blank for automatic quality selection, or enter IDs such as 137+140.")
        format_entry = self._entry(format_row, textvariable=self.format_id_var)
        format_entry.pack(side="left", fill="x", expand=True, padx=(10, 10), ipady=4)
        self._add_tooltip(format_entry, "Use List formats first, then enter the exact format ID or combination you want.")
        list_formats_button = self._button(format_row, "List formats", self._list_formats)
        list_formats_button.pack(side="left")
        self._add_tooltip(list_formats_button, "Inspect the formats reported for the first URL in the link box.")

        # Buttons
        btn_frame = self._frame(content)
        btn_frame.pack(fill="x", **pad)
        self.download_btn = self._button(btn_frame, "Download", self._start_download, primary=True)
        self.download_btn.pack(side="left", ipadx=30, ipady=10)
        self._add_tooltip(self.download_btn, "Start downloading all links in the box using the selected options.")
        self.cancel_btn = self._button(btn_frame, "Cancel", self._cancel_download, state="disabled")
        self.cancel_btn.pack(side="left", padx=(14, 0), ipady=6)
        self._add_tooltip(self.cancel_btn, "Stop after the current download operation and keep partial files for later.")
        open_folder_button = self._button(btn_frame, "Open Save Folder", self._open_output_folder)
        open_folder_button.pack(side="left", padx=(14, 0), ipady=6)
        self._add_tooltip(open_folder_button, "Open the selected save folder in your system file browser.")

        # Progress
        prog_frame = self._frame(content)
        prog_frame.pack(fill="x", **pad)
        self.progress = ttk.Progressbar(prog_frame, orient="horizontal", mode="determinate", maximum=100)
        self.progress.pack(fill="x", ipady=4)
        self._add_tooltip(self.progress, "Shows download progress for the current video or playlist item.")

        self.status_label = self._label(content, text="Ready.", fg=FG_MUTED, anchor="w")
        self.status_label.pack(fill="x", padx=24)
        self._add_tooltip(self.status_label, "Current activity, speed, estimated time, and connection status appear here.")

        # Log
        log_frame = self._labelframe(content, "Log", padx=10, pady=10)
        log_frame.pack(fill="both", expand=True, **pad)
        self.log_box = self._scrolled_text(log_frame, BG_LOG, FG_LOG, height=12, state="disabled",
                                            font=("Consolas", 11))
        self.log_box.pack(fill="both", expand=True)
        self._add_tooltip(log_frame, "The log records each link, playlist item, retry, conversion, and error.")

    def _build_menu_bar(self):
        menu_bar = tk.Menu(self)

        file_menu = tk.Menu(menu_bar, tearoff=False)
        file_menu.add_command(label="New link list", accelerator="Ctrl+N", command=self._new_link_list)
        file_menu.add_command(label="Open save folder", command=self._open_output_folder)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", accelerator="Alt+F4", command=self._on_close)
        menu_bar.add_cascade(label="File", menu=file_menu)

        edit_menu = tk.Menu(menu_bar, tearoff=False)
        edit_menu.add_command(label="Undo", accelerator="Ctrl+Z", command=lambda: self._edit_focused("undo"))
        edit_menu.add_command(label="Redo", accelerator="Ctrl+Y", command=lambda: self._edit_focused("redo"))
        edit_menu.add_separator()
        edit_menu.add_command(label="Cut", accelerator="Ctrl+X", command=lambda: self._edit_focused("cut"))
        edit_menu.add_command(label="Copy", accelerator="Ctrl+C", command=lambda: self._edit_focused("copy"))
        edit_menu.add_command(label="Paste", accelerator="Ctrl+V", command=lambda: self._edit_focused("paste"))
        edit_menu.add_command(label="Select all", accelerator="Ctrl+A", command=lambda: self._edit_focused("select_all"))
        preferences_menu = tk.Menu(edit_menu, tearoff=False)
        preferences_menu.add_command(label="Key bindings and scroll speed...",
                                     command=self._show_key_bindings_preferences)
        edit_menu.add_cascade(label="Preferences", menu=preferences_menu)
        menu_bar.add_cascade(label="Edit", menu=edit_menu)

        view_menu = tk.Menu(menu_bar, tearoff=False)
        view_menu.add_command(label="Scroll to top", command=lambda: self._set_scroll_position(0.0))
        view_menu.add_command(label="Scroll to bottom", command=lambda: self._set_scroll_position(1.0))
        view_menu.add_separator()
        view_menu.add_command(label="Reset scroll speed", command=self._reset_scroll_speed)
        menu_bar.add_cascade(label="View", menu=view_menu)

        window_menu = tk.Menu(menu_bar, tearoff=False)
        window_menu.add_command(label="Minimize", command=lambda: self.state("iconic"))
        window_menu.add_command(label="Maximize", command=self._maximize_window)
        window_menu.add_command(label="Restore", command=lambda: self.state("normal"))
        menu_bar.add_cascade(label="Window", menu=window_menu)

        help_menu = tk.Menu(menu_bar, tearoff=False)
        help_menu.add_command(label="Keyboard shortcuts", command=self._show_shortcuts)
        help_menu.add_command(label="Supported platforms", command=self._show_supported_platforms)
        help_menu.add_command(label="Open README", command=self._open_readme)
        help_menu.add_command(label="Check for yt-dlp updates", command=self._check_for_updates)
        menu_bar.add_cascade(label="Help", menu=help_menu)

        about_menu = tk.Menu(menu_bar, tearoff=False)
        about_menu.add_command(label="About GGU_VDOD", command=self._show_about)
        menu_bar.add_cascade(label="About", menu=about_menu)
        self.config(menu=menu_bar)

        self.bind("<Control-n>", lambda _event: self._new_link_list(), add="+")

    def _edit_focused(self, action):
        widget = self.focus_get()
        if widget is None:
            return
        try:
            if action == "undo":
                widget.edit_undo()
            elif action == "redo":
                widget.edit_redo()
            else:
                widget.event_generate({
                    "cut": "<<Cut>>",
                    "copy": "<<Copy>>",
                    "paste": "<<Paste>>",
                    "select_all": "<<SelectAll>>",
                }[action])
        except (tk.TclError, KeyError):
            pass

    def _new_link_list(self):
        self.url_text.focus_set()
        self.url_text.delete("1.0", "end")
        self.status_label.config(text="New link list ready.")

    def _set_scroll_position(self, position):
        self._scroll_target = position
        self.main_canvas.yview_moveto(position)

    def _reset_scroll_speed(self):
        self.scroll_speed_var.set(SCROLL_SPEED_DEFAULT)
        save_config(self._settings_from_ui())

    def _maximize_window(self):
        try:
            self.state("zoomed")
        except tk.TclError:
            self.attributes("-zoomed", True)

    def _show_key_bindings_preferences(self):
        dialog = tk.Toplevel(self)
        dialog.title("Preferences - Key Bindings")
        dialog.configure(bg=BG)
        dialog.transient(self)
        dialog.resizable(False, False)
        dialog.grab_set()

        body = self._frame(dialog, padx=20, pady=16)
        body.pack(fill="both", expand=True)
        title = self._label(body, text="Key bindings and scroll speed", font=("Segoe UI", 15, "bold"))
        title.pack(anchor="w", pady=(0, 12))

        speed_row = self._frame(body)
        speed_row.pack(fill="x", pady=(0, 14))
        self._label(speed_row, text="Scroll speed:").pack(side="left")
        dialog_speed = tk.IntVar(value=clamp_scroll_speed(self.scroll_speed_var.get()))
        speed_spinbox = ttk.Spinbox(speed_row, from_=SCROLL_SPEED_MIN, to=SCROLL_SPEED_MAX,
                                    textvariable=dialog_speed, width=5, state="readonly")
        speed_spinbox.pack(side="left", padx=(12, 8))
        self._label(speed_row, text="1 slow  ·  6 fast", fg=FG_MUTED,
                    font=("Segoe UI", 9)).pack(side="left")

        self._label(body, text="Text editing shortcuts", font=("Segoe UI", 11, "bold")).pack(anchor="w")
        shortcuts = (
            ("Undo", "Ctrl+Z"),
            ("Redo", "Ctrl+Y  /  Ctrl+Shift+Z  /  Ctrl+Alt+Z"),
            ("Cut", "Ctrl+X"),
            ("Copy", "Ctrl+C"),
            ("Paste", "Ctrl+V"),
            ("Select all", "Ctrl+A"),
        )
        for name, binding in shortcuts:
            row = self._frame(body)
            row.pack(fill="x", pady=2)
            self._label(row, text=name, width=14, anchor="w").pack(side="left")
            self._label(row, text=binding, fg=FG_MUTED, anchor="w").pack(side="left")

        button_row = self._frame(body)
        button_row.pack(fill="x", pady=(16, 0))
        self._button(button_row, "Cancel", dialog.destroy).pack(side="right")

        def apply_preferences():
            self.scroll_speed_var.set(clamp_scroll_speed(dialog_speed.get()))
            save_config(self._settings_from_ui())
            dialog.destroy()

        self._button(button_row, "Apply", apply_preferences, primary=True).pack(side="right", padx=(0, 10))

    def _show_shortcuts(self):
        messagebox.showinfo(
            "Keyboard shortcuts",
            "Ctrl+Z  Undo\n"
            "Ctrl+Y / Ctrl+Shift+Z / Ctrl+Alt+Z  Redo\n"
            "Ctrl+X  Cut\nCtrl+C  Copy\nCtrl+V  Paste\nCtrl+A  Select all\n"
            "Ctrl+N  New link list",
        )

    def _show_supported_platforms(self):
        dialog = tk.Toplevel(self)
        dialog.title("Supported platforms and extractors")
        dialog.configure(bg=BG)
        dialog.transient(self)
        dialog.geometry("820x620")

        header = self._frame(dialog, padx=16, pady=12)
        header.pack(fill="x")
        self._label(
            header,
            text="Platforms supported by this installed yt-dlp build",
            font=("Segoe UI", 14, "bold"),
        ).pack(anchor="w")
        self._label(
            header,
            text="Support changes over time and individual sites may be broken, restricted, or require cookies.",
            fg=FG_MUTED,
            font=("Segoe UI", 9),
        ).pack(anchor="w", pady=(4, 8))
        search_var = tk.StringVar()
        search_entry = self._entry(header, textvariable=search_var)
        search_entry.pack(fill="x", ipady=4)
        self._add_tooltip(search_entry, "Filter the installed extractor list by site or platform name.")

        listing = self._scrolled_text(dialog, BG_LOG, FG_LOG, state="disabled",
                                      wrap="none", font=("Consolas", 10))
        listing.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        self._supported_platform_widget = listing
        self._supported_platform_search = search_var
        search_var.trace_add("write", lambda *_args: self._render_supported_platforms(search_var.get()))

        if self._supported_platform_lines is None:
            self._supported_platform_widget.configure(state="normal")
            self._supported_platform_widget.insert("end", "Loading installed extractors...\n")
            self._supported_platform_widget.configure(state="disabled")
            threading.Thread(target=self._load_supported_platforms, args=(dialog,), daemon=True).start()
        else:
            self._render_supported_platforms("")

    def _load_supported_platforms(self, dialog):
        try:
            from yt_dlp.extractor import gen_extractors
            lines = sorted({
                f"{extractor.IE_NAME}"
                + (f" — {extractor.IE_DESC}" if extractor.IE_DESC else "")
                for extractor in gen_extractors()
            }, key=str.casefold)
            self._enqueue(self._set_supported_platforms, dialog, lines)
        except Exception as error:
            self._enqueue(self._apply_supported_platform_error, dialog, str(error))

    def _set_supported_platforms(self, dialog, lines):
        if not dialog.winfo_exists():
            return
        self._supported_platform_lines = lines
        self._render_supported_platforms(self._supported_platform_search.get())

    def _apply_supported_platform_error(self, dialog, error):
        if not dialog.winfo_exists():
            return
        self._supported_platform_lines = [f"Could not load extractor list: {error}"]
        self._render_supported_platforms("")

    def _render_supported_platforms(self, query):
        if not hasattr(self, "_supported_platform_widget") or self._supported_platform_lines is None:
            return
        query = (query or "").casefold().strip()
        lines = [line for line in self._supported_platform_lines if not query or query in line.casefold()]
        widget = self._supported_platform_widget
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("end", f"{len(lines)} matching extractor(s)\n\n")
        widget.insert("end", "\n".join(lines))
        widget.configure(state="disabled")

    def _open_readme(self):
        readme = os.path.join(get_app_dir(), "README.md")
        if os.path.isfile(readme):
            try:
                if sys.platform == "win32":
                    os.startfile(readme)
                elif sys.platform == "darwin":
                    subprocess.Popen(["open", readme])
                else:
                    subprocess.Popen(["xdg-open", readme])
            except OSError as e:
                messagebox.showerror("Couldn't open README", str(e))
        else:
            messagebox.showinfo("README", "README.md is available in the project folder.")

    def _show_about(self):
        messagebox.showinfo(
            "About GGU_VDOD",
            "GGU_VDOD\n\n"
            "A dark-themed yt-dlp desktop downloader with resumable downloads, subtitles, "
            "metadata, cookies, proxy support, animated help, and traditional desktop menus.",
        )

    def _build_status_bar(self):
        status_bar = tk.Frame(self, bg="#171717", height=38, bd=0,
                              highlightthickness=1, highlightbackground=BORDER)
        status_bar.pack(side="bottom", fill="x")
        status_bar.pack_propagate(False)

        def add_cell(caption, variable, width, tooltip):
            cell = tk.Frame(status_bar, bg="#171717", width=width)
            cell.pack(side="left", fill="y", padx=(10, 0))
            cell.pack_propagate(False)
            label = tk.Label(cell, text=caption, bg="#171717", fg=FG_MUTED,
                             font=("Segoe UI", 9, "bold"), anchor="w")
            label.pack(side="left")
            value = tk.Label(cell, textvariable=variable, bg="#171717", fg=FG,
                             font=("Segoe UI", 9), anchor="w")
            value.pack(side="left", padx=(5, 0))
            self._add_tooltip(cell, tooltip)

        add_cell("Status:", self.download_status_var, 250,
                 "The current queue state, such as ready, downloading, retrying, or complete.")
        add_cell("↓ Download:", self.download_rate_var, 145,
                 "Current download speed reported by yt-dlp.")
        add_cell("↑ Upload:", self.upload_rate_var, 145,
                 "This application only downloads, so its upload rate remains 0 B/s.")
        add_cell("Progress:", self.progress_summary_var, 110,
                 "Percentage completed for the current download item.")
        add_cell("Transferred:", self.transfer_summary_var, 170,
                 "Downloaded bytes compared with the available file size estimate.")
        add_cell("ETA:", self.eta_var, 100,
                 "Estimated time remaining when yt-dlp can calculate it.")

    def _on_url_modified(self, _event=None):
        if not self.url_text.edit_modified():
            return
        self.url_text.edit_modified(False)
        self._schedule_preview()

    def _schedule_preview(self):
        if self._preview_after_id is not None:
            self.after_cancel(self._preview_after_id)
            self._preview_after_id = None
        self._preview_token += 1
        urls = [u.strip() for u in self.url_text.get("1.0", "end").splitlines() if u.strip()]
        if not urls:
            self._clear_preview()
            return
        self.preview_status_var.set("Waiting for typing to finish...")
        token = self._preview_token
        self._preview_after_id = self.after(500, self._start_preview, urls[0], token)

    def _start_preview(self, url, token):
        self._preview_after_id = None
        if token != self._preview_token:
            return
        self.preview_status_var.set("Fetching preview...")
        browser = self.browser_var.get()
        cookies_file = self.cookies_file_var.get().strip()
        proxy = self.proxy_var.get().strip()
        threading.Thread(
            target=self._preview_worker,
            args=(url, token, browser, cookies_file, proxy),
            daemon=True,
        ).start()

    def _preview_worker(self, url, token, browser, cookies_file, proxy):
        options = {"quiet": True, "no_warnings": True, "skip_download": True}
        if browser != "None":
            options["cookiesfrombrowser"] = (browser.lower(), None, None, None)
        if cookies_file:
            options["cookiefile"] = cookies_file
        if proxy:
            options["proxy"] = proxy
        try:
            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(url, download=False)
        except Exception as error:
            if browser == "None" or not _looks_like_cookie_database_error(error):
                self._enqueue(self._apply_preview_error, token, str(error))
                return
            options.pop("cookiesfrombrowser", None)
            try:
                with yt_dlp.YoutubeDL(options) as ydl:
                    info = ydl.extract_info(url, download=False)
            except Exception as retry_error:
                self._enqueue(self._apply_preview_error, token, str(retry_error))
                return

        if info.get("_type") == "playlist":
            entries = info.get("entries") or []
            info = next((entry for entry in entries if entry), info)

        thumbnail_data = None
        thumbnail_url = info.get("thumbnail")
        if thumbnail_url:
            try:
                request = urllib.request.Request(thumbnail_url, headers={"User-Agent": APP_NAME})
                with urllib.request.urlopen(request, timeout=8) as response:
                    thumbnail_data = response.read(4 * 1024 * 1024)
            except Exception:
                thumbnail_data = None

        height = info.get("height")
        abr = info.get("abr")
        resolution = info.get("resolution") or (f"{height}p" if height else "")
        if not resolution and abr:
            resolution = f"{abr:.0f} kbps"
        preview = {
            "title": info.get("title") or "Untitled media",
            "details": "  •  ".join(filter(None, [
                info.get("extractor_key") or info.get("extractor"),
                info.get("uploader") or info.get("channel"),
                self._format_duration(info.get("duration")),
                resolution,
            ])) or "Metadata available",
            "thumbnail_data": thumbnail_data,
        }
        self._enqueue(self._apply_preview, token, preview)

    @staticmethod
    def _format_duration(seconds):
        if not seconds:
            return ""
        try:
            seconds = int(seconds)
        except (TypeError, ValueError):
            return ""
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes}:{seconds:02d}"

    def _clear_preview(self):
        self.preview_title_var.set("Paste a link to preview it")
        self.preview_details_var.set("Title, thumbnail, duration, uploader, and platform will appear here.")
        self.preview_status_var.set("Waiting for a link")
        self._preview_photo = None
        self.preview_image_label.configure(image="", text="No preview")

    def _apply_preview_error(self, token, error):
        if token != self._preview_token:
            return
        self.preview_status_var.set(f"Preview unavailable: {explain_download_error(error)}")

    def _apply_preview(self, token, preview):
        if token != self._preview_token:
            return
        self.preview_title_var.set(preview["title"])
        self.preview_details_var.set(preview["details"])
        self.preview_status_var.set("Preview ready")
        thumbnail_data = preview.get("thumbnail_data")
        if thumbnail_data and Image is not None and ImageTk is not None:
            try:
                image = Image.open(io.BytesIO(thumbnail_data)).convert("RGB")
                image.thumbnail((PREVIEW_WIDTH, PREVIEW_HEIGHT))
                self._preview_photo = ImageTk.PhotoImage(image)
                self.preview_image_label.configure(
                    image=self._preview_photo,
                    text="",
                    width=PREVIEW_WIDTH,
                    height=PREVIEW_HEIGHT,
                )
                return
            except Exception:
                pass
        self._preview_photo = None
        self.preview_image_label.configure(image="", text="Thumbnail unavailable")

    def _scroll_main(self, event):
        """Animate the outer panel without stealing the wheel from text editors."""
        if isinstance(event.widget, tk.Text):
            return
        if getattr(event, "num", None) == 4:
            direction = -1
        elif getattr(event, "num", None) == 5:
            direction = 1
        elif event.delta:
            direction = -1 if event.delta > 0 else 1
        else:
            return

        current_top, current_bottom = self.main_canvas.yview()
        if current_bottom - current_top >= 0.999:
            return
        if self._scroll_target is None:
            self._scroll_target = current_top
        step = 0.025 * clamp_scroll_speed(self.scroll_speed_var.get())
        max_top = max(0.0, 1.0 - (current_bottom - current_top))
        self._scroll_target = max(0.0, min(max_top, self._scroll_target + direction * step))
        self._animate_main_scroll()

    def _animate_main_scroll(self):
        if self._scroll_animation_id is not None:
            return
        self._scroll_animation_id = self.after(10, self._step_main_scroll)

    def _step_main_scroll(self):
        self._scroll_animation_id = None
        if self._scroll_target is None:
            return
        current_top, _current_bottom = self.main_canvas.yview()
        distance = self._scroll_target - current_top
        if abs(distance) < 0.001:
            self.main_canvas.yview_moveto(self._scroll_target)
            self._scroll_target = None
            return
        self.main_canvas.yview_moveto(current_top + distance * 0.30)
        self._scroll_animation_id = self.after(10, self._step_main_scroll)

    def _toggle_format(self):
        if self.format_var.get() == "video":
            self.quality_combo["values"] = VIDEO_QUALITIES
            self.quality_var.set(VIDEO_QUALITIES[0])
        else:
            self.quality_combo["values"] = AUDIO_QUALITIES
            self.quality_var.set(AUDIO_QUALITIES[0])

    # ------------------------------------------------------------ helpers --
    def _browse_output(self):
        folder = filedialog.askdirectory(initialdir=self.output_var.get() or "/")
        if folder:
            self.output_var.set(folder)

    def _browse_ffmpeg(self):
        path = filedialog.askopenfilename(
            title="Select ffmpeg",
            filetypes=[("ffmpeg", "ffmpeg*"), ("All files", "*.*")]
        )
        if path:
            self.ffmpeg_var.set(path)

    def _browse_cookies(self):
        path = filedialog.askopenfilename(
            title="Select cookies.txt",
            filetypes=[("Cookie files", "*.txt"), ("All files", "*.*")]
        )
        if path:
            self.cookies_file_var.set(path)

    def _update_ffmpeg_status(self, *_args):
        path = self.ffmpeg_var.get().strip()
        if path and os.path.isfile(path):
            self.ffmpeg_status_label.config(text=f"\u2713 Using: {path}", fg=SUCCESS)
        elif path:
            self.ffmpeg_status_label.config(text="\u26a0 That file wasn't found - check the path.", fg=WARNING)
        else:
            self.ffmpeg_status_label.config(
                text="\u26a0 ffmpeg wasn't found automatically - click Browse, or install it (see README).",
                fg=WARNING
            )

    def _open_output_folder(self):
        folder = self.output_var.get().strip()
        if folder and os.path.isdir(folder):
            try:
                if sys.platform == "win32":
                    os.startfile(folder)
                elif sys.platform == "darwin":
                    subprocess.Popen(["open", folder])
                else:
                    subprocess.Popen(["xdg-open", folder])
            except OSError as e:
                messagebox.showerror("Couldn't open folder", str(e))
        else:
            messagebox.showwarning(
                "Folder not found",
                "That save folder doesn't exist yet. It will be created when you start a download."
            )

    def log(self, message):
        try:
            self.log_box.configure(state="normal")
            self.log_box.insert("end", str(message) + "\n")
            self.log_box.see("end")
            self.log_box.configure(state="disabled")
        except tk.TclError:
            pass  # widget may be gone during shutdown

    def _handle_tk_exception(self, exc, val, tb):
        """Any otherwise-uncaught error in a Tk callback lands in the log instead of vanishing."""
        msg = "".join(traceback.format_exception(exc, val, tb))
        self.log(f"[Unexpected error]\n{msg}")

    def _on_close(self):
        save_config(self._settings_from_ui())
        self.destroy()

    def _settings_from_ui(self):
        return {
            "format": self.format_var.get(),
            "quality": self.quality_var.get(),
            "only_this_video": self.playlist_var.get(),
            "output_dir": self.output_var.get().strip(),
            "ffmpeg_path": self.ffmpeg_var.get().strip(),
            "cookies_browser": self.browser_var.get(),
            "cookies_file": self.cookies_file_var.get().strip(),
            "proxy": self.proxy_var.get().strip(),
            "subtitles": self.subtitles_var.get(),
            "auto_subtitles": self.auto_subtitles_var.get(),
            "subtitle_languages": self.subtitle_langs_var.get().strip() or "en.*",
            "embed_metadata": self.embed_metadata_var.get(),
            "embed_thumbnail": self.embed_thumbnail_var.get(),
            "live_from_start": self.live_from_start_var.get(),
            "format_id": self.format_id_var.get().strip(),
            "last_update_check": self._last_update_check,
            "scroll_speed": clamp_scroll_speed(self.scroll_speed_var.get()),
        }

    def _list_formats(self):
        urls = [u.strip() for u in self.url_text.get("1.0", "end").splitlines() if u.strip()]
        if not urls:
            messagebox.showwarning("No link", "Paste a video link first.")
            return
        url = urls[0]
        browser = self.browser_var.get()
        cookies_file = self.cookies_file_var.get().strip()
        self.log(f"\nAvailable formats for: {url}")
        self.status_label.config(text="Inspecting available formats...")
        threading.Thread(target=self._format_worker, args=(url, browser, cookies_file), daemon=True).start()

    def _format_worker(self, url, browser, cookies_file):
        try:
            opts = {"quiet": True, "no_warnings": True}
            if browser != "None":
                opts["cookiesfrombrowser"] = (browser.lower(), None, None, None)
            if cookies_file:
                opts["cookiefile"] = cookies_file
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
            rows = []
            for item in info.get("formats", []):
                rows.append(
                    f"{item.get('format_id', '?'):>8} | "
                    f"{item.get('ext', '?'):<4} | "
                    f"{item.get('resolution') or item.get('format_note') or '?':<12} | "
                    f"{item.get('vcodec', 'none'):<12} | "
                    f"{item.get('acodec', 'none'):<12} | "
                    f"{item.get('filesize') or item.get('filesize_approx') or '?'}"
                )
            self._enqueue(self.log, "format_id | ext  | resolution   | video codec  | audio codec  | size")
            for row in rows:
                self._enqueue(self.log, row)
            self._enqueue(self.log, "Use a format ID or combination such as 137+140 in the exact format field.")
            self._enqueue(self.status_label.config, {"text": "Format list ready."})
        except Exception as e:
            self._enqueue(self.log, f"[Format inspection failed] {e}")
            self._enqueue(self.status_label.config, {"text": "Format inspection failed."})

    def _check_for_updates(self):
        self.status_label.config(text="Checking yt-dlp version...")
        threading.Thread(target=self._update_check_worker, daemon=True).start()

    def _auto_update_check(self):
        if time.time() - self._last_update_check >= 86400:
            self._last_update_check = time.time()
            settings = self._settings_from_ui()
            settings["last_update_check"] = self._last_update_check
            save_config(settings)
            self._check_for_updates()

    def _update_check_worker(self):
        try:
            current = getattr(getattr(yt_dlp, "version", None), "__version__", "unknown")
            request = urllib.request.Request(
                "https://pypi.org/pypi/yt-dlp/json",
                headers={"User-Agent": f"{APP_NAME}/{current}"},
            )
            with urllib.request.urlopen(request, timeout=8) as response:
                latest = json.load(response)["info"]["version"]
            current_key = self._version_key(current)
            latest_key = self._version_key(latest)
            if current_key < latest_key:
                message = f"yt-dlp update available: {current} -> {latest}. Rebuild the app after updating."
            else:
                message = f"yt-dlp is up to date ({current})."
            self._enqueue(self.log, message)
            self._enqueue(self.status_label.config, {"text": message})
        except Exception as e:
            message = f"Could not check for yt-dlp updates: {e}"
            self._enqueue(self.log, message)
            self._enqueue(self.status_label.config, {"text": "Update check failed."})

    @staticmethod
    def _version_key(version):
        return tuple(int(part) for part in re.findall(r"\d+", version or "0"))

    # ------------------------------------------------- thread-safe UI queue --
    def _enqueue(self, func, *args):
        self._ui_queue.put((func, args))

    def _drain_queue(self):
        try:
            while True:
                func, args = self._ui_queue.get_nowait()
                try:
                    func(*args)
                except Exception:
                    try:
                        self.log(f"[UI error] {traceback.format_exc()}")
                    except Exception:
                        pass
        except queue.Empty:
            pass
        self.after(100, self._drain_queue)

    # ------------------------------------------------------- download logic --
    def _start_download(self):
        urls = [u.strip() for u in self.url_text.get("1.0", "end").splitlines() if u.strip()]
        if not urls:
            messagebox.showwarning("No link", "Paste at least one video link first.")
            return

        output_dir = self.output_var.get().strip()
        if not output_dir:
            messagebox.showwarning("No folder", "Choose a folder to save downloads to.")
            return

        try:
            os.makedirs(output_dir, exist_ok=True)
        except Exception as e:
            messagebox.showerror("Folder error", f"Couldn't create/access that folder:\n{e}")
            return

        self._download_settings = self._settings_from_ui()
        save_config(self._download_settings)

        self._cancel_requested = False
        self._playlist_seen = set()
        self._failed_count = 0
        self.download_status_var.set(f"Queued {len(urls)} link(s)")
        self.download_rate_var.set("0 B/s")
        self.upload_rate_var.set("0 B/s")
        self.progress_summary_var.set("0%")
        self.transfer_summary_var.set("0 B / 0 B")
        self.eta_var.set("—")
        self.download_btn.config(state="disabled", text="Downloading...")
        self.cancel_btn.config(state="normal")
        self.progress["value"] = 0
        self.status_label.config(text="Starting...")
        threading.Thread(target=self._download_worker, args=(urls, self._download_settings), daemon=True).start()

    def _cancel_download(self):
        self._cancel_requested = True
        self.download_status_var.set("Cancelling")
        self.status_label.config(text="Cancelling... (finishing current chunk)")
        self.cancel_btn.config(state="disabled")

    def _download_worker(self, urls, settings):
        total = len(urls)
        for idx, url in enumerate(urls, start=1):
            self._enqueue(self.log, f"[{idx}/{total}] Starting: {url}")
            attempt = 0
            active_settings = dict(settings)
            cookie_fallback_attempted = False
            subtitle_fallback_attempted = False
            while True:
                attempt += 1
                try:
                    self._do_download(url, idx, total, active_settings)
                    self._enqueue(self.log, f"[{idx}/{total}] Finished: {url}")
                    break
                except _ConnectionLostError:
                    self._enqueue(self.log,
                                  f"[{idx}/{total}] Internet connection lost. Will keep retrying and "
                                  f"resume from where it stopped (not from the start)...")
                    self._enqueue(self._on_connection_lost, idx, total)
                    self._wait_for_reconnect(idx, total)
                    if self._cancel_requested:
                        break
                    self._enqueue(self.log, f"[{idx}/{total}] Connection restored - resuming download...")
                    continue
                except yt_dlp.utils.DownloadError as e:
                    if (_looks_like_cookie_database_error(e)
                            and active_settings["cookies_browser"] != "None"
                            and not cookie_fallback_attempted
                            and not self._cancel_requested):
                        cookie_fallback_attempted = True
                        active_settings = dict(active_settings)
                        active_settings["cookies_browser"] = "None"
                        self._enqueue(self.log,
                                      f"[{idx}/{total}] Could not copy the browser cookie database. "
                                      "Retrying without browser cookies; close the browser or use cookies.txt "
                                      "if sign-in is required...")
                        continue
                    if (_looks_like_subtitle_rate_limit(e)
                            and active_settings["subtitles"]
                            and not subtitle_fallback_attempted
                            and not self._cancel_requested):
                        subtitle_fallback_attempted = True
                        active_settings = dict(active_settings)
                        active_settings["subtitles"] = False
                        self._enqueue(self.log,
                                      f"[{idx}/{total}] Subtitle service returned HTTP 429. "
                                      "Retrying the video without subtitles...")
                        continue
                    if _looks_like_connection_error(e) and attempt < MAX_RETRIES and not self._cancel_requested:
                        self._enqueue(self.log,
                                      f"[{idx}/{total}] Network error, retrying in {RETRY_WAIT_SECONDS}s "
                                      f"(resumes from where it left off)...")
                        time.sleep(RETRY_WAIT_SECONDS)
                        continue
                    self._enqueue(self.log, f"[{idx}/{total}] FAILED: {explain_download_error(e)}")
                    self._enqueue(self._set_transfer_status, "Failed")
                    self._failed_count += 1
                    break
                except Exception as e:
                    self._enqueue(self.log, f"[{idx}/{total}] FAILED (unexpected error): {explain_download_error(e)}")
                    self._enqueue(self._set_transfer_status, "Failed")
                    self._failed_count += 1
                    break
                if self._cancel_requested:
                    break
            if self._cancel_requested:
                break
        self._enqueue(self._on_all_done, total)

    def _wait_for_reconnect(self, idx, total):
        """Block (in the worker thread) until internet is back, checking periodically."""
        while not is_internet_up() and not self._cancel_requested:
            time.sleep(RETRY_WAIT_SECONDS)

    def _on_connection_lost(self, idx, total):
        self.download_status_var.set("Waiting for connection")
        self.status_label.config(text=f"[{idx}/{total}] Internet connection lost - waiting to resume...")

    def _set_transfer_status(self, status):
        self.download_status_var.set(status)

    def _do_download(self, url, idx, total, settings):
        fmt = settings["format"]
        quality = settings["quality"]
        output_dir = settings["output_dir"]
        ffmpeg_path = settings["ffmpeg_path"]
        only_this_video = settings["only_this_video"]
        detected_ffmpeg = ffmpeg_path if ffmpeg_path and os.path.isfile(ffmpeg_path) else find_ffmpeg()

        if fmt == "audio" and not detected_ffmpeg:
            raise yt_dlp.utils.DownloadError(
                "MP3 conversion requires ffmpeg. Install ffmpeg or place it beside the app."
            )

        def hook(d):
            status = d.get("status")
            info = d.get("info_dict") or {}
            playlist_index = info.get("playlist_index")
            playlist_count = info.get("n_entries") or info.get("playlist_count")
            item_key = info.get("id") or info.get("webpage_url") or info.get("title")
            if item_key and item_key not in self._playlist_seen:
                self._playlist_seen.add(item_key)
                self._enqueue(self._on_playlist_item, idx, total, playlist_index, playlist_count,
                              info.get("title") or url)
            # If a chunk errors out mid-stream because the connection dropped,
            # yt-dlp reports it here before raising. Treat it as a connection-lost signal.
            if status == "error" and not is_internet_up(timeout=2):
                raise _ConnectionLostError("Internet connection lost during download")
            self._enqueue(self._on_progress, d, idx, total)

        if fmt == "video":
            # height is resolved from the actual selected video format, so the suffix
            # remains truthful when a requested ceiling is unavailable.
            output_template = os.path.join(output_dir, "%(title)s [%(height)sp].%(ext)s")
        else:
            bitrate = BITRATE_MAP.get(quality, "192")
            output_template = os.path.join(output_dir, f"%(title)s [{bitrate}kbps].%(ext)s")

        ydl_opts = {
            "outtmpl": output_template,
            "noplaylist": only_this_video,
            "windowsfilenames": True,
            "progress_hooks": [hook],
            "quiet": True,
            "no_warnings": True,
            # --- Resume support: never start over, always continue partial (.part) files ---
            "continuedl": True,
            "nopart": False,
            "retries": 20,
            "fragment_retries": 20,
            "file_access_retries": 10,
            "retry_sleep_functions": {
                "http": lambda n: min(RETRY_WAIT_SECONDS * n, 30),
                "fragment": lambda n: min(RETRY_WAIT_SECONDS * n, 30),
                "file_access": lambda n: min(RETRY_WAIT_SECONDS * n, 30),
            },
        }
        if settings["cookies_browser"] != "None":
            ydl_opts["cookiesfrombrowser"] = (settings["cookies_browser"].lower(), None, None, None)
        if settings["cookies_file"]:
            ydl_opts["cookiefile"] = settings["cookies_file"]
        if settings["proxy"]:
            ydl_opts["proxy"] = settings["proxy"]
        if settings["live_from_start"]:
            ydl_opts["live_from_start"] = True
        if settings["subtitles"]:
            ydl_opts["writesubtitles"] = True
            ydl_opts["subtitleslangs"] = [lang.strip() for lang in settings["subtitle_languages"].split(",") if lang.strip()]
            ydl_opts["writeautomaticsub"] = settings["auto_subtitles"]
            ydl_opts["embedsubs"] = True
        if settings["embed_metadata"]:
            ydl_opts["addmetadata"] = True
        if settings["embed_thumbnail"]:
            ydl_opts["writethumbnail"] = True
            ydl_opts["embedthumbnail"] = True
        if detected_ffmpeg:
            ydl_opts["ffmpeg_location"] = detected_ffmpeg

        if settings["format_id"]:
            ydl_opts["format"] = settings["format_id"]
        elif fmt == "video":
            h = HEIGHT_MAP.get(quality)
            if not detected_ffmpeg:
                if h:
                    ydl_opts["format"] = f"best[height<={h}][ext=mp4]/best[height<={h}]/best"
                else:
                    ydl_opts["format"] = "best[ext=mp4]/best"
            elif h:
                ydl_opts["format"] = (
                    f"bestvideo[height<={h}][ext=mp4]+bestaudio[ext=m4a]/"
                    f"best[height<={h}][ext=mp4]/best[height<={h}]"
                )
            else:
                ydl_opts["format"] = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
        if fmt == "video" and detected_ffmpeg:
            ydl_opts["merge_output_format"] = "mp4"
        elif not settings["format_id"] or fmt == "audio":
            bitrate = BITRATE_MAP.get(quality, "192")
            if not settings["format_id"]:
                ydl_opts["format"] = "bestaudio/best"
            ydl_opts["postprocessors"] = [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": bitrate,
            }]

        # Before even starting, if there's no internet, wait rather than fail immediately.
        if not is_internet_up():
            raise _ConnectionLostError("No internet connection")

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

    def _on_progress(self, d, idx, total):
        status = d.get("status")
        if status == "downloading":
            downloaded = d.get("downloaded_bytes", 0) or 0
            grand_total = d.get("total_bytes") or d.get("total_bytes_estimate")
            percent = (downloaded / grand_total * 100) if grand_total else 0
            self.progress["value"] = percent
            self.download_status_var.set("Downloading")
            self.progress_summary_var.set(f"{percent:.1f}%")
            if grand_total:
                self.transfer_summary_var.set(f"{format_bytes(downloaded)} / {format_bytes(grand_total)}")
            else:
                self.transfer_summary_var.set(f"{format_bytes(downloaded)} / —")

            speed = d.get("speed")
            speed_str = format_rate(speed)
            self.download_rate_var.set(speed_str)
            eta = d.get("eta")
            eta_str = f"{eta}s" if eta else "..."
            self.eta_var.set(eta_str)
            self.status_label.config(
                text=f"[{idx}/{total}] Downloading: {percent:.1f}%  |  Speed: {speed_str}  |  ETA: {eta_str}"
            )
        elif status == "finished":
            self.progress["value"] = 100
            self.download_status_var.set("Processing")
            self.progress_summary_var.set("100%")
            self.download_rate_var.set("0 B/s")
            self.eta_var.set("—")
            self.status_label.config(text=f"[{idx}/{total}] Converting/merging (this can take a moment)...")

    def _on_playlist_item(self, idx, total, playlist_index, playlist_count, title):
        if playlist_index and playlist_count:
            self.log(f"[{idx}/{total}] Playlist item {playlist_index}/{playlist_count}: {title}")
            self.status_label.config(text=f"[{idx}/{total}] Playlist item {playlist_index}/{playlist_count}: {title}")
        else:
            self.log(f"[{idx}/{total}] Video: {title}")

    def _on_all_done(self, total):
        self.download_btn.config(state="normal", text="Download")
        self.cancel_btn.config(state="disabled")
        self.status_label.config(text="Ready.")
        if self._cancel_requested:
            self.download_status_var.set("Cancelled")
            self.log("\nCancelled. Partially downloaded files are kept and will resume next time you click Download.\n")
            messagebox.showinfo("Cancelled", "Download cancelled. Re-run the same link later to resume from where it stopped.")
        else:
            if self._failed_count:
                self.download_status_var.set("Completed with errors")
            else:
                self.download_status_var.set("Complete")
            self.download_rate_var.set("0 B/s")
            self.eta_var.set("—")
            if self._failed_count:
                self.log(f"\nCompleted with errors. Processed {total} link(s); "
                         f"{self._failed_count} failed.\n")
                messagebox.showwarning(
                    "Completed with errors",
                    f"Processed {total} link(s); {self._failed_count} failed. Check the log for details."
                )
            else:
                self.log(f"\nAll done! Processed {total} link(s).\n")
                messagebox.showinfo("Complete", f"Finished processing {total} link(s).\nCheck the log for any errors.")


if __name__ == "__main__":
    app = GGUVDODApp()
    app.mainloop()
