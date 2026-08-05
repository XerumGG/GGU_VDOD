"""PySide6 main window providing 100% complete desktop downloader capabilities."""

import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import urllib.request

from PIL import Image
from PySide6.QtCore import QEvent, QObject, QPoint, QRect, QSize, Qt, QThread, QTimer, QUrl, Signal
from PySide6.QtGui import QAction, QColor, QDesktopServices, QFont, QIcon, QKeySequence, QPixmap
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QCheckBox, QComboBox, QDialog, QFileDialog,
    QFormLayout, QFrame, QGridLayout, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QMainWindow, QMessageBox, QPlainTextEdit, QProgressBar,
    QPushButton, QRadioButton, QScrollArea, QSlider, QSpinBox, QSplitter,
    QStyle, QTableWidget, QTableWidgetItem, QTabWidget, QToolButton,
    QVBoxLayout, QWidget,
)

from ...config.paths import get_app_dir, get_default_output_dir
from ...config.store import load_config, save_config
from ...conversion.options import (
    audio_conversion_args, audio_fallback_args, clean_video_sidecars,
    output_template, valid_bitrate, video_conversion_args, video_fallback_args,
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
from ...services.network import explain_download_error, is_internet_up
from .dialogs import (
    FontPreferencesDialog, HelpCenterDialog, KeyBindingsDialog, LibraryDialog,
    LinkHistoryDialog, SupportedPlatformsDialog, UpdateCheckDialog,
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
            raw_bytes, ext = download_thumbnail_bytes(self.thumbnail_url)
            safe_title = re.sub(r'[\\/*?:"<>|]', '_', self.title or "thumbnail")
            save_path = os.path.join(self.output_dir, f"{safe_title}_HQ{ext}")

            with open(save_path, "wb") as f:
                f.write(raw_bytes)

            self.thumbnail_saved.emit(save_path)
        except Exception as err:
            self.thumbnail_failed.emit(str(err))


class QtDownloadWorker(QThread):
    """Download media queue on a background QThread with real-time Qt signals."""
    log_emitted = Signal(str)
    progress_updated = Signal(dict)
    status_updated = Signal(str)
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

            success = self._process_single_url(url)
            if success:
                success_count += 1
            else:
                failure_count += 1

        self.status_updated.emit("Ready.")
        self.queue_completed.emit(success_count, failure_count)

    def _process_single_url(self, url):
        output_dir = self.settings.get("output_dir") or get_default_output_dir()
        os.makedirs(output_dir, exist_ok=True)
        is_audio = self.settings.get("format") == "audio"
        target_ext = (AUDIO_FORMAT_EXTENSIONS if is_audio else VIDEO_FORMAT_EXTENSIONS).get(
            self.settings.get("output_format"), "mp3" if is_audio else "mp4"
        )

        def progress_hook(d):
            if self.cancelled:
                raise Exception("Download cancelled by user")
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
                    "eta": f"{eta}s" if eta else "—",
                })
            elif status == "finished":
                self.log_emitted.emit("[INFO] Primary download complete. Finalizing media file...")

        ydl_opts = {
            "outtmpl": output_template(self.settings, output_dir, target_ext),
            "progress_hooks": [progress_hook],
            "noplaylist": self.settings.get("single_only", True),
            "quiet": True,
            "no_warnings": True,
        }

        ffmpeg_path = self.settings.get("ffmpeg_path") or os.path.join(get_app_dir(), "ffmpeg", "ffmpeg.exe")
        if ffmpeg_path and os.path.exists(ffmpeg_path):
            ydl_opts["ffmpeg_location"] = ffmpeg_path

        # Cookies configuration
        browser = self.settings.get("cookies_browser")
        cookies_file = self.settings.get("cookies_file")
        if cookies_file and os.path.exists(cookies_file):
            ydl_opts["cookiefile"] = cookies_file
        elif browser and browser not in ("None", "custom"):
            ydl_opts["cookiesfrombrowser"] = (browser.lower(),)

        # Proxy configuration
        proxy = self.settings.get("proxy")
        if proxy:
            ydl_opts["proxy"] = proxy

        # Subtitles configuration
        if self.settings.get("embed_subtitles"):
            ydl_opts["writesubtitles"] = True
            ydl_opts["writeautomaticsub"] = True
            sub_langs = self.settings.get("subtitle_langs", "en").split(",")
            ydl_opts["subtitleslangs"] = [s.strip() for s in sub_langs if s.strip()]
            ydl_opts["postprocessors"] = ydl_opts.get("postprocessors", []) + [{
                "key": "FFmpegEmbedSubtitle",
            }]

        if is_audio:
            ydl_opts["format"] = "bestaudio/best"
            ydl_opts["postprocessors"] = ydl_opts.get("postprocessors", []) + [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": target_ext,
                "preferredquality": self.settings.get("quality", "320").split()[0],
            }]
        else:
            quality = self.settings.get("quality", "Best available")
            height = HEIGHT_MAP.get(quality)
            if height:
                ydl_opts["format"] = f"bestvideo[height<={height}]+bestaudio/best[height<={height}]/best"
            else:
                ydl_opts["format"] = "bestvideo+bestaudio/best"

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

            if self.settings.get("clean_sidecars", True):
                clean_video_sidecars(output_dir)

            self.log_emitted.emit(f"[SUCCESS] Successfully processed: {url}")
            return True
        except Exception as err:
            if "cancelled" in str(err).lower():
                self.log_emitted.emit("[INFO] Item cancelled.")
            else:
                self.log_emitted.emit(f"[ERROR] Failed {url}: {explain_download_error(err)}")
            return False


class QtMainWindow(QMainWindow):
    """Production PySide6 MainWindow for GGU_VDOD bringing 100% legacy parity."""

    def __init__(self, settings=None, persist_settings=True):
        super().__init__()
        self._config = dict(load_config() if settings is None else settings)
        self._persist_settings = persist_settings
        self._preview_token = 0
        self._preview_workers = set()
        self._download_worker = None
        self._current_preview_data = None

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
        zoom_in_act.setShortcut(QKeySequence("Ctrl++"))
        zoom_in_act.triggered.connect(lambda: self._change_zoom(ZOOM_STEP_PERCENT))
        view_menu.addAction(zoom_in_act)

        zoom_out_act = QAction("Zoom out", self)
        zoom_out_act.setShortcut(QKeySequence("Ctrl+-"))
        zoom_out_act.triggered.connect(lambda: self._change_zoom(-ZOOM_STEP_PERCENT))
        view_menu.addAction(zoom_out_act)

        zoom_reset_act = QAction("Reset zoom", self)
        zoom_reset_act.setShortcut(QKeySequence("Ctrl+0"))
        zoom_reset_act.triggered.connect(lambda: self._apply_zoom(ZOOM_DEFAULT_PERCENT))
        view_menu.addAction(zoom_reset_act)

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
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

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
        self.download_thumbnail_btn.clicked.connect(self._download_thumbnail_file)

        self.preview_status = QLabel("Waiting for a link")
        self.preview_status.setObjectName("muted")

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
        self.format_group = QButtonGroup(self)
        self.format_group.addButton(self.video_radio)
        self.format_group.addButton(self.audio_radio)

        self.single_only_check = QCheckBox("Only download this video (ignore playlist)")
        self.single_only_check.setChecked(True)

        self.quality_combo = QComboBox()
        self.quality_combo.addItems(VIDEO_QUALITIES)
        self.output_format_combo = QComboBox()
        self.output_format_combo.addItems(VIDEO_OUTPUT_FORMATS)

        fmt_grid.addWidget(self.video_radio, 0, 0)
        fmt_grid.addWidget(self.audio_radio, 0, 1)
        fmt_grid.addWidget(QLabel("Quality:"), 1, 0)
        fmt_grid.addWidget(self.quality_combo, 1, 1)
        fmt_grid.addWidget(QLabel("Save as:"), 2, 0)
        fmt_grid.addWidget(self.output_format_combo, 2, 1)
        fmt_grid.addWidget(self.single_only_check, 3, 0, 1, 3)
        fmt_grid.setColumnStretch(2, 1)
        layout.addWidget(fmt_panel)

        # Save Folder Picker
        save_row = QHBoxLayout()
        self.output_path = QLineEdit()
        self.output_path.setPlaceholderText("Save folder")
        self.browse_button = QPushButton("Browse…")
        save_row.addWidget(QLabel("Save to:"))
        save_row.addWidget(self.output_path, 1)
        save_row.addWidget(self.browse_button)
        layout.addLayout(save_row)

        # Advanced Panel Toggle & Granular Controls
        advanced_toggle = QToolButton()
        advanced_toggle.setText("Advanced Options  [+]")
        advanced_toggle.setCheckable(True)
        advanced_toggle.setStyleSheet("border: none; color: #a7a7a7; font-weight: 600;")
        layout.addWidget(advanced_toggle)

        self.advanced_panel = QFrame()
        self.advanced_panel.setObjectName("panel")
        adv_layout = QFormLayout(self.advanced_panel)
        adv_layout.setContentsMargins(16, 14, 16, 14)
        adv_layout.setSpacing(10)

        self.video_codec_combo = QComboBox()
        self.video_codec_combo.addItems(VIDEO_CODEC_OPTIONS)

        self.video_bitrate_input = QLineEdit()
        self.video_bitrate_input.setPlaceholderText("Auto (e.g. 8000k)")

        self.resolution_combo = QComboBox()
        self.resolution_combo.addItems(VIDEO_RESOLUTION_OPTIONS)

        self.frame_rate_combo = QComboBox()
        self.frame_rate_combo.addItems(FRAME_RATE_OPTIONS)

        self.sample_rate_combo = QComboBox()
        self.sample_rate_combo.addItems(SAMPLE_RATE_OPTIONS)

        self.channel_combo = QComboBox()
        self.channel_combo.addItems(CHANNEL_OPTIONS)

        self.compression_combo = QComboBox()
        self.compression_combo.addItems(COMPRESSION_OPTIONS)

        self.pattern_input = QLineEdit()
        self.pattern_input.setPlaceholderText("%(title)s [%(height)sp]")

        self.cookie_browser_combo = QComboBox()
        self.cookie_browser_combo.addItems(["None", "chrome", "edge", "firefox", "brave", "vivaldi", "opera", "safari", "Custom cookies.txt file..."])

        cookie_row = QHBoxLayout()
        self.cookie_file_input = QLineEdit()
        self.cookie_file_input.setPlaceholderText("Path to cookies.txt")
        self.cookie_browse_btn = QPushButton("Browse…")
        self.cookie_browse_btn.clicked.connect(self._choose_cookie_file)
        cookie_row.addWidget(self.cookie_file_input, 1)
        cookie_row.addWidget(self.cookie_browse_btn)

        self.proxy_input = QLineEdit()
        self.proxy_input.setPlaceholderText("http://user:pass@host:port")

        self.embed_subs_check = QCheckBox("Embed subtitles")
        self.sub_lang_input = QLineEdit("en,es,fr")

        self.clean_sidecars_check = QCheckBox("Clean temporary sidecar files after conversion")
        self.clean_sidecars_check.setChecked(True)

        adv_layout.addRow(QLabel("Video Codec:"), self.video_codec_combo)
        adv_layout.addRow(QLabel("Video Bitrate:"), self.video_bitrate_input)
        adv_layout.addRow(QLabel("Resolution Override:"), self.resolution_combo)
        adv_layout.addRow(QLabel("Frame Rate Override:"), self.frame_rate_combo)
        adv_layout.addRow(QLabel("Audio Sample Rate:"), self.sample_rate_combo)
        adv_layout.addRow(QLabel("Audio Channels:"), self.channel_combo)
        adv_layout.addRow(QLabel("Audio Compression:"), self.compression_combo)
        adv_layout.addRow(QLabel("Filename Pattern:"), self.pattern_input)
        adv_layout.addRow(QLabel("Cookie Browser:"), self.cookie_browser_combo)
        adv_layout.addRow(QLabel("Cookies File:"), cookie_row)
        adv_layout.addRow(QLabel("Proxy Server:"), self.proxy_input)
        adv_layout.addRow(self.embed_subs_check, self.sub_lang_input)
        adv_layout.addRow(self.clean_sidecars_check)

        self.advanced_panel.setVisible(False)
        advanced_toggle.toggled.connect(lambda open_: self.advanced_panel.setVisible(open_))
        advanced_toggle.toggled.connect(lambda open_: advanced_toggle.setText("Advanced Options  [-]" if open_ else "Advanced Options  [+]"))
        layout.addWidget(self.advanced_panel)

        # Download Actions Row
        action_row = QHBoxLayout()
        self.download_button = QPushButton("Download")
        self.download_button.setObjectName("primary")
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setEnabled(False)
        self.open_folder_button = QPushButton("Open Save Folder")

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

        scroll.setWidget(scroll_content)
        main_vbox.addWidget(scroll, 1)

        # Status Bar
        self.transfer_status = TransferStatusBar()
        main_vbox.addWidget(self.transfer_status)

        self.setCentralWidget(root)

    def _connect_ui(self):
        self.url_text.textChanged.connect(self._schedule_preview)
        self.video_radio.toggled.connect(self._sync_format_controls)
        self.browse_button.clicked.connect(self._choose_output_folder)
        self.open_folder_button.clicked.connect(self._open_output_folder)
        self.download_button.clicked.connect(self._start_download)
        self.cancel_button.clicked.connect(self._cancel_download)

    def _restore_settings(self):
        video_selected = self._config.get("format", "video") == "video"
        self.video_radio.setChecked(video_selected)
        self._set_combo_value(self.quality_combo, self._config.get("quality"))
        self._set_combo_value(self.output_format_combo, self._config.get("output_format"))
        self.output_path.setText(self._config.get("output_dir") or get_default_output_dir())

    @staticmethod
    def _set_combo_value(combo, value):
        index = combo.findText(value or "")
        if index >= 0:
            combo.setCurrentIndex(index)

    def _sync_format_controls(self, video_selected):
        self.quality_combo.clear()
        self.output_format_combo.clear()
        if video_selected:
            self.quality_combo.addItems(VIDEO_QUALITIES)
            self.output_format_combo.addItems(VIDEO_OUTPUT_FORMATS)
        else:
            self.quality_combo.addItems(AUDIO_QUALITIES)
            self.output_format_combo.addItems(AUDIO_OUTPUT_FORMATS)

    def _choose_output_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Choose save folder", self.output_path.text().strip() or get_default_output_dir()
        )
        if folder:
            self.output_path.setText(folder)

    def _choose_cookie_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select cookies.txt file", "", "Text files (*.txt);;All files (*.*)")
        if file_path:
            self.cookie_file_input.setText(file_path)

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
        font = self.font()
        font.setPointSize(max(7, int(10 * self.zoom_percent / 100.0)))
        self.setFont(font)

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
            self.cookie_file_input.text().strip(),
            self.proxy_input.text().strip(),
            self
        )
        worker.preview_ready.connect(self._apply_preview)
        worker.preview_failed.connect(self._apply_preview_error)
        worker.finished.connect(lambda: self._preview_workers.discard(worker))
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
        worker.start()

    def _start_download(self):
        urls = [line.strip() for line in self.url_text.toPlainText().splitlines() if line.strip()]
        if not urls:
            QMessageBox.warning(self, "No links provided", "Please paste at least one video link before clicking Download.")
            return

        settings = {
            "format": "video" if self.video_radio.isChecked() else "audio",
            "quality": self.quality_combo.currentText(),
            "output_format": self.output_format_combo.currentText(),
            "output_dir": self.output_path.text().strip() or get_default_output_dir(),
            "single_only": self.single_only_check.isChecked(),
            "filename_pattern": self.pattern_input.text().strip(),
            "cookies_browser": self.cookie_browser_combo.currentText(),
            "cookies_file": self.cookie_file_input.text().strip(),
            "proxy": self.proxy_input.text().strip(),
            "embed_subtitles": self.embed_subs_check.isChecked(),
            "subtitle_langs": self.sub_lang_input.text().strip(),
            "clean_sidecars": self.clean_sidecars_check.isChecked(),
        }

        from ...config.store import add_history_entry
        for url in urls:
            add_history_entry(url, title=url, format_type=settings.get("format", "video"))

        self.download_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.log_box.appendPlainText("\n=== Starting Download Operation ===")

        self._download_worker = QtDownloadWorker(urls, settings, self)
        self._download_worker.log_emitted.connect(self.log_box.appendPlainText)
        self._download_worker.progress_updated.connect(self._on_progress_update)
        self._download_worker.status_updated.connect(self._on_status_update)
        self._download_worker.queue_completed.connect(self._on_download_complete)
        self._download_worker.start()

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

    def _on_download_complete(self, success_count, failure_count):
        self.download_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.log_box.appendPlainText(f"\n[FINISHED] Queue finished: {success_count} succeeded, {failure_count} failed.")

    # Dialog Connectors
    def _show_key_bindings_dialog(self):
        dlg = KeyBindingsDialog(self._config.get("key_bindings"), self._config.get("scroll_speed", SCROLL_SPEED_DEFAULT), self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            bindings, speed = dlg.get_settings()
            self._config["key_bindings"] = bindings
            self._config["scroll_speed"] = speed
            if self._persist_settings:
                save_config(self._config)

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
