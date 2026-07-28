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
CONNECTIVITY_HOST = "8.8.8.8"
CONNECTIVITY_PORT = 53

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
    try:
        with socket.create_connection((CONNECTIVITY_HOST, CONNECTIVITY_PORT), timeout=timeout):
            return True
    except OSError:
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

        # Thread-safe UI update queue. The download worker thread NEVER touches
        # Tk widgets directly - it only pushes (callable, args) here, and a
        # periodic poll on the main thread drains it. This is what makes the
        # log panel and progress bar update reliably.
        self._ui_queue = queue.Queue()

        self._setup_style()
        self._build_ui()
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
        return tk.Entry(parent, textvariable=textvariable, **kwargs)

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
        widget = scrolledtext.ScrolledText(parent, **kwargs)
        try:
            widget.vbar.configure(bg=BG_PANEL, troughcolor=BG, activebackground=BORDER,
                                   highlightthickness=0, bd=0, relief="flat")
        except Exception:
            pass
        return widget

    # ---------------------------------------------------------- UI build --
    def _build_ui(self):
        pad = {"padx": 24, "pady": 10}

        # Center column so the UI doesn't stretch edge-to-edge on a 1920px window
        container = self._frame(self)
        container.pack(fill="both", expand=True)
        container.grid_columnconfigure(0, weight=1)
        container.grid_columnconfigure(1, weight=0, minsize=1200)
        container.grid_columnconfigure(2, weight=1)
        container.grid_rowconfigure(0, weight=1)

        content = self._frame(container)
        content.grid(row=0, column=1, sticky="nsew")

        self._label(content, text=APP_NAME, font=("Segoe UI", 28, "bold")).pack(pady=(26, 6))
        self._label(content, text="Paste one or more video links below (one per line)",
                     font=("Segoe UI", 12), fg=FG_MUTED).pack()

        self.url_text = self._scrolled_text(content, BG_ENTRY, FG, height=5, wrap="word", font=("Segoe UI", 12))
        self.url_text.pack(fill="x", **pad)

        # Format + quality
        fmt_frame = self._labelframe(content, "Format", padx=16, pady=12)
        fmt_frame.pack(fill="x", **pad)

        self._radio(fmt_frame, text="Video (MP4)", variable=self.format_var, value="video",
                    command=self._toggle_format).grid(row=0, column=0, sticky="w", padx=(0, 30))
        self._radio(fmt_frame, text="Audio only (MP3)", variable=self.format_var, value="audio",
                    command=self._toggle_format).grid(row=0, column=1, sticky="w")

        self._label(fmt_frame, text="Quality:", bg=BG_PANEL).grid(row=1, column=0, sticky="w", pady=(12, 0))
        self.quality_combo = ttk.Combobox(fmt_frame, textvariable=self.quality_var, values=VIDEO_QUALITIES,
                                           state="readonly", width=22, font=("Segoe UI", 11))
        self.quality_combo.grid(row=1, column=1, sticky="w", pady=(12, 0))

        self._check(fmt_frame, text="Only download this video (ignore playlist)",
                    variable=self.playlist_var).grid(row=2, column=0, columnspan=2, sticky="w", pady=(12, 0))

        # Output folder
        out_frame = self._labelframe(content, "Save to", padx=16, pady=12)
        out_frame.pack(fill="x", **pad)
        out_row = self._frame(out_frame, bg=BG_PANEL)
        out_row.pack(fill="x")
        self._entry(out_row, textvariable=self.output_var).pack(side="left", fill="x", expand=True, ipady=4)
        self._button(out_row, "Browse...", self._browse_output).pack(side="left", padx=(10, 0))

        # ffmpeg path (auto-detected by default; editable)
        ff_frame = self._labelframe(content, "ffmpeg location (auto-detected - change only if needed)",
                                     padx=16, pady=12)
        ff_frame.pack(fill="x", **pad)
        ff_row = self._frame(ff_frame, bg=BG_PANEL)
        ff_row.pack(fill="x")
        self._entry(ff_row, textvariable=self.ffmpeg_var).pack(side="left", fill="x", expand=True, ipady=4)
        self._button(ff_row, "Browse...", self._browse_ffmpeg).pack(side="left", padx=(10, 0))
        self.ffmpeg_status_label = self._label(ff_frame, text="", bg=BG_PANEL, font=("Segoe UI", 9))
        self.ffmpeg_status_label.pack(anchor="w", pady=(8, 0))
        self.ffmpeg_var.trace_add("write", lambda *a: self._update_ffmpeg_status())

        # Authentication and output options
        options_frame = self._labelframe(content, "Authentication and output options", padx=16, pady=12)
        options_frame.pack(fill="x", **pad)

        auth_row = self._frame(options_frame, bg=BG_PANEL)
        auth_row.pack(fill="x", pady=(0, 8))
        self._label(auth_row, text="Browser cookies:", bg=BG_PANEL).pack(side="left")
        ttk.Combobox(auth_row, textvariable=self.browser_var, values=COOKIE_BROWSERS,
                     state="readonly", width=14, font=("Segoe UI", 11)).pack(side="left", padx=(10, 20))
        self._label(auth_row, text="Cookies file:", bg=BG_PANEL).pack(side="left")
        self._entry(auth_row, textvariable=self.cookies_file_var).pack(side="left", fill="x", expand=True,
                                                                        padx=(10, 0), ipady=4)
        self._button(auth_row, "Browse...", self._browse_cookies).pack(side="left", padx=(10, 0))

        proxy_row = self._frame(options_frame, bg=BG_PANEL)
        proxy_row.pack(fill="x", pady=(0, 8))
        self._label(proxy_row, text="Proxy (optional):", bg=BG_PANEL).pack(side="left")
        self._entry(proxy_row, textvariable=self.proxy_var).pack(side="left", fill="x", expand=True,
                                                                 padx=(10, 10), ipady=4)
        self._label(proxy_row, text="Example: http://user:pass@host:port", bg=BG_PANEL,
                    fg=FG_MUTED, font=("Segoe UI", 9)).pack(side="left")
        self._button(proxy_row, "Check yt-dlp updates", self._check_for_updates).pack(side="right", padx=(10, 0))

        subtitle_row = self._frame(options_frame, bg=BG_PANEL)
        subtitle_row.pack(fill="x", pady=(0, 8))
        self._check(subtitle_row, text="Download subtitles", variable=self.subtitles_var).pack(side="left")
        self._check(subtitle_row, text="Include auto-generated", variable=self.auto_subtitles_var).pack(side="left", padx=(18, 0))
        self._label(subtitle_row, text="Languages:", bg=BG_PANEL).pack(side="left", padx=(18, 0))
        self._entry(subtitle_row, textvariable=self.subtitle_langs_var, width=18).pack(side="left", padx=(8, 0), ipady=4)
        self._check(subtitle_row, text="Embed metadata", variable=self.embed_metadata_var).pack(side="left", padx=(18, 0))
        self._check(subtitle_row, text="Embed thumbnail", variable=self.embed_thumbnail_var).pack(side="left", padx=(18, 0))
        self._check(subtitle_row, text="Live: start from beginning", variable=self.live_from_start_var).pack(side="left", padx=(18, 0))

        format_row = self._frame(options_frame, bg=BG_PANEL)
        format_row.pack(fill="x")
        self._label(format_row, text="Exact format ID(s) (optional):", bg=BG_PANEL).pack(side="left")
        self._entry(format_row, textvariable=self.format_id_var).pack(side="left", fill="x", expand=True,
                                                                       padx=(10, 10), ipady=4)
        self._button(format_row, "List formats", self._list_formats).pack(side="left")

        # Buttons
        btn_frame = self._frame(content)
        btn_frame.pack(fill="x", **pad)
        self.download_btn = self._button(btn_frame, "Download", self._start_download, primary=True)
        self.download_btn.pack(side="left", ipadx=30, ipady=10)
        self.cancel_btn = self._button(btn_frame, "Cancel", self._cancel_download, state="disabled")
        self.cancel_btn.pack(side="left", padx=(14, 0), ipady=6)
        self._button(btn_frame, "Open Save Folder", self._open_output_folder).pack(side="left", padx=(14, 0), ipady=6)

        # Progress
        prog_frame = self._frame(content)
        prog_frame.pack(fill="x", **pad)
        self.progress = ttk.Progressbar(prog_frame, orient="horizontal", mode="determinate", maximum=100)
        self.progress.pack(fill="x", ipady=4)

        self.status_label = self._label(content, text="Ready.", fg=FG_MUTED, anchor="w")
        self.status_label.pack(fill="x", padx=24)

        # Log
        log_frame = self._labelframe(content, "Log", padx=10, pady=10)
        log_frame.pack(fill="both", expand=True, **pad)
        self.log_box = self._scrolled_text(log_frame, BG_LOG, FG_LOG, height=12, state="disabled",
                                            font=("Consolas", 11))
        self.log_box.pack(fill="both", expand=True)

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
        self.download_btn.config(state="disabled", text="Downloading...")
        self.cancel_btn.config(state="normal")
        self.progress["value"] = 0
        self.status_label.config(text="Starting...")
        threading.Thread(target=self._download_worker, args=(urls, self._download_settings), daemon=True).start()

    def _cancel_download(self):
        self._cancel_requested = True
        self.status_label.config(text="Cancelling... (finishing current chunk)")
        self.cancel_btn.config(state="disabled")

    def _download_worker(self, urls, settings):
        total = len(urls)
        for idx, url in enumerate(urls, start=1):
            self._enqueue(self.log, f"[{idx}/{total}] Starting: {url}")
            attempt = 0
            while True:
                attempt += 1
                try:
                    self._do_download(url, idx, total, settings)
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
                    if _looks_like_connection_error(e) and attempt < MAX_RETRIES and not self._cancel_requested:
                        self._enqueue(self.log,
                                      f"[{idx}/{total}] Network error, retrying in {RETRY_WAIT_SECONDS}s "
                                      f"(resumes from where it left off)...")
                        time.sleep(RETRY_WAIT_SECONDS)
                        continue
                    self._enqueue(self.log, f"[{idx}/{total}] FAILED: {explain_download_error(e)}")
                    break
                except Exception as e:
                    self._enqueue(self.log, f"[{idx}/{total}] FAILED (unexpected error): {explain_download_error(e)}")
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
        self.status_label.config(text=f"[{idx}/{total}] Internet connection lost - waiting to resume...")

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

        ydl_opts = {
            "outtmpl": os.path.join(output_dir, "%(title)s.%(ext)s"),
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

            speed = d.get("speed")
            speed_str = f"{speed / 1024 / 1024:.2f} MB/s" if speed else "..."
            eta = d.get("eta")
            eta_str = f"{eta}s" if eta else "..."
            self.status_label.config(
                text=f"[{idx}/{total}] Downloading: {percent:.1f}%  |  Speed: {speed_str}  |  ETA: {eta_str}"
            )
        elif status == "finished":
            self.progress["value"] = 100
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
            self.log("\nCancelled. Partially downloaded files are kept and will resume next time you click Download.\n")
            messagebox.showinfo("Cancelled", "Download cancelled. Re-run the same link later to resume from where it stopped.")
        else:
            self.log(f"\nAll done! Processed {total} link(s).\n")
            messagebox.showinfo("Complete", f"Finished processing {total} link(s).\nCheck the log for any errors.")


if __name__ == "__main__":
    app = GGUVDODApp()
    app.mainloop()
