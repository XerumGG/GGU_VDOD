"""PySide6 main window providing 100% complete desktop downloader capabilities."""

import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import urllib.request

from PIL import Image
from PySide6.QtCore import QEvent, QObject, QPoint, QRect, QSize, Qt, QThread, QTimer, QUrl, Signal
from PySide6.QtGui import QAction, QColor, QDesktopServices, QFont, QIcon, QKeySequence, QPixmap
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QCheckBox, QComboBox, QDialog, QFileDialog,
    QFormLayout, QFrame, QGridLayout, QGroupBox, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QMainWindow, QMessageBox, QPlainTextEdit, QProgressBar,
    QPushButton, QRadioButton, QScrollArea, QSlider, QSpinBox, QSplitter,
    QStyle, QTableWidget, QTableWidgetItem, QTabWidget, QToolButton,
    QVBoxLayout, QWidget,
)

from ...config.paths import get_app_dir, get_default_ffmpeg_path, get_default_output_dir
from ...config.store import add_history_entry, load_config, save_config, update_history_entry
from ...conversion.options import (
    FFmpegCustomAudioConvertPP, FFmpegCustomReencodePP, audio_conversion_args,
    clean_video_sidecars, output_template, video_conversion_args,
)
from ...core.constants import (
    APP_NAME, AUDIO_FORMAT_EXTENSIONS, AUDIO_OUTPUT_FORMATS, AUDIO_QUALITIES,
    BITRATE_MAP, CHANNEL_OPTIONS, COMPRESSION_OPTIONS, COOKIE_BROWSERS,
    DEFAULT_KEY_BINDINGS, FRAME_RATE_OPTIONS, HEIGHT_MAP, KEY_BINDING_CHOICES,
    MAX_RETRIES, PREVIEW_HEIGHT, PREVIEW_WIDTH, RETRY_WAIT_SECONDS,
    SAMPLE_RATE_OPTIONS, SCROLL_SPEED_DEFAULT, SCROLL_SPEED_MAX, SCROLL_SPEED_MIN,
    UPDATE_COMPONENTS, VIDEO_CODEC_ARGS, VIDEO_CODEC_OPTIONS, VIDEO_FORMAT_EXTENSIONS,
    VIDEO_OUTPUT_FORMATS, VIDEO_QUALITIES, VIDEO_RESOLUTION_OPTIONS,
    VIDEO_SIDECAR_EXTENSIONS, ZOOM_DEFAULT_PERCENT, ZOOM_MAX_PERCENT,
    ZOOM_MIN_PERCENT, ZOOM_STEP_PERCENT, clamp_scroll_speed, clamp_zoom_percent,
)
from ...core.formatting import format_bytes, format_rate
from ...core.version import DEVELOPMENT_BUILD_LABEL, PACKAGE_VERSION
from ...preview.metadata import (
    best_thumbnail_url, download_thumbnail_bytes, format_duration,
    friendly_source_name, preview_target_url, youtube_video_id,
)
from ...preview.service import fetch_preview
from ...services.network import (
    explain_download_error, is_internet_up, looks_like_connection_error,
    looks_like_cookie_database_error, looks_like_subtitle_rate_limit,
)
from ...services.cookies import inspect_netscape_cookie_file
from ...auth.sanitizer import is_adult_or_age_restricted_url, sanitize_log_text
from .account_panel import AccountSessionWidget
from .test_inbox import MailpitTestInboxWidget
from .dialogs import (
    AgeGateAuthDialog, AgeVerificationDialog, FontPreferencesDialog,
    HelpCenterDialog, KeyBindingsDialog, LibraryDialog, LinkHistoryDialog,
    SignInPromptDialog, SupportedPlatformsDialog, UpdateCheckDialog,
)
from .theme import apply_dark_theme
from .widgets import TransferStatusBar

try:
    import yt_dlp
except ImportError:
    yt_dlp = None


class PreviewWorker(QThread):
    """Fetch media metadata off the Qt event loop."""
    preview_ready = Signal(int, object)
    preview_failed = Signal(int, str)

    def __init__(self, token, url, browser, cookies_file, proxy, parent=None):
        super().__init__(parent)
        self.token = token
        self.url = url
        self.browser = browser
        self.cookies_file = cookies_file
        self.proxy = proxy

    def run(self):
        try:
            preview = fetch_preview(self.url, self.browser, self.cookies_file, self.proxy)
        except Exception as error:
            self.preview_failed.emit(self.token, str(error))
        else:
            self.preview_ready.emit(self.token, preview)


class ThumbnailDownloadWorker(QThread):
    """Download HQ thumbnail file asynchronously."""
    thumbnail_saved = Signal(str)
    thumbnail_failed = Signal(str)

    def __init__(self, thumbnail_url, title, output_dir, parent=None):
        super().__init__(parent)
        self.thumbnail_url = thumbnail_url
        self.title = title
        self.output_dir = output_dir

    def run(self):
        try:
            raw_bytes = download_thumbnail_bytes(self.thumbnail_url)
            if not raw_bytes:
                self.thumbnail_failed.emit("Failed to download thumbnail bytes from server.")
                return

            ext = ".jpg"
            if ".png" in self.thumbnail_url.lower():
                ext = ".png"
            elif ".webp" in self.thumbnail_url.lower():
                ext = ".webp"

            safe_title = re.sub(r'[\\/*?:"<>|]', '_', self.title or "thumbnail")
            save_path = os.path.join(self.output_dir, f"{safe_title}_HQ{ext}")

            with open(save_path, "wb") as f:
                f.write(raw_bytes)

            self.thumbnail_saved.emit(save_path)
        except Exception as err:
            self.thumbnail_failed.emit(str(err))


class FormatListWorker(QThread):
    """Inspect all available formats without blocking the main Qt event loop."""

    formats_ready = Signal(list)
    formats_failed = Signal(str)

    def __init__(self, url, browser, cookies_file, proxy, parent=None):
        super().__init__(parent)
        self.url = url
        self.browser = browser
        self.cookies_file = cookies_file
        self.proxy = proxy

    def run(self):
        try:
            if not yt_dlp:
                raise RuntimeError("yt-dlp library is missing.")
            options = {"quiet": True, "no_warnings": True, "noplaylist": True}
            if self.cookies_file and os.path.exists(self.cookies_file):
                options["cookiefile"] = self.cookies_file
            elif self.browser and self.browser not in ("None", "Custom cookies.txt file..."):
                options["cookiesfrombrowser"] = (self.browser.lower(),)
            if self.proxy:
                options["proxy"] = self.proxy
            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(self.url, download=False)
            rows = []
            for item in info.get("formats", []):
                rows.append({
                    "id": item.get("format_id", "?"),
                    "ext": item.get("ext", "?"),
                    "resolution": item.get("resolution") or item.get("format_note") or "audio",
                    "vcodec": item.get("vcodec", "none"),
                    "acodec": item.get("acodec", "none"),
                    "size": item.get("filesize") or item.get("filesize_approx"),
                })
            self.formats_ready.emit(rows)
        except Exception as error:
            self.formats_failed.emit(str(error))


class DownloadCancelled(Exception):
    """Raised from a progress hook to stop the active yt-dlp operation."""


def format_eta_clean(eta_seconds) -> str:
    """Format ETA seconds into clean rounded figures (e.g. '5m 49s' or '45s')."""
    if not eta_seconds or float(eta_seconds) <= 0:
        return "—"
    try:
        secs = int(round(float(eta_seconds)))
        if secs < 60:
            return f"{secs}s"
        mins = secs // 60
        rem_secs = secs % 60
        if mins < 60:
            return f"{mins}m {rem_secs:02d}s"
        hours = mins // 60
        rem_mins = mins % 60
        return f"{hours}h {rem_mins:02d}m"
    except Exception:
        return f"{eta_seconds}s"


class QtYTDLPLogger:
    """Forward status messages into the Qt log box, throttled every 10 seconds without tool prefixes."""

    def __init__(self, emit):
        self._emit = emit
        self._last_log_time = 0

    def debug(self, message):
        if not message:
            return
        text = str(message).strip()
        if text.startswith("[download]") or text.startswith("[debug]") or "frag" in text.lower():
            return
        now = time.time()
        if now - self._last_log_time >= 10.0:
            self._last_log_time = now
            clean_msg = re.sub(r"^\[[^\]]+\]\s*", "", text)
            self._emit(f"[STATUS] {clean_msg}")

    def warning(self, message):
        clean_msg = re.sub(r"^\[[^\]]+\]\s*", "", str(message or "").strip())
        self._emit(f"[WARNING] {clean_msg}")

    def error(self, message):
        clean_msg = re.sub(r"^\[[^\]]+\]\s*", "", str(message or "").strip())
        self._emit(f"[ERROR] {clean_msg}")


class QtDownloadWorker(QThread):
    """Download media queue on a background QThread with real-time Qt signals."""
    log_emitted = Signal(str)
    progress_updated = Signal(dict)
    status_updated = Signal(str)
    item_finished = Signal(str, bool, str)
    queue_completed = Signal(int, int)

    def __init__(self, urls, settings, parent=None):
        super().__init__(parent)
        self.urls = urls
        self.settings = settings
        self.cancelled = False

    def cancel(self):
        self.cancelled = True

    def run(self):
        if not yt_dlp:
            self.log_emitted.emit("[ERROR] yt-dlp library is missing.")
            self.queue_completed.emit(0, len(self.urls))
            return

        success_count = 0
        failure_count = 0

        for index, url in enumerate(self.urls, 1):
            if self.cancelled:
                self.log_emitted.emit("[INFO] Download operation cancelled by user.")
                break

            self.log_emitted.emit(f"\n--- [Queue {index}/{len(self.urls)}] Processing {url} ---")
            self.status_updated.emit(f"Downloading item {index} of {len(self.urls)}...")

            success = self._download_with_retries(url)
            self.item_finished.emit(url, success, self.settings.get("format", "video"))
            if success:
                success_count += 1
            else:
                failure_count += 1

        self.status_updated.emit("Ready.")
        self.queue_completed.emit(success_count, failure_count)

    def _download_with_retries(self, url):
        """Retry recoverable failures while keeping the final error visible."""
        settings = dict(self.settings)
        cookie_fallback_used = False
        subtitle_fallback_used = False

        for attempt in range(1, MAX_RETRIES + 1):
            if self.cancelled:
                self.log_emitted.emit("[INFO] Item cancelled.")
                return False
            try:
                self._process_single_url(url, settings)
                return True
            except DownloadCancelled:
                self.log_emitted.emit("[INFO] Item cancelled.")
                return False
            except Exception as error:
                if (
                    not cookie_fallback_used
                    and settings.get("cookies_browser") not in (None, "", "None")
                    and looks_like_cookie_database_error(error)
                ):
                    cookie_fallback_used = True
                    settings["cookies_browser"] = "None"
                    self.log_emitted.emit(
                        "[WARNING] Browser cookies could not be read; retrying without them. "
                        "Close the browser or use cookies.txt if sign-in is required."
                    )
                    continue
                if (
                    not subtitle_fallback_used
                    and settings.get("embed_subtitles")
                    and looks_like_subtitle_rate_limit(error)
                ):
                    subtitle_fallback_used = True
                    settings["embed_subtitles"] = False
                    self.log_emitted.emit(
                        "[WARNING] Subtitle service rate-limited this request; retrying the media without subtitles."
                    )
                    continue
                if looks_like_connection_error(error) and attempt < MAX_RETRIES:
                    self.status_updated.emit(f"Connection issue; retrying ({attempt}/{MAX_RETRIES})...")
                    self.log_emitted.emit(
                        f"[WARNING] Network error. Retrying in {RETRY_WAIT_SECONDS}s "
                        f"({attempt}/{MAX_RETRIES})..."
                    )
                    time.sleep(RETRY_WAIT_SECONDS)
                    if not is_internet_up():
                        self.log_emitted.emit("[WARNING] Internet connection still unavailable; retry will continue when possible.")
                    continue
                self.log_emitted.emit(f"[ERROR] Failed {url}: {explain_download_error(error)}")
                return False
        return False

    def _process_single_url(self, url, settings):
        output_dir = settings.get("output_dir") or get_default_output_dir()
        os.makedirs(output_dir, exist_ok=True)
        is_audio = settings.get("format") == "audio"
        target_ext = (AUDIO_FORMAT_EXTENSIONS if is_audio else VIDEO_FORMAT_EXTENSIONS).get(
            str(settings.get("output_format") or "").upper(), ""
        ).lower()
        if not target_ext:
            raise ValueError("Choose a valid output format before downloading.")

        def progress_hook(d):
            if self.cancelled:
                raise DownloadCancelled("Download cancelled by user")
            status = d.get("status")
            if status == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                downloaded = d.get("downloaded_bytes") or 0
                speed = d.get("speed") or 0
                eta = d.get("eta") or 0

                percent = (downloaded / total * 100.0) if total > 0 else 0
                self.progress_updated.emit({
                    "status": "Downloading...",
                    "progress": percent,
                    "download_rate": format_rate(speed),
                    "upload_rate": "0 B/s",
                    "transferred": f"{format_bytes(downloaded)} / {format_bytes(total)}" if total else format_bytes(downloaded),
                    "eta": format_eta_clean(eta),
                })
            elif status == "finished":
                self.log_emitted.emit("[INFO] Primary download complete. Finalizing media file...")

        ydl_opts = {
            "outtmpl": output_template(settings, output_dir, target_ext),
            "progress_hooks": [progress_hook],
            "noplaylist": settings.get("single_only", True),
            "quiet": True,
            "no_warnings": False,
            "age_limit": 99,
            "extractor_args": {"generic": ["impersonate"]},
            "logger": QtYTDLPLogger(self.log_emitted.emit),
            "retries": MAX_RETRIES,
            "fragment_retries": MAX_RETRIES,
            "file_access_retries": MAX_RETRIES,
            "http_headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
            },
            "postprocessors": [],
        }

        try:
            from yt_dlp.networking.impersonate import ImpersonateTarget
            ydl_opts["impersonate"] = ImpersonateTarget.from_str("chrome")
        except Exception:
            pass

        # Automatic DPAPI Account & Session Injection for current target URL
        try:
            target_domain = urllib.parse.urlparse(url).netloc
            if target_domain:
                from ...auth.manager import AuthManager
                session = AuthManager.resolve_domain_session(target_domain)
                if session:
                    account_lbl = session.get("account_label")
                    sec = session.get("secret")
                    if account_lbl and sec:
                        ydl_opts["username"] = account_lbl
                        ydl_opts["password"] = sec
                        self.log_emitted.emit(f"[INFO] Injected stored DPAPI account credentials for domain: {target_domain} ({account_lbl})")
                    else:
                        self.log_emitted.emit(f"[INFO] Injected active domain session for: {target_domain}")
        except Exception as auth_err:
            pass

        ffmpeg_path = settings.get("ffmpeg_path") or get_default_ffmpeg_path()
        if ffmpeg_path and os.path.exists(ffmpeg_path):
            ydl_opts["ffmpeg_location"] = ffmpeg_path
            self.log_emitted.emit(f"[INFO] Using FFmpeg binary: {ffmpeg_path}")
        else:
            self.log_emitted.emit("[WARNING] FFmpeg binary not found! Video merging and container conversion may be limited.")

        # Cookies configuration
        browser = settings.get("cookies_browser")
        cookies_file = settings.get("cookies_file")
        if cookies_file and os.path.exists(cookies_file):
            ydl_opts["cookiefile"] = cookies_file
        elif browser and browser not in ("None", "custom", "Custom cookies.txt file..."):
            ydl_opts["cookiesfrombrowser"] = (browser.lower(),)

        # Proxy configuration
        proxy = settings.get("proxy")
        if proxy:
            ydl_opts["proxy"] = proxy

        # Subtitles configuration
        if settings.get("embed_subtitles"):
            ydl_opts["writesubtitles"] = True
            if settings.get("auto_subtitles"):
                ydl_opts["writeautomaticsub"] = True
            sub_langs = [s.strip() for s in settings.get("subtitle_langs", "en").split(",") if s.strip()]
            ydl_opts["subtitleslangs"] = sub_langs or ["en"]
            ydl_opts["postprocessors"].append({"key": "FFmpegEmbedSubtitle"})

        # Metadata & thumbnail embedding
        if settings.get("embed_metadata", True):
            ydl_opts["postprocessors"].append({"key": "FFmpegMetadata", "add_chapters": True, "add_metadata": True})
        if settings.get("embed_thumbnail"):
            ydl_opts["writethumbnail"] = True
            ydl_opts["postprocessors"].append({"key": "FFmpegThumbnailsConvertor", "format": "jpg"})
            ydl_opts["postprocessors"].append({"key": "EmbedThumbnail"})

        # Live stream option
        if settings.get("live_start_from_beginning"):
            ydl_opts["live_from_start"] = True

        # Format & Quality selection
        exact_format_id = settings.get("exact_format_id")
        if exact_format_id:
            ydl_opts["format"] = exact_format_id
        elif is_audio:
            ydl_opts["format"] = "bestaudio/best"
        else:
            quality = settings.get("quality", "Best available")
            height = HEIGHT_MAP.get(quality)
            if height:
                ydl_opts["format"] = (
                    f"bestvideo[height={height}]+bestaudio/best[height={height}]"
                    f"/bestvideo[height<={height}]+bestaudio/best[height<={height}]"
                    f"/best[height<={height}]/best"
                )
            else:
                ydl_opts["format"] = "bestvideo+bestaudio/best"

        # Local output conversion. Audio uses the custom converter so every UI
        # target (including OGG, WMA, and AIFF) is handled consistently.
        if is_audio:
            audio_args = audio_conversion_args(settings, target_ext)
        else:
            ydl_opts["recode_video"] = target_ext
            ydl_opts["merge_output_format"] = "mp4" if target_ext == "mp4" else "mkv"
            video_args = video_conversion_args(settings, target_ext)

        started_at = time.time()
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            if is_audio:
                ydl.add_post_processor(FFmpegCustomAudioConvertPP(ydl, target_ext, audio_args))
            elif video_args:
                ydl.add_post_processor(FFmpegCustomReencodePP(ydl, target_ext, video_args))
            info = ydl.extract_info(url, download=True)

        if settings.get("clean_sidecars", True):
            clean_video_sidecars(output_dir, started_at, target_ext)
        self._report_selected_format(info, settings, target_ext)
        self.log_emitted.emit(f"[SUCCESS] Successfully processed: {url}")

    def _report_selected_format(self, info, settings, target_ext):
        """Make actual source and final conversion choices visible in the log."""
        if not isinstance(info, dict):
            return
        selected = info.get("requested_formats") or [info]
        stream_details = []
        selected_heights = []
        for item in selected:
            if not isinstance(item, dict):
                continue
            height = item.get("height")
            if height:
                selected_heights.append(height)
            role = "video" if item.get("vcodec") not in (None, "none") else "audio"
            resolution = item.get("resolution") or (f"{height}p" if height else "audio")
            codec = item.get("vcodec") if role == "video" else item.get("acodec")
            stream_details.append(
                f"{role}: id={item.get('format_id', '?')}, ext={item.get('ext', '?')}, "
                f"resolution={resolution}, codec={codec}"
            )
        if stream_details:
            self.log_emitted.emit("[FORMAT] Selected source " + " | ".join(stream_details))
        requested_height = HEIGHT_MAP.get(settings.get("quality"))
        if requested_height and selected_heights and max(selected_heights) < requested_height:
            self.log_emitted.emit(
                f"[FORMAT] Requested {requested_height}p; source only provided {max(selected_heights)}p. "
                "The highest accessible lower-quality stream was used."
            )
        conversion_resolution = settings.get("conversion_resolution", "Source")
        if conversion_resolution != "Source":
            self.log_emitted.emit(
                f"[FORMAT] Final output is intentionally scaled to {conversion_resolution}."
            )
        self.log_emitted.emit(f"[FORMAT] Final container target: {target_ext.upper()}")


class QtMainWindow(QMainWindow):
    """Production PySide6 MainWindow for GGU_VDOD bringing 100% legacy parity."""

    def __init__(self, settings=None, persist_settings=True):
        super().__init__()
        self._config = dict(load_config() if settings is None else settings)
        self._persist_settings = persist_settings
        self._preview_token = 0
        self._preview_workers = set()
        self._thumbnail_workers = set()
        self._format_workers = set()
        self._download_worker = None
        self._current_preview_data = None
        self._cookie_file_approved = False
        self._cookie_summary = None

        self.zoom_percent = ZOOM_DEFAULT_PERCENT

        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(500)
        self._preview_timer.timeout.connect(self._start_preview)

        self.setWindowTitle(APP_NAME)
        self.resize(1280, 880)
        self.setMinimumSize(900, 680)

        self._build_menu()
        self._build_content()
        self._restore_settings()
        self._connect_ui()
        self._apply_preferences()

    def _build_menu(self):
        menubar = self.menuBar()

        # File Menu
        file_menu = menubar.addMenu("File")
        new_list_act = QAction("New link list", self)
        new_list_act.setShortcut(QKeySequence("Ctrl+N"))
        new_list_act.triggered.connect(self._new_link_list)
        file_menu.addAction(new_list_act)

        open_folder_act = QAction("Open save folder", self)
        open_folder_act.triggered.connect(self._open_output_folder)
        file_menu.addAction(open_folder_act)

        history_act = QAction("Link history...", self)
        history_act.setShortcut(QKeySequence("Ctrl+H"))
        history_act.triggered.connect(self._show_history_dialog)
        file_menu.addAction(history_act)

        file_menu.addSeparator()
        exit_act = QAction("Exit", self)
        exit_act.setShortcut(QKeySequence("Alt+F4"))
        exit_act.triggered.connect(self.close)
        file_menu.addAction(exit_act)

        # Edit Menu
        edit_menu = menubar.addMenu("Edit")
        undo_act = QAction("Undo", self)
        undo_act.setShortcut(QKeySequence.Undo)
        undo_act.triggered.connect(lambda: self._edit_focused("undo"))
        edit_menu.addAction(undo_act)

        redo_act = QAction("Redo", self)
        redo_act.setShortcut(QKeySequence.Redo)
        redo_act.triggered.connect(lambda: self._edit_focused("redo"))
        edit_menu.addAction(redo_act)

        edit_menu.addSeparator()
        cut_act = QAction("Cut", self)
        cut_act.setShortcut(QKeySequence.Cut)
        cut_act.triggered.connect(lambda: self._edit_focused("cut"))
        edit_menu.addAction(cut_act)

        copy_act = QAction("Copy", self)
        copy_act.setShortcut(QKeySequence.Copy)
        copy_act.triggered.connect(lambda: self._edit_focused("copy"))
        edit_menu.addAction(copy_act)

        paste_act = QAction("Paste", self)
        paste_act.setShortcut(QKeySequence.Paste)
        paste_act.triggered.connect(lambda: self._edit_focused("paste"))
        edit_menu.addAction(paste_act)

        select_all_act = QAction("Select all", self)
        select_all_act.setShortcut(QKeySequence.SelectAll)
        select_all_act.triggered.connect(lambda: self._edit_focused("select_all"))
        edit_menu.addAction(select_all_act)

        edit_menu.addSeparator()
        pref_bindings_act = QAction("Preferences - Key bindings and scroll speed...", self)
        pref_bindings_act.triggered.connect(self._show_key_bindings_dialog)
        edit_menu.addAction(pref_bindings_act)

        pref_font_act = QAction("Preferences - UI Font panel...", self)
        pref_font_act.triggered.connect(self._show_font_dialog)
        edit_menu.addAction(pref_font_act)

        # View Menu
        view_menu = menubar.addMenu("View")
        library_act = QAction("Downloaded content library...", self)
        library_act.setShortcut(QKeySequence("Ctrl+L"))
        library_act.triggered.connect(self._show_library_dialog)
        view_menu.addAction(library_act)

        view_menu.addSeparator()
        zoom_in_act = QAction("Zoom in", self)
        zoom_in_act.triggered.connect(lambda: self._change_zoom(ZOOM_STEP_PERCENT))
        view_menu.addAction(zoom_in_act)

        zoom_out_act = QAction("Zoom out", self)
        zoom_out_act.triggered.connect(lambda: self._change_zoom(-ZOOM_STEP_PERCENT))
        view_menu.addAction(zoom_out_act)

        zoom_reset_act = QAction("Reset zoom", self)
        zoom_reset_act.triggered.connect(lambda: self._apply_zoom(ZOOM_DEFAULT_PERCENT))
        view_menu.addAction(zoom_reset_act)
        self._zoom_actions = {
            "zoom_in": zoom_in_act,
            "zoom_out": zoom_out_act,
            "zoom_reset": zoom_reset_act,
        }

        # Help Menu
        help_menu = menubar.addMenu("Help")
        help_center_act = QAction("Help center", self)
        help_center_act.triggered.connect(self._show_help_dialog)
        help_menu.addAction(help_center_act)

        platforms_act = QAction("Supported platforms and extractors...", self)
        platforms_act.triggered.connect(self._show_supported_platforms_dialog)
        help_menu.addAction(platforms_act)

        updates_act = QAction("Check for updates & dependencies...", self)
        updates_act.triggered.connect(self._show_updates_dialog)
        help_menu.addAction(updates_act)

        about_menu = menubar.addMenu("About")
        about_act = QAction("About GGU_VDOD", self)
        about_act.triggered.connect(self._show_about_dialog)
        about_menu.addAction(about_act)

    def _build_content(self):
        root = QWidget()
        main_vbox = QVBoxLayout(root)
        main_vbox.setContentsMargins(0, 0, 0, 0)
        main_vbox.setSpacing(0)

        # Scroll Area for main content
        self.content_scroll = QScrollArea()
        self.content_scroll.setWidgetResizable(True)
        self.content_scroll.setFrameShape(QFrame.NoFrame)

        scroll_content = QWidget()
        layout = QVBoxLayout(scroll_content)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        # Header Title
        title = QLabel(APP_NAME)
        title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        title.setStyleSheet("font-size: 26px; font-weight: 700;")
        subtitle = QLabel("Paste one or more video links below (one per line)")
        subtitle.setObjectName("muted")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(title)
        layout.addWidget(subtitle)

        # URL Text Box
        self.url_text = QPlainTextEdit()
        self.url_text.setPlaceholderText("https://www.youtube.com/watch?v=...")
        self.url_text.setMinimumHeight(120)
        self.url_text.setToolTip("Paste one or multiple video/audio URLs (one per line) or playlist links here.")
        layout.addWidget(self.url_text)

        # Video Preview Box
        preview = QFrame()
        preview.setObjectName("panel")
        preview_layout = QVBoxLayout(preview)
        preview_layout.setContentsMargins(16, 12, 16, 12)
        preview_title_lbl = QLabel("Video preview")
        preview_title_lbl.setStyleSheet("font-weight: 600; color: #a7a7a7;")
        preview_layout.addWidget(preview_title_lbl)

        preview_body = QHBoxLayout()
        self.preview_image = QLabel("No preview")
        self.preview_image.setFixedSize(PREVIEW_WIDTH, PREVIEW_HEIGHT)
        self.preview_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_image.setStyleSheet("border: 1px solid #303030; border-radius: 6px; background: #111;")
        preview_body.addWidget(self.preview_image)

        preview_text_vbox = QVBoxLayout()
        self.preview_title = QLabel("Paste a link to preview it")
        self.preview_title.setStyleSheet("font-size: 15px; font-weight: 600;")
        self.preview_source = QLabel("Source: waiting for a link")
        self.preview_source.setObjectName("muted")
        self.preview_details = QLabel("Title, duration, uploader, and platform will appear here.")
        self.preview_details.setObjectName("muted")
        self.preview_details.setWordWrap(True)

        self.download_thumbnail_btn = QPushButton("Download thumbnail (HQ)")
        self.download_thumbnail_btn.setEnabled(False)
        self.download_thumbnail_btn.setFixedWidth(180)
        self.download_thumbnail_btn.setToolTip("Save high-resolution thumbnail image for the previewed video.")
        self.download_thumbnail_btn.clicked.connect(self._download_thumbnail_file)

        self.preview_status = QLabel("Waiting for a link")
        self.preview_status.setObjectName("muted")
        self.preview_status.setWordWrap(True)

        preview_text_vbox.addWidget(self.preview_title)
        preview_text_vbox.addWidget(self.preview_source)
        preview_text_vbox.addWidget(self.preview_details)
        preview_text_vbox.addWidget(self.download_thumbnail_btn)
        preview_text_vbox.addWidget(self.preview_status)
        preview_text_vbox.addStretch(1)

        preview_body.addLayout(preview_text_vbox, 1)
        preview_layout.addLayout(preview_body)
        layout.addWidget(preview)

        # Format & Quality Options Panel
        fmt_panel = QFrame()
        fmt_panel.setObjectName("panel")
        fmt_grid = QGridLayout(fmt_panel)
        fmt_grid.setContentsMargins(16, 14, 16, 14)
        fmt_grid.setHorizontalSpacing(16)
        fmt_grid.setVerticalSpacing(10)

        self.video_radio = QRadioButton("Video")
        self.audio_radio = QRadioButton("Audio only")
        self.video_radio.setChecked(True)
        self.video_radio.setToolTip("Download video streams with selectable resolution.")
        self.audio_radio.setToolTip("Extract audio tracks and convert to MP3, M4A, WAV, FLAC, OPUS, etc.")
        self.format_group = QButtonGroup(self)
        self.format_group.addButton(self.video_radio)
        self.format_group.addButton(self.audio_radio)

        self.single_only_check = QCheckBox("Only download this video (ignore playlist)")
        self.single_only_check.setChecked(True)
        self.single_only_check.setToolTip("Ignore playlist context and download only the specific video link.")

        self.quality_combo = QComboBox()
        self.quality_combo.addItems(VIDEO_QUALITIES)
        self.quality_combo.setToolTip("Select desired video resolution (e.g. 2160p 4K, 1080p, 720p, 480p) or audio bitrate.")

        self.output_format_combo = QComboBox()
        self.output_format_combo.addItems(VIDEO_OUTPUT_FORMATS)
        self.output_format_combo.setToolTip("Select output container format (MP4, MKV, MP3, WAV, etc.).")

        fmt_grid.addWidget(self.video_radio, 0, 0)
        fmt_grid.addWidget(self.audio_radio, 0, 1)
        fmt_grid.addWidget(QLabel("Quality:"), 1, 0)
        fmt_grid.addWidget(self.quality_combo, 1, 1)
        fmt_grid.addWidget(QLabel("Save as:"), 2, 0)
        fmt_grid.addWidget(self.output_format_combo, 2, 1)
        fmt_grid.addWidget(self.single_only_check, 3, 0, 1, 3)
        fmt_grid.setColumnStretch(2, 1)
        layout.addWidget(fmt_panel)

        # Save Folder Picker Panel
        save_panel = QFrame()
        save_panel.setObjectName("panel")
        save_row = QHBoxLayout(save_panel)
        save_row.setContentsMargins(16, 12, 16, 12)
        save_row.setSpacing(12)
        self.output_path = QLineEdit()
        self.output_path.setPlaceholderText("Save folder")
        self.output_path.setToolTip("Destination folder where downloaded media files will be saved.")
        self.browse_button = QPushButton("Browse…")
        self.browse_button.setToolTip("Browse and select a destination folder on your computer.")
        save_row.addWidget(QLabel("Save to:"))
        save_row.addWidget(self.output_path, 1)
        save_row.addWidget(self.browse_button)
        layout.addWidget(save_panel)

        # ------------------ Complex & Advanced Options Card Header ------------------
        adv_header_frame = QFrame()
        adv_header_frame.setObjectName("panel")
        adv_header_frame.setStyleSheet("QFrame#panel { background: #121212; border: 1px solid #333333; border-radius: 6px; padding: 2px 6px; }")
        adv_header_layout = QHBoxLayout(adv_header_frame)
        adv_header_layout.setContentsMargins(10, 4, 10, 4)

        adv_title_label = QLabel("Complex & Advanced Conversion Options", self)
        adv_title_label.setStyleSheet("font-weight: 600; color: #e5e5e5;")

        advanced_toggle = QToolButton(self)
        advanced_toggle.setText("Expand [+]")
        advanced_toggle.setCheckable(True)
        advanced_toggle.setStyleSheet(
            "QToolButton { background: #1f1f1f; color: #ffffff; border: 1px solid #383838; border-radius: 4px; padding: 4px 10px; font-weight: 600; } "
            "QToolButton:hover { background: #2a2a2a; border-color: #e5484d; }"
        )
        advanced_toggle.setToolTip("Expand or collapse advanced FFmpeg, cookie, proxy, subtitle, and codec settings.")

        self.complex_help_btn = QToolButton(self)
        self.complex_help_btn.setText("Help [?]")
        self.complex_help_btn.setStyleSheet(
            "QToolButton { background: #e5484d; color: #ffffff; border: 1px solid #e5484d; border-radius: 4px; padding: 4px 10px; font-weight: bold; } "
            "QToolButton:hover { background: #c53f43; }"
        )
        self.complex_help_btn.setToolTip("Click to view detailed explanations for all complex video, audio, codec, and network options.")
        self.complex_help_btn.clicked.connect(self._show_complex_options_help)

        adv_header_layout.addWidget(adv_title_label)
        adv_header_layout.addStretch(1)
        adv_header_layout.addWidget(advanced_toggle)
        adv_header_layout.addWidget(self.complex_help_btn)

        layout.addWidget(adv_header_frame)

        self.advanced_panel = QFrame()
        self.advanced_panel.setObjectName("panel")
        adv_vbox = QVBoxLayout(self.advanced_panel)
        adv_vbox.setContentsMargins(14, 12, 14, 12)
        adv_vbox.setSpacing(12)

        # ------------------ Box 1: FFmpeg location ------------------
        ffmpeg_box = QGroupBox("FFmpeg location (auto-detected - change only if needed)")
        ffmpeg_layout = QVBoxLayout(ffmpeg_box)
        ffmpeg_row = QHBoxLayout()
        detected_ffmpeg = get_default_ffmpeg_path()
        self.ffmpeg_path_input = QLineEdit(detected_ffmpeg)
        self.ffmpeg_path_input.setPlaceholderText("Path to ffmpeg.exe")
        self.ffmpeg_path_input.setToolTip("Path to ffmpeg.exe binary for audio extraction, merging, and local re-encoding.")
        self.ffmpeg_browse_btn = QPushButton("Browse…")
        self.ffmpeg_browse_btn.setToolTip("Browse for ffmpeg.exe on your system.")
        self.ffmpeg_browse_btn.clicked.connect(self._choose_ffmpeg_file)
        ffmpeg_row.addWidget(self.ffmpeg_path_input, 1)
        ffmpeg_row.addWidget(self.ffmpeg_browse_btn)
        ffmpeg_layout.addLayout(ffmpeg_row)

        self.ffmpeg_status_label = QLabel()
        self._update_ffmpeg_status_label()
        ffmpeg_layout.addWidget(self.ffmpeg_status_label)
        adv_vbox.addWidget(ffmpeg_box)

        # ------------------ Box 2: Authentication and output options ------------------
        auth_box = QGroupBox("Authentication and output options")
        auth_grid = QGridLayout(auth_box)
        auth_grid.setContentsMargins(12, 10, 12, 10)
        auth_grid.setHorizontalSpacing(14)
        auth_grid.setVerticalSpacing(8)

        self.cookie_browser_combo = QComboBox()
        self.cookie_browser_combo.addItems(["None", "chrome", "edge", "firefox", "brave", "vivaldi", "opera", "safari", "Custom cookies.txt file..."])
        self.cookie_browser_combo.setToolTip("Import browser cookies to bypass login screens or age restrictions.")

        cookie_row = QHBoxLayout()
        self.cookie_file_input = QLineEdit()
        self.cookie_file_input.setPlaceholderText("Path to cookies.txt")
        self.cookie_file_input.setToolTip("Validated Netscape-format cookies.txt file used only with your confirmation.")
        self.remember_cookie_path_check = QCheckBox("Remember path")
        self.remember_cookie_path_check.setToolTip("Save only the file path, never cookie contents. You will still confirm before use.")
        self.cookie_browse_btn = QPushButton("Browse…")
        self.cookie_browse_btn.setToolTip("Browse and select a cookies.txt file.")
        self.cookie_browse_btn.clicked.connect(self._choose_cookie_file)
        self.cookie_browse_btn.setText("Import and validate")
        cookie_row.addWidget(self.cookie_file_input, 1)
        cookie_row.addWidget(self.remember_cookie_path_check)
        cookie_row.addWidget(self.cookie_browse_btn)

        self.proxy_input = QLineEdit()
        self.proxy_input.setPlaceholderText("http://user:pass@host:port")
        self.proxy_input.setToolTip("Route downloads through HTTP/HTTPS/SOCKS proxy server.")

        self.check_library_btn = QPushButton("Check library updates")
        self.check_library_btn.setToolTip("Check for online updates to yt-dlp and FFmpeg core modules.")
        self.check_library_btn.clicked.connect(self._show_updates_dialog)

        auth_grid.addWidget(QLabel("Browser cookies:"), 0, 0)
        auth_grid.addWidget(self.cookie_browser_combo, 0, 1)
        auth_grid.addWidget(QLabel("Cookies file:"), 1, 0)
        auth_grid.addLayout(cookie_row, 1, 1, 1, 2)
        auth_grid.addWidget(QLabel("Proxy (optional):"), 2, 0)
        auth_grid.addWidget(self.proxy_input, 2, 1)
        auth_grid.addWidget(self.check_library_btn, 2, 2)

        # Subtitles row
        sub_row = QHBoxLayout()
        self.download_subs_check = QCheckBox("Download subtitles")
        self.download_subs_check.setToolTip("Download closed caption / subtitle files.")
        self.auto_subs_check = QCheckBox("Include auto-generated")
        self.auto_subs_check.setToolTip("Include automatically generated subtitle tracks.")
        self.sub_lang_input = QLineEdit("en.*")
        self.sub_lang_input.setFixedWidth(100)
        self.sub_lang_input.setToolTip("Comma-separated language codes or regex patterns (e.g. en.*, es, fr).")
        sub_row.addWidget(self.download_subs_check)
        sub_row.addWidget(self.auto_subs_check)
        sub_row.addWidget(QLabel("Languages:"))
        sub_row.addWidget(self.sub_lang_input)
        sub_row.addStretch(1)
        auth_grid.addLayout(sub_row, 3, 0, 1, 3)

        # Metadata row
        meta_row = QHBoxLayout()
        self.embed_metadata_check = QCheckBox("Embed metadata")
        self.embed_metadata_check.setChecked(True)
        self.embed_metadata_check.setToolTip("Embed media title, artist, uploader, and release tags directly into output files.")
        self.embed_thumb_check = QCheckBox("Embed thumbnail")
        self.embed_thumb_check.setToolTip("Embed video thumbnail image into output audio/video file cover art.")
        self.live_start_check = QCheckBox("Live: start from beginning")
        self.live_start_check.setToolTip("For ongoing live streams, start downloading from the beginning.")
        meta_row.addWidget(self.embed_metadata_check)
        meta_row.addWidget(self.embed_thumb_check)
        meta_row.addWidget(self.live_start_check)
        meta_row.addStretch(1)
        auth_grid.addLayout(meta_row, 4, 0, 1, 3)

        # Format ID row
        fmt_id_row = QHBoxLayout()
        fmt_id_row.addWidget(QLabel("Exact format ID(s) (optional):"))
        self.format_id_input = QLineEdit()
        self.format_id_input.setToolTip("Specify custom yt-dlp format codes (e.g. 137+140).")
        self.list_formats_btn = QPushButton("List formats")
        self.list_formats_btn.setToolTip("Fetch and display all available format IDs for the entered video URL.")
        self.list_formats_btn.clicked.connect(self._list_formats)
        fmt_id_row.addWidget(self.format_id_input, 1)
        fmt_id_row.addWidget(self.list_formats_btn)
        auth_grid.addLayout(fmt_id_row, 5, 0, 1, 3)

        adv_vbox.addWidget(auth_box)

        # ------------------ Box 3: Local conversion settings ------------------
        conv_box = QGroupBox("Local conversion settings")
        conv_grid = QGridLayout(conv_box)
        conv_grid.setContentsMargins(12, 10, 12, 10)
        conv_grid.setHorizontalSpacing(14)
        conv_grid.setVerticalSpacing(8)

        self.video_codec_combo = QComboBox()
        self.video_codec_combo.addItems(VIDEO_CODEC_OPTIONS)
        self.video_codec_combo.setToolTip("Select video re-encoding codec (H.264, HEVC, VP9, AV1, ProRes, MPEG-4).")

        self.video_bitrate_input = QLineEdit()
        self.video_bitrate_input.setPlaceholderText("Auto (e.g. 8000k)")
        self.video_bitrate_input.setToolTip("Specify custom video bitrate (e.g. 8000k, 12M). Leave blank for auto.")

        self.resolution_combo = QComboBox()
        self.resolution_combo.addItems(VIDEO_RESOLUTION_OPTIONS)
        self.resolution_combo.setToolTip("Override video resolution scaling.")

        self.frame_rate_combo = QComboBox()
        self.frame_rate_combo.addItems(FRAME_RATE_OPTIONS)
        self.frame_rate_combo.setToolTip("Override video frame rate (FPS) during local re-encoding.")

        self.sample_rate_combo = QComboBox()
        self.sample_rate_combo.addItems(SAMPLE_RATE_OPTIONS)
        self.sample_rate_combo.setToolTip("Override audio sampling frequency (e.g. 44100 Hz, 48000 Hz).")

        self.channel_combo = QComboBox()
        self.channel_combo.addItems(CHANNEL_OPTIONS)
        self.channel_combo.setToolTip("Override audio channel layout (Source, Mono, Stereo).")

        self.compression_combo = QComboBox()
        self.compression_combo.addItems(COMPRESSION_OPTIONS)
        self.compression_combo.setToolTip("Set compression level for FLAC or OPUS audio encoders.")

        self.pattern_input = QLineEdit()
        self.pattern_input.setPlaceholderText("%(title)s [%(height)sp]")
        self.pattern_input.setToolTip("Customize output filename template pattern (e.g. %(title)s [%(height)sp]).")

        self.clean_sidecars_check = QCheckBox("Clean temporary sidecar files after conversion")
        self.clean_sidecars_check.setChecked(True)
        self.clean_sidecars_check.setToolTip("Automatically remove intermediate conversion files and sidecars after processing.")

        conv_grid.addWidget(QLabel("Video codec:"), 0, 0)
        conv_grid.addWidget(self.video_codec_combo, 0, 1)
        conv_grid.addWidget(QLabel("Video bitrate:"), 0, 2)
        conv_grid.addWidget(self.video_bitrate_input, 0, 3)

        conv_grid.addWidget(QLabel("Resolution:"), 1, 0)
        conv_grid.addWidget(self.resolution_combo, 1, 1)
        conv_grid.addWidget(QLabel("FPS:"), 1, 2)
        conv_grid.addWidget(self.frame_rate_combo, 1, 3)

        conv_grid.addWidget(QLabel("Sample rate:"), 2, 0)
        conv_grid.addWidget(self.sample_rate_combo, 2, 1)
        conv_grid.addWidget(QLabel("Channels:"), 2, 2)
        conv_grid.addWidget(self.channel_combo, 2, 3)

        conv_grid.addWidget(QLabel("Compression:"), 3, 0)
        conv_grid.addWidget(self.compression_combo, 3, 1)

        conv_grid.addWidget(QLabel("Filename pattern (optional):"), 4, 0)
        conv_grid.addWidget(self.pattern_input, 4, 1, 1, 3)

        conv_grid.addWidget(self.clean_sidecars_check, 5, 0, 1, 4)

        adv_vbox.addWidget(conv_box)

        self.advanced_panel.setVisible(False)
        advanced_toggle.toggled.connect(lambda open_: self.advanced_panel.setVisible(open_))
        advanced_toggle.toggled.connect(lambda open_: advanced_toggle.setText("Collapse [-]" if open_ else "Expand [+]"))
        layout.addWidget(self.advanced_panel)

        # Download Actions Row
        action_row = QHBoxLayout()
        action_row.setContentsMargins(4, 10, 4, 10)
        action_row.setSpacing(12)

        self.download_button = QPushButton("Download")
        self.download_button.setObjectName("primary")
        self.download_button.setMinimumHeight(38)
        self.download_button.setMinimumWidth(130)
        self.download_button.setToolTip("Start downloading all links currently in the queue.")

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setMinimumHeight(38)
        self.cancel_button.setMinimumWidth(100)
        self.cancel_button.setEnabled(False)
        self.cancel_button.setToolTip("Cancel ongoing download operations.")

        self.open_folder_button = QPushButton("Open Save Folder")
        self.open_folder_button.setMinimumHeight(38)
        self.open_folder_button.setToolTip("Open the save directory in Windows File Explorer.")

        action_row.addWidget(self.download_button)
        action_row.addWidget(self.cancel_button)
        action_row.addWidget(self.open_folder_button)
        action_row.addStretch(1)
        layout.addLayout(action_row)

        # Log Section
        log_frame = QFrame()
        log_frame.setObjectName("panel")
        log_layout = QVBoxLayout(log_frame)
        log_layout.setContentsMargins(12, 10, 12, 10)

        log_hdr = QHBoxLayout()
        log_hdr.addWidget(QLabel("Log Stream"))
        log_hdr.addStretch(1)
        clear_log_btn = QPushButton("Clear Log")
        clear_log_btn.setFixedWidth(90)
        clear_log_btn.clicked.connect(lambda: self.log_box.clear())
        log_hdr.addWidget(clear_log_btn)
        log_layout.addLayout(log_hdr)

        self.log_box = QPlainTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setMinimumHeight(150)
        self.log_box.setStyleSheet("font-family: Consolas, monospace; font-size: 12px; background: #080808;")
        log_layout.addWidget(self.log_box)
        layout.addWidget(log_frame)

        self.content_scroll.setWidget(scroll_content)

        # Main Tab Widget
        self.main_tab_widget = QTabWidget()
        self.main_tab_widget.addTab(self.content_scroll, "📥 Downloader & Queue")

        self.account_widget = AccountSessionWidget(self)
        self.main_tab_widget.addTab(self.account_widget, "🔑 Account & Sessions")

        self.test_inbox_widget = MailpitTestInboxWidget(self)
        self.main_tab_widget.addTab(self.test_inbox_widget, "📬 Local Test Inbox (Mailpit)")

        main_vbox.addWidget(self.main_tab_widget, 1)

        # Status Bar
        self.transfer_status = TransferStatusBar()
        main_vbox.addWidget(self.transfer_status)

        self.setCentralWidget(root)

    def _connect_ui(self):
        self.url_text.textChanged.connect(self._schedule_preview)
        self.video_radio.toggled.connect(self._sync_format_controls)
        self.cookie_file_input.textChanged.connect(self._invalidate_cookie_consent)
        self.browse_button.clicked.connect(self._choose_output_folder)
        self.open_folder_button.clicked.connect(self._open_output_folder)
        self.download_button.clicked.connect(self._start_download)
        self.cancel_button.clicked.connect(self._cancel_download)

    def _restore_settings(self):
        is_audio = self._config.get("format", "video") == "audio"
        if is_audio:
            self.audio_radio.setChecked(True)
        else:
            self.video_radio.setChecked(True)
        self._sync_format_controls(not is_audio)
        self._set_combo_value(self.quality_combo, self._config.get("quality"))
        self._set_combo_value(self.output_format_combo, self._config.get("output_format"))
        self.output_path.setText(self._config.get("output_dir") or get_default_output_dir())
        self.single_only_check.setChecked(self._config.get("single_only", self._config.get("only_this_video", True)))
        self.ffmpeg_path_input.setText(self._config.get("ffmpeg_path") or get_default_ffmpeg_path())
        self._update_ffmpeg_status_label()
        self._set_combo_value(self.cookie_browser_combo, self._config.get("cookies_browser"))
        self.remember_cookie_path_check.setChecked(self._config.get("remember_cookie_file", False))
        self.cookie_file_input.setText(self._config.get("cookies_file", ""))
        self._cookie_file_approved = False
        self._cookie_summary = None
        self.proxy_input.setText(self._config.get("proxy", ""))
        self.download_subs_check.setChecked(self._config.get("embed_subtitles", self._config.get("subtitles", False)))
        self.auto_subs_check.setChecked(self._config.get("auto_subtitles", False))
        self.sub_lang_input.setText(self._config.get("subtitle_langs", self._config.get("subtitle_languages", "en.*")))
        self.embed_metadata_check.setChecked(self._config.get("embed_metadata", True))
        self.embed_thumb_check.setChecked(self._config.get("embed_thumbnail", False))
        self.live_start_check.setChecked(self._config.get("live_start_from_beginning", self._config.get("live_from_start", False)))
        self.format_id_input.setText(self._config.get("exact_format_id", self._config.get("format_id", "")))
        self._set_combo_value(self.video_codec_combo, self._config.get("video_codec"))
        self.video_bitrate_input.setText(self._config.get("video_bitrate", ""))
        self._set_combo_value(self.resolution_combo, self._config.get("conversion_resolution"))
        self._set_combo_value(self.frame_rate_combo, self._config.get("frame_rate"))
        self._set_combo_value(self.sample_rate_combo, self._config.get("sample_rate"))
        self._set_combo_value(self.channel_combo, self._config.get("channels"))
        self._set_combo_value(self.compression_combo, self._config.get("compression_level"))
        self.pattern_input.setText(self._config.get("filename_pattern", ""))
        self.clean_sidecars_check.setChecked(self._config.get("clean_sidecars", True))

    def _choose_ffmpeg_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select ffmpeg.exe", "", "Executables (*.exe);;All files (*.*)")
        if file_path:
            self.ffmpeg_path_input.setText(file_path)
            self._update_ffmpeg_status_label()

    def _update_ffmpeg_status_label(self):
        path = self.ffmpeg_path_input.text().strip()
        if path and os.path.exists(path):
            self.ffmpeg_status_label.setText(f"✔ Using: {path}")
            self.ffmpeg_status_label.setStyleSheet("color: #57c26a; font-weight: 500;")
        else:
            self.ffmpeg_status_label.setText("⚠ FFmpeg executable not found at specified path. System PATH will be used.")
            self.ffmpeg_status_label.setStyleSheet("color: #e5b84d; font-weight: 500;")

    def _list_formats(self):
        url = self._first_url()
        if not url:
            QMessageBox.warning(self, "No URL", "Paste a video link first to list available formats.")
            return
        if not self._ensure_cookie_file_consent():
            return

        self.log_box.appendPlainText(f"\n[INFO] Fetching exact format IDs for {url}...")
        self.list_formats_btn.setEnabled(False)
        worker = FormatListWorker(
            url,
            self.cookie_browser_combo.currentText(),
            self.cookie_file_input.text().strip() if self._cookie_file_approved else "",
            self.proxy_input.text().strip(),
            self,
        )
        worker.formats_ready.connect(self._show_format_list)
        worker.formats_failed.connect(lambda error: self.log_box.appendPlainText(f"[ERROR] Failed to fetch formats: {error}"))
        worker.finished.connect(lambda: self.list_formats_btn.setEnabled(True))
        worker.finished.connect(lambda: self._format_workers.discard(worker))
        worker.finished.connect(worker.deleteLater)
        self._format_workers.add(worker)
        worker.start()

    def _show_format_list(self, formats):
        self.log_box.appendPlainText(f"\nAvailable Formats ({len(formats)}):")
        self.log_box.appendPlainText("format_id | ext  | resolution   | video codec  | audio codec  | size")
        for item in formats:
            self.log_box.appendPlainText(
                f"{str(item['id']):>8} | {item['ext']:<4} | {item['resolution']:<12} | "
                f"{item['vcodec']:<12} | {item['acodec']:<12} | {item['size'] or '?'}"
            )

    @staticmethod
    def _set_combo_value(combo, value):
        index = combo.findText(value or "")
        if index >= 0:
            combo.setCurrentIndex(index)

    def _sync_format_controls(self, video_selected):
        previous_quality = self.quality_combo.currentText()
        previous_output = self.output_format_combo.currentText()
        self.quality_combo.clear()
        self.output_format_combo.clear()
        if video_selected:
            self.quality_combo.addItems(VIDEO_QUALITIES)
            self.output_format_combo.addItems(VIDEO_OUTPUT_FORMATS)
        else:
            self.quality_combo.addItems(AUDIO_QUALITIES)
            self.output_format_combo.addItems(AUDIO_OUTPUT_FORMATS)
        self._set_combo_value(self.quality_combo, previous_quality)
        self._set_combo_value(self.output_format_combo, previous_output)

    def _settings_from_ui(self, include_cookie_file=False):
        """Return every user-facing setting using the stable Qt configuration schema."""
        cookie_file = self.cookie_file_input.text().strip()
        remember_cookie_file = self.remember_cookie_path_check.isChecked()
        return {
            "format": "video" if self.video_radio.isChecked() else "audio",
            "quality": self.quality_combo.currentText(),
            "output_format": self.output_format_combo.currentText(),
            "output_dir": self.output_path.text().strip(),
            "single_only": self.single_only_check.isChecked(),
            "ffmpeg_path": self.ffmpeg_path_input.text().strip(),
            "cookies_browser": self.cookie_browser_combo.currentText(),
            "cookies_file": cookie_file if include_cookie_file or remember_cookie_file else "",
            "remember_cookie_file": remember_cookie_file,
            "proxy": self.proxy_input.text().strip(),
            "embed_subtitles": self.download_subs_check.isChecked(),
            "auto_subtitles": self.auto_subs_check.isChecked(),
            "subtitle_langs": self.sub_lang_input.text().strip() or "en.*",
            "embed_metadata": self.embed_metadata_check.isChecked(),
            "embed_thumbnail": self.embed_thumb_check.isChecked(),
            "live_start_from_beginning": self.live_start_check.isChecked(),
            "exact_format_id": self.format_id_input.text().strip(),
            "video_codec": self.video_codec_combo.currentText(),
            "video_bitrate": self.video_bitrate_input.text().strip(),
            "conversion_resolution": self.resolution_combo.currentText(),
            "frame_rate": self.frame_rate_combo.currentText(),
            "sample_rate": self.sample_rate_combo.currentText(),
            "channels": self.channel_combo.currentText(),
            "compression_level": self.compression_combo.currentText(),
            "filename_pattern": self.pattern_input.text().strip(),
            "clean_sidecars": self.clean_sidecars_check.isChecked(),
            "key_bindings": dict(self._config.get("key_bindings", DEFAULT_KEY_BINDINGS)),
            "scroll_speed": clamp_scroll_speed(self._config.get("scroll_speed", SCROLL_SPEED_DEFAULT)),
        }

    def _save_settings(self):
        if not self._persist_settings:
            return
        self._config = self._settings_from_ui()
        save_config(self._config)

    def _apply_preferences(self):
        self._apply_key_bindings(self._config.get("key_bindings", DEFAULT_KEY_BINDINGS))
        speed = clamp_scroll_speed(self._config.get("scroll_speed", SCROLL_SPEED_DEFAULT))
        vbar = self.content_scroll.verticalScrollBar()
        hbar = self.content_scroll.horizontalScrollBar()
        vbar.setSingleStep(12 * speed)
        hbar.setSingleStep(12 * speed)
        self.content_scroll.viewport().installEventFilter(self)

    def _apply_key_bindings(self, bindings):
        sequence_map = {
            "Ctrl + + / Ctrl + =": [QKeySequence.ZoomIn, QKeySequence("Ctrl+="), QKeySequence("Ctrl++")],
            "Ctrl + -": [QKeySequence.ZoomOut, QKeySequence("Ctrl+-")],
            "Ctrl + 0": [QKeySequence("Ctrl+0")],
            "None": [],
        }
        for name, action in self._zoom_actions.items():
            action.setShortcuts(sequence_map.get(bindings.get(name, DEFAULT_KEY_BINDINGS[name]), []))

    def _choose_output_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Choose save folder", self.output_path.text().strip() or get_default_output_dir()
        )
        if folder:
            self.output_path.setText(folder)

    def _choose_cookie_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Import Netscape cookies.txt", "", "Cookie files (*.txt *.cookies);;All files (*.*)"
        )
        if not file_path:
            return
        self._confirm_cookie_file(file_path)

    def _confirm_cookie_file(self, file_path):
        """Validate locally and request clear user consent before a cookie file is used."""
        try:
            summary = inspect_netscape_cookie_file(file_path)
        except ValueError as error:
            QMessageBox.warning(self, "Cookie import failed", str(error))
            return False

        domains = ", ".join(summary["domains"][:6])
        if len(summary["domains"]) > 6:
            domains += f" and {len(summary['domains']) - 6} more"
        answer = QMessageBox.question(
            self,
            "Use imported cookies?",
            "This file contains session cookies that may grant account access.\n\n"
            f"Detected: {summary['cookie_count']} cookies for {len(summary['domains'])} domain(s)\n"
            f"Domains: {domains}\n\n"
            "Use this file only for downloads you are authorized to access?\n"
            "Cookie values will not be displayed, copied, or written to logs.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return False
        self.cookie_file_input.setText(file_path)
        self._set_combo_value(self.cookie_browser_combo, "Custom cookies.txt file...")
        self._cookie_file_approved = True
        self._cookie_summary = summary
        self.log_box.appendPlainText(
            f"[INFO] Authorized cookies.txt import ready for {len(summary['domains'])} domain(s); cookie values are hidden."
        )
        return True

    def _ensure_cookie_file_consent(self):
        """Require a confirmation in each app session before a saved path is used."""
        file_path = self.cookie_file_input.text().strip()
        if not file_path or self._cookie_file_approved:
            return True
        return self._confirm_cookie_file(file_path)

    def _invalidate_cookie_consent(self):
        self._cookie_file_approved = False
        self._cookie_summary = None

    def _open_output_folder(self):
        folder = self.output_path.text().strip() or get_default_output_dir()
        os.makedirs(folder, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(folder))

    def _edit_focused(self, action):
        widget = QApplication.focusWidget()
        if not widget:
            return
        if hasattr(widget, action):
            getattr(widget, action)()
        elif action == "select_all" and hasattr(widget, "selectAll"):
            widget.selectAll()

    def _new_link_list(self):
        self.url_text.clear()
        self.url_text.setFocus()
        self.log_box.appendPlainText("[INFO] New link list ready.")

    def _change_zoom(self, delta):
        self._apply_zoom(self.zoom_percent + delta)

    def _apply_zoom(self, percent):
        self.zoom_percent = clamp_zoom_percent(percent)
        scaled_size = max(7, int(10 * self.zoom_percent / 100.0))
        app = QApplication.instance()
        if app:
            apply_dark_theme(app, base_font_size=scaled_size)
            font = app.font()
            font.setPointSize(scaled_size)
            app.setFont(font)
            for widget in app.allWidgets():
                widget.setFont(font)
                widget.update()
        self.log_box.appendPlainText(f"[INFO] UI Zoom set to {self.zoom_percent}%")

    def eventFilter(self, watched, event):
        """Provide Ctrl + mouse-wheel zoom without interfering with normal scrolling."""
        if (
            event.type() == QEvent.Type.Wheel
            and event.modifiers() & Qt.KeyboardModifier.ControlModifier
        ):
            delta = event.angleDelta().y()
            if delta:
                self._change_zoom(ZOOM_STEP_PERCENT if delta > 0 else -ZOOM_STEP_PERCENT)
                event.accept()
                return True
        return super().eventFilter(watched, event)

    def _schedule_preview(self):
        self._preview_timer.stop()
        self._preview_token += 1
        if not self._first_url():
            self._clear_preview()
            return
        self._set_preview_loading()
        self._preview_timer.start()

    def _first_url(self):
        return next((line.strip() for line in self.url_text.toPlainText().splitlines() if line.strip()), "")

    def _start_preview(self):
        url = self._first_url()
        if not url:
            return
        token = self._preview_token
        self.preview_status.setText("Fetching preview…")
        worker = PreviewWorker(
            token, url,
            self.cookie_browser_combo.currentText(),
            self.cookie_file_input.text().strip() if self._cookie_file_approved else "",
            self.proxy_input.text().strip(),
            self
        )
        worker.preview_ready.connect(self._apply_preview)
        worker.preview_failed.connect(self._apply_preview_error)
        worker.finished.connect(lambda w=worker: self._preview_workers.discard(w))
        worker.finished.connect(worker.deleteLater)
        self._preview_workers.add(worker)
        worker.start()

    def _clear_preview(self):
        self._current_preview_data = None
        self.preview_title.setText("Paste a link to preview it")
        self.preview_source.setText("Source: waiting for a link")
        self.preview_details.setText("Title, duration, uploader, and platform will appear here.")
        self.preview_status.setText("Waiting for a link")
        self.download_thumbnail_btn.setEnabled(False)
        self.preview_image.setPixmap(QPixmap())
        self.preview_image.setText("No preview")

    def _set_preview_loading(self):
        self.preview_title.setText("Loading preview…")
        self.preview_source.setText("Source: loading preview…")
        self.preview_details.setText("Fetching public title, source, and thumbnail…")
        self.preview_status.setText("Waiting for typing to finish…")
        self.download_thumbnail_btn.setEnabled(False)
        self.preview_image.setPixmap(QPixmap())
        self.preview_image.setText("Loading thumbnail…")

    def _apply_preview_error(self, token, error):
        if token != self._preview_token:
            return
        self._current_preview_data = None
        self.preview_title.setText("Preview unavailable")
        self.preview_source.setText("Source: unavailable")
        self.preview_details.setText("No public metadata could be loaded for this link.")
        self.preview_status.setText(f"Preview unavailable: {explain_download_error(error)}")
        self.download_thumbnail_btn.setEnabled(False)
        self.preview_image.setPixmap(QPixmap())
        self.preview_image.setText("Thumbnail unavailable")

    def _apply_preview(self, token, preview):
        if token != self._preview_token:
            return
        self._current_preview_data = preview
        self.preview_title.setText(preview["title"])
        self.preview_source.setText(f"Source: {preview.get('source') or 'Unknown source'}")
        self.preview_details.setText(preview["details"])
        self.preview_status.setText(preview.get("status", "Preview ready"))
        self.download_thumbnail_btn.setEnabled(bool(preview.get("thumbnail_url")))

        thumbnail_data = preview.get("thumbnail_data")
        pixmap = QPixmap()
        if thumbnail_data and pixmap.loadFromData(thumbnail_data):
            self.preview_image.setPixmap(pixmap.scaled(
                self.preview_image.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            ))
            self.preview_image.setText("")
        else:
            self.preview_image.setPixmap(QPixmap())
            self.preview_image.setText("Thumbnail unavailable")

    def _download_thumbnail_file(self):
        if not self._current_preview_data or not self._current_preview_data.get("thumbnail_url"):
            return

        out_dir = self.output_path.text().strip() or get_default_output_dir()
        os.makedirs(out_dir, exist_ok=True)
        url = self._current_preview_data["thumbnail_url"]
        title = self._current_preview_data.get("title", "thumbnail")

        self.log_box.appendPlainText(f"[INFO] Downloading thumbnail HQ for '{title}'...")
        worker = ThumbnailDownloadWorker(url, title, out_dir, self)
        worker.thumbnail_saved.connect(lambda path: self.log_box.appendPlainText(f"[SUCCESS] Thumbnail saved: {path}"))
        worker.thumbnail_failed.connect(lambda err: self.log_box.appendPlainText(f"[ERROR] Failed to save thumbnail: {err}"))
        worker.finished.connect(lambda w=worker: self._thumbnail_workers.discard(w))
        worker.finished.connect(worker.deleteLater)
        self._thumbnail_workers.add(worker)
        worker.start()

    def _handle_age_verification(self, urls: list[str]) -> list[str]:
        """Check for adult/18+ URLs and prompt for age verification and authentication options."""
        adult_urls = [u for u in urls if is_adult_or_age_restricted_url(u)]
        if not adult_urls:
            return urls

        # Step 1: Age Gate Verification Dialog (18+)
        first_adult_url = adult_urls[0]
        dlg = AgeVerificationDialog(first_adult_url, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            self.log_box.appendPlainText("[NOTICE] Download cancelled for adult link(s): Age verification (18+) not confirmed.")
            safe_urls = [u for u in urls if not is_adult_or_age_restricted_url(u)]
            return safe_urls

        self.log_box.appendPlainText("[INFO] Age verification (18+) confirmed by user.")

        # Step 2: Sign-in / Cookie / Session Setup Dialog
        try:
            domain = urllib.parse.urlparse(first_adult_url).netloc or "this site"
        except Exception:
            domain = "this site"

        auth_dlg = AgeGateAuthDialog(domain, self)
        if auth_dlg.exec() == QDialog.DialogCode.Accepted:
            action = getattr(auth_dlg, "user_action", "guest")
            if action == "cookies":
                self._set_combo_value(self.cookie_browser_combo, "chrome")
                self.log_box.appendPlainText(f"[INFO] Configured browser cookie import for {domain}.")
            elif action == "account_sessions":
                self.main_tab_widget.setCurrentIndex(1)
                self.log_box.appendPlainText(f"[INFO] Redirecting to Account & Sessions tab for {domain}.")
            elif action == "mailpit":
                self.main_tab_widget.setCurrentIndex(2)
                self.log_box.appendPlainText("[INFO] Redirecting to Local Test Inbox (Mailpit) tab.")
            elif action == "guest":
                self.log_box.appendPlainText("[INFO] Proceeding as guest using 18+ age limit bypass flag.")

        return urls

    def _start_download(self):
        try:
            raw_text = self.url_text.toPlainText()
            urls = []
            for token in re.split(r"[\r\n,\s]+", raw_text):
                cleaned = token.strip(" \"'\t\r\n,;")
                if cleaned and (cleaned.startswith("http://") or cleaned.startswith("https://") or "www." in cleaned or "youtu" in cleaned):
                    urls.append(cleaned)
                elif cleaned and len(cleaned) > 5 and "." in cleaned:
                    urls.append("https://" + cleaned if not cleaned.startswith("http") else cleaned)

            if not urls:
                self.log_box.appendPlainText("[WARNING] Download clicked but no valid video links found in input box.")
                QMessageBox.warning(self, "No links provided", "Please paste at least one valid video link before clicking Download.")
                return

            urls = self._handle_age_verification(urls)
            if not urls:
                return

            if not self._ensure_cookie_file_consent():
                return

            settings = {
                "format": "video" if self.video_radio.isChecked() else "audio",
                "quality": self.quality_combo.currentText(),
                "output_format": self.output_format_combo.currentText(),
                "output_dir": self.output_path.text().strip() or get_default_output_dir(),
                "ffmpeg_path": self.ffmpeg_path_input.text().strip() or get_default_ffmpeg_path(),
                "single_only": self.single_only_check.isChecked(),
                "filename_pattern": self.pattern_input.text().strip(),
                "cookies_browser": self.cookie_browser_combo.currentText(),
                "cookies_file": self.cookie_file_input.text().strip(),
                "proxy": self.proxy_input.text().strip(),
                "embed_subtitles": self.download_subs_check.isChecked(),
                "auto_subtitles": self.auto_subs_check.isChecked(),
                "subtitle_langs": self.sub_lang_input.text().strip(),
                "embed_metadata": self.embed_metadata_check.isChecked(),
                "embed_thumbnail": self.embed_thumb_check.isChecked(),
                "live_start_from_beginning": self.live_start_check.isChecked(),
                "exact_format_id": self.format_id_input.text().strip(),
                "video_codec": self.video_codec_combo.currentText(),
                "video_bitrate": self.video_bitrate_input.text().strip(),
                "conversion_resolution": self.resolution_combo.currentText(),
                "frame_rate": self.frame_rate_combo.currentText(),
                "sample_rate": self.sample_rate_combo.currentText(),
                "channels": self.channel_combo.currentText(),
                "compression_level": self.compression_combo.currentText(),
                "clean_sidecars": self.clean_sidecars_check.isChecked(),
            }
            self._save_settings()

            for url in urls:
                add_history_entry(url, title=url, format_type=settings.get("format", "video"), status="Queued")

            self.download_button.setEnabled(False)
            self.cancel_button.setEnabled(True)
            self.log_box.appendPlainText(f"\n=== Starting Download Operation for {len(urls)} item(s) ===")

            self._download_worker = QtDownloadWorker(urls, settings, self)
            self._download_worker.log_emitted.connect(self.log_box.appendPlainText)
            self._download_worker.progress_updated.connect(self._on_progress_update)
            self._download_worker.status_updated.connect(self._on_status_update)
            self._download_worker.item_finished.connect(self._on_item_finished)
            self._download_worker.queue_completed.connect(self._on_download_complete)
            self._download_worker.start()
        except Exception as err:
            self.log_box.appendPlainText(f"[ERROR] Could not start download: {err}")
            QMessageBox.critical(self, "Download Error", f"Failed to start download operation:\n{err}")

    def _cancel_download(self):
        if self._download_worker:
            self._download_worker.cancel()
            self.cancel_button.setEnabled(False)
            self.log_box.appendPlainText("[INFO] Cancellation requested...")

    def _on_progress_update(self, data):
        self.transfer_status.set_transfer_state(
            status=data.get("status", "Downloading..."),
            download_rate=data.get("download_rate", "0 B/s"),
            upload_rate=data.get("upload_rate", "0 B/s"),
            transferred=data.get("transferred", "0 B"),
            eta=data.get("eta", "—"),
            progress=data.get("progress", 0)
        )

    def _on_status_update(self, status):
        self.transfer_status.status_label.setText(f"Status: {status}")

    def _play_notification_sound(self):
        """Play Windows default notification sound chime when a download finishes."""
        if sys.platform == "win32":
            try:
                import winsound
                winsound.MessageBeep(winsound.MB_ICONASTERISK)
            except Exception:
                pass

    def _on_download_complete(self, success_count, failure_count):
        self.download_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.log_box.appendPlainText(f"\n[FINISHED] Queue finished: {success_count} succeeded, {failure_count} failed.")
        self._play_notification_sound()

    def _on_item_finished(self, url, succeeded, format_type):
        update_history_entry(
            url,
            "Completed" if succeeded else "Failed or cancelled",
            format_type=format_type,
        )
        if succeeded:
            self._play_notification_sound()

    def closeEvent(self, event):
        """Stop timers, purge temporary cookies, and give active workers a safe shutdown window."""
        self._preview_timer.stop()
        if self._download_worker and self._download_worker.isRunning():
            self._download_worker.cancel()
            self._download_worker.wait(1500)
        for worker in tuple(self._preview_workers | self._thumbnail_workers | self._format_workers):
            if worker.isRunning():
                worker.wait(750)
        self._save_settings()
        try:
            from ...services.cookies import purge_all_temporary_cookie_files
            from ...auth.manager import AuthManager
            purge_all_temporary_cookie_files()
            AuthManager.purge_expired_sessions()
        except Exception:
            pass
        super().closeEvent(event)

    # Dialog Connectors
    def _show_complex_options_help(self):
        QMessageBox.information(
            self,
            "Complex Options Reference Guide",
            "<h3>Complex & Advanced Options Reference Guide</h3>"
            "<hr>"
            "<p><b>FFmpeg Location:</b> Custom path to <code>ffmpeg.exe</code> for merging audio/video streams, converting containers, and re-encoding.</p>"
            "<p><b>Browser Cookies:</b> Load authenticated session cookies directly from Chrome, Firefox, Edge, Brave, etc., to bypass age limits or login screens.</p>"
            "<p><b>Proxy:</b> Route HTTP/HTTPS/SOCKS traffic through a proxy server (format: <code>http://user:pass@host:port</code>).</p>"
            "<p><b>Subtitles:</b> Select language codes (e.g. <code>en.*, es</code>) to download and embed closed captions or auto-generated tracks.</p>"
            "<p><b>Exact Format IDs:</b> Specify raw yt-dlp format codes (e.g. <code>137+140</code>) after running <i>List Formats</i>.</p>"
            "<p><b>Video Codec & Bitrate:</b> Re-encode video using H.264, H.265, VP9, or AV1 with custom bitrate targets (e.g. <code>8000k</code>).</p>"
            "<p><b>Resolution & FPS:</b> Override output video dimensions (e.g. <code>1920x1080</code>, <code>1080p</code>) and frame rates (e.g. <code>60 FPS</code>).</p>"
            "<p><b>Sample Rate & Channels:</b> Override audio frequency (e.g. <code>48000 Hz</code>) and channel layout (Mono/Stereo).</p>"
        )

    def _show_key_bindings_dialog(self):
        dlg = KeyBindingsDialog(self._config.get("key_bindings"), self._config.get("scroll_speed", SCROLL_SPEED_DEFAULT), self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            bindings, speed = dlg.get_settings()
            self._config["key_bindings"] = bindings
            self._config["scroll_speed"] = speed
            if self._persist_settings:
                save_config(self._config)
            self._apply_preferences()

    def _show_history_dialog(self):
        dlg = LinkHistoryDialog(self)
        dlg.exec()

    def _show_library_dialog(self):
        dlg = LibraryDialog(self.output_path.text().strip() or get_default_output_dir(), self)
        dlg.exec()

    def _show_font_dialog(self):
        dlg = FontPreferencesDialog(parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            family, size = dlg.get_font_choice()
            font = QFont(family, size)
            QApplication.setFont(font)
            self.setFont(font)

    def _show_supported_platforms_dialog(self):
        dlg = SupportedPlatformsDialog(self)
        dlg.exec()

    def _show_updates_dialog(self):
        dlg = UpdateCheckDialog(self)
        dlg.exec()

    def _show_help_dialog(self):
        dlg = HelpCenterDialog(self)
        dlg.exec()

    def _show_about_dialog(self):
        QMessageBox.about(
            self, f"About {APP_NAME}",
            f"{APP_NAME}\n{DEVELOPMENT_BUILD_LABEL}\nVersion: {PACKAGE_VERSION}\n\n"
            "High-performance media downloader and local converter.\nBuilt with PySide6 & yt-dlp."
        )
