"""PySide6 dialog windows for preferences, help center, supported platforms, update checker, and shortcuts."""

import os
import subprocess
import sys
import threading
from PySide6.QtCore import Qt, QThread, Signal, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QFont, QKeySequence
from PySide6.QtWidgets import (
    QApplication, QColorDialog, QComboBox, QDialog, QFileDialog, QFormLayout,
    QFrame, QGridLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QMessageBox, QPlainTextEdit, QPushButton, QScrollArea, QSlider, QSpinBox,
    QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget,
)

from ...config.paths import get_default_output_dir
from ...core.constants import (
    APP_NAME, DEFAULT_KEY_BINDINGS, KEY_BINDING_CHOICES, SCROLL_SPEED_DEFAULT,
    SCROLL_SPEED_MAX, SCROLL_SPEED_MIN, UPDATE_COMPONENTS, clamp_scroll_speed,
)
from ...core.version import DEVELOPMENT_BUILD_LABEL

try:
    import yt_dlp
except ImportError:
    yt_dlp = None


class KeyBindingsDialog(QDialog):
    """Preferences dialog for key bindings and scroll speed."""

    def __init__(self, key_bindings=None, scroll_speed=SCROLL_SPEED_DEFAULT, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Preferences - Key Bindings & Scroll Speed")
        self.resize(600, 480)
        self.setMinimumSize(500, 400)

        self.bindings = dict(DEFAULT_KEY_BINDINGS if key_bindings is None else key_bindings)
        self.scroll_speed = clamp_scroll_speed(scroll_speed)
        self.combos = {}

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(14)

        title = QLabel("Key Bindings & Scroll Speed")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)

        form = QFormLayout()
        form.setSpacing(10)

        for action_name, default_val in DEFAULT_KEY_BINDINGS.items():
            combo = QComboBox()
            combo.addItems(KEY_BINDING_CHOICES)
            current = self.bindings.get(action_name, default_val)
            idx = combo.findText(current)
            if idx >= 0:
                combo.setCurrentIndex(idx)
            self.combos[action_name] = combo
            form.addRow(QLabel(f"{action_name}:"), combo)

        layout.addLayout(form)

        # Scroll Speed Slider
        scroll_box = QFrame()
        scroll_box.setObjectName("panel")
        scroll_layout = QHBoxLayout(scroll_box)
        scroll_layout.addWidget(QLabel("Scroll Speed:"))

        self.speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.speed_slider.setRange(SCROLL_SPEED_MIN, SCROLL_SPEED_MAX)
        self.speed_slider.setValue(self.scroll_speed)
        self.speed_label = QLabel(str(self.scroll_speed))

        self.speed_slider.valueChanged.connect(lambda val: self.speed_label.setText(str(val)))

        scroll_layout.addWidget(self.speed_slider, 1)
        scroll_layout.addWidget(self.speed_label)
        layout.addWidget(scroll_box)

        # Action Buttons
        btn_box = QHBoxLayout()
        btn_box.addStretch(1)

        reset_btn = QPushButton("Restore Defaults")
        reset_btn.clicked.connect(self._reset_defaults)
        btn_box.addWidget(reset_btn)

        save_btn = QPushButton("Save")
        save_btn.setObjectName("primary")
        save_btn.clicked.connect(self.accept)
        btn_box.addWidget(save_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_box.addWidget(cancel_btn)

        layout.addLayout(btn_box)

    def _reset_defaults(self):
        for action_name, default_val in DEFAULT_KEY_BINDINGS.items():
            if action_name in self.combos:
                idx = self.combos[action_name].findText(default_val)
                if idx >= 0:
                    self.combos[action_name].setCurrentIndex(idx)
        self.speed_slider.setValue(SCROLL_SPEED_DEFAULT)

    def get_settings(self):
        result_bindings = {name: combo.currentText() for name, combo in self.combos.items()}
        return result_bindings, self.speed_slider.value()


class SupportedPlatformsWorker(QThread):
    """Background worker to extract supported yt-dlp extractors."""
    loaded = Signal(list)

    def run(self):
        extractors = []
        if yt_dlp:
            try:
                for ie in yt_dlp.list_extractors():
                    name = ie.IE_NAME if hasattr(ie, "IE_NAME") else str(ie)
                    desc = ie.description() if hasattr(ie, "description") and callable(ie.description) else ""
                    extractors.append((name, desc or "Supported media extractor"))
            except Exception:
                pass
        extractors.sort(key=lambda x: x[0].lower())
        self.loaded.emit(extractors)


class SupportedPlatformsDialog(QDialog):
    """Searchable dialog listing supported video platforms and extractors."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Supported Platforms & Extractors")
        self.resize(750, 550)
        self.setMinimumSize(600, 400)
        self.all_extractors = []

        self._build_ui()
        self._start_loading()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        header = QHBoxLayout()
        header.addWidget(QLabel("Search Platform / Extractor:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Filter platforms (e.g. youtube, vimeo, twitter, twitch)...")
        self.search_input.textChanged.connect(self._filter_table)
        header.addWidget(self.search_input, 1)
        layout.addLayout(header)

        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Extractor / Platform Name", "Description"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(0, 240)
        self.table.setAlternatingRowColors(True)

        layout.addWidget(self.table, 1)

        btn_row = QHBoxLayout()
        self.count_label = QLabel("Loading extractors...")
        self.count_label.setObjectName("muted")
        btn_row.addWidget(self.count_label)
        btn_row.addStretch(1)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    def _start_loading(self):
        self.worker = SupportedPlatformsWorker(self)
        self.worker.loaded.connect(self._on_extractors_loaded)
        self.worker.start()

    def _on_extractors_loaded(self, extractors):
        self.all_extractors = extractors
        self.count_label.setText(f"Loaded {len(extractors)} supported platform extractors.")
        self._filter_table(self.search_input.text())

    def _filter_table(self, query):
        query = query.strip().lower()
        filtered = [
            (name, desc) for name, desc in self.all_extractors
            if not query or query in name.lower() or query in desc.lower()
        ]

        self.table.setRowCount(len(filtered))
        for row, (name, desc) in enumerate(filtered):
            self.table.setItem(row, 0, QTableWidgetItem(name))
            self.table.setItem(row, 1, QTableWidgetItem(desc))


class UpdateCheckWorker(QThread):
    """Check component versions in background."""
    results_ready = Signal(list)

    def run(self):
        results = []
        for name, module_name, component_type in UPDATE_COMPONENTS:
            version_str = "Unknown"
            if name == "yt-dlp" and yt_dlp:
                version_str = getattr(yt_dlp, "__version__", "Installed")
            else:
                try:
                    mod = __import__(module_name)
                    version_str = getattr(mod, "__version__", "Installed")
                except ImportError:
                    version_str = "Not installed"

            results.append((name, component_type, version_str))
        self.results_ready.emit(results)


class UpdateCheckDialog(QDialog):
    """Dialog showing runtime component versions and update check."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Check for Updates & Dependencies")
        self.resize(600, 400)

        self._build_ui()
        self._check_versions()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(14)

        title = QLabel("Component & Dependency Status")
        title.setStyleSheet("font-size: 17px; font-weight: bold;")
        layout.addWidget(title)

        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Component Name", "Type", "Installed Version"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    def _check_versions(self):
        self.worker = UpdateCheckWorker(self)
        self.worker.results_ready.connect(self._populate_results)
        self.worker.start()

    def _populate_results(self, results):
        self.table.setRowCount(len(results))
        for row, (name, comp_type, ver) in enumerate(results):
            self.table.setItem(row, 0, QTableWidgetItem(name))
            self.table.setItem(row, 1, QTableWidgetItem(comp_type))
            self.table.setItem(row, 2, QTableWidgetItem(ver))


class HelpCenterDialog(QDialog):
    """Help center dialog containing guide and troubleshooting info."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("GGU_VDOD Help Center")
        self.resize(720, 520)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)

        title = QLabel(f"{APP_NAME} User Guide & Help")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)

        help_text = QPlainTextEdit()
        help_text.setReadOnly(True)
        help_text.setPlainText(
            f"=== {APP_NAME} Desktop Guide ===\n\n"
            "1. How to Download Media:\n"
            "   - Copy one or more media links from YouTube, Vimeo, Twitter/X, TikTok, etc.\n"
            "   - Paste the links into the top text box (one URL per line).\n"
            "   - Select 'Video' or 'Audio only' and choose your preferred quality.\n"
            "   - Click the 'Download' button.\n\n"
            "2. Advanced Conversion Options:\n"
            "   - Expand the 'Advanced' options drawer to select custom Video Codecs (H.264, HEVC, VP9, AV1),\n"
            "     custom bitrates, resolution overrides, frame rates, audio sample rates, and channels.\n"
            "   - Configure browser cookies (Chrome, Firefox, Edge, etc.) if downloading age-restricted videos.\n"
            "   - Enter proxy credentials if accessing region-locked content.\n\n"
            "3. Keyboard & Mouse Shortcuts:\n"
            "   - Ctrl + + / Ctrl + - : Zoom interface in/out.\n"
            "   - Ctrl + 0 : Reset zoom.\n"
            "   - Ctrl + Mouse Wheel : Dynamic zoom scaling.\n"
            "   - Ctrl + N : Clear and prepare a new link list.\n\n"
            "4. Subtitles & Metadata:\n"
            "   - Enable 'Embed Subtitles' in Advanced options to mux subtitle tracks directly into video files."
        )
        layout.addWidget(help_text, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)


class LinkHistoryDialog(QDialog):
    """Dialog showing history of past media links."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Link History")
        self.resize(750, 480)
        self._build_ui()
        self._load_data()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        hdr = QHBoxLayout()
        hdr.addWidget(QLabel("Media Download History"))
        hdr.addStretch(1)
        clear_btn = QPushButton("Clear History")
        clear_btn.clicked.connect(self._clear_history)
        hdr.addWidget(clear_btn)
        layout.addLayout(hdr)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Title / URL", "Format", "Status", "Date"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self.table, 1)

        btn_row = QHBoxLayout()
        copy_btn = QPushButton("Copy Selected Link")
        copy_btn.clicked.connect(self._copy_selected)
        btn_row.addWidget(copy_btn)

        add_btn = QPushButton("Add to Queue")
        add_btn.setObjectName("primary")
        add_btn.clicked.connect(self._add_to_queue)
        btn_row.addWidget(add_btn)

        btn_row.addStretch(1)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    def _load_data(self):
        from ...config.store import load_history
        history = load_history()
        self.table.setRowCount(len(history))
        for row, item in enumerate(history):
            self.table.setItem(row, 0, QTableWidgetItem(item.get("title") or item.get("url")))
            self.table.setItem(row, 1, QTableWidgetItem(item.get("format", "video")))
            self.table.setItem(row, 2, QTableWidgetItem(item.get("status", "Completed")))
            self.table.setItem(row, 3, QTableWidgetItem(item.get("timestamp", "")))
            # Store full URL in user data
            self.table.item(row, 0).setData(Qt.ItemDataRole.UserRole, item.get("url"))

    def _copy_selected(self):
        row = self.table.currentRow()
        if row >= 0:
            url = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
            if url:
                QApplication.clipboard().setText(url)
                QMessageBox.information(self, "Copied", "Link copied to clipboard!")

    def _add_to_queue(self):
        row = self.table.currentRow()
        if row >= 0 and self.parent():
            url = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
            if url and hasattr(self.parent(), "url_text"):
                curr = self.parent().url_text.toPlainText().strip()
                new_text = f"{curr}\n{url}" if curr else url
                self.parent().url_text.setPlainText(new_text)
                self.accept()

    def _clear_history(self):
        from ...config.store import clear_history
        clear_history()
        self._load_data()


class LibraryDialog(QDialog):
    """Media library manager separating Videos, Audios, and Thumbnails."""

    def __init__(self, output_dir=None, parent=None):
        super().__init__(parent)
        self.output_dir = output_dir or get_default_output_dir()
        self.setWindowTitle("Downloaded Content Library")
        self.resize(850, 520)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        hdr = QHBoxLayout()
        hdr.addWidget(QLabel(f"Library Output: {self.output_dir}"))
        hdr.addStretch(1)
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._scan_files)
        hdr.addWidget(refresh_btn)
        layout.addLayout(hdr)

        self.tabs = QTabWidget()
        self.video_table = self._create_table()
        self.audio_table = self._create_table()
        self.image_table = self._create_table()

        self.tabs.addTab(self.video_table, "🎬 Videos")
        self.tabs.addTab(self.audio_table, "🎵 Audios")
        self.tabs.addTab(self.image_table, "🖼️ Thumbnails")

        layout.addWidget(self.tabs, 1)

        btn_row = QHBoxLayout()
        play_btn = QPushButton("Open / Play File")
        play_btn.setObjectName("primary")
        play_btn.clicked.connect(self._open_selected_file)
        btn_row.addWidget(play_btn)

        folder_btn = QPushButton("Show in Folder")
        folder_btn.clicked.connect(self._show_in_folder)
        btn_row.addWidget(folder_btn)

        btn_row.addStretch(1)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        self._scan_files()

    def _create_table(self):
        table = QTableWidget()
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels(["File Name", "Size", "Type", "Path"])
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        return table

    def _scan_files(self):
        video_exts = {".mp4", ".mkv", ".mov", ".avi", ".webm", ".flv", ".mpeg", ".ts", ".m4v", ".ogv", ".3gp"}
        audio_exts = {".mp3", ".m4a", ".aac", ".wav", ".flac", ".opus", ".ogg", ".alac"}
        image_exts = {".jpg", ".jpeg", ".png", ".webp"}

        videos, audios, images = [], [], []

        if os.path.exists(self.output_dir):
            for root_path, _, filenames in os.walk(self.output_dir):
                for fn in filenames:
                    ext = os.path.splitext(fn)[1].lower()
                    full_path = os.path.join(root_path, fn)
                    try:
                        sz = os.path.getsize(full_path)
                        from ...core.formatting import format_bytes
                        sz_str = format_bytes(sz)
                    except Exception:
                        sz_str = "Unknown"

                    entry = (fn, sz_str, ext[1:].upper(), full_path)
                    if ext in video_exts:
                        videos.append(entry)
                    elif ext in audio_exts:
                        audios.append(entry)
                    elif ext in image_exts:
                        images.append(entry)

        self._populate_table(self.video_table, videos)
        self._populate_table(self.audio_table, audios)
        self._populate_table(self.image_table, images)

    def _populate_table(self, table, items):
        table.setRowCount(len(items))
        for row, (fn, sz, ext, path) in enumerate(items):
            table.setItem(row, 0, QTableWidgetItem(fn))
            table.setItem(row, 1, QTableWidgetItem(sz))
            table.setItem(row, 2, QTableWidgetItem(ext))
            table.setItem(row, 3, QTableWidgetItem(path))
            table.item(row, 0).setData(Qt.ItemDataRole.UserRole, path)

    def _get_active_table(self):
        return [self.video_table, self.audio_table, self.image_table][self.tabs.currentIndex()]

    def _open_selected_file(self):
        table = self._get_active_table()
        row = table.currentRow()
        if row >= 0:
            path = table.item(row, 0).data(Qt.ItemDataRole.UserRole)
            if path and os.path.exists(path):
                QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def _show_in_folder(self):
        table = self._get_active_table()
        row = table.currentRow()
        if row >= 0:
            path = table.item(row, 0).data(Qt.ItemDataRole.UserRole)
            if path and os.path.exists(path):
                folder = os.path.dirname(path)
                QDesktopServices.openUrl(QUrl.fromLocalFile(folder))


class FontPreferencesDialog(QDialog):
    """Preferences dialog to choose UI font family and size."""

    def __init__(self, current_font=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Preferences - UI Font Panel")
        self.resize(480, 260)
        self.font_family = "Segoe UI"
        self.font_size = 10
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)

        form = QFormLayout()

        self.family_combo = QComboBox()
        self.family_combo.addItems(["Segoe UI", "Roboto", "Inter", "Arial", "Consolas", "Segoe UI Variable Display"])
        form.addRow(QLabel("Font Family:"), self.family_combo)

        self.size_spin = QSpinBox()
        self.size_spin.setRange(8, 18)
        self.size_spin.setValue(10)
        form.addRow(QLabel("Base Size (pt):"), self.size_spin)

        layout.addLayout(form)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        save_btn = QPushButton("Save Font")
        save_btn.setObjectName("primary")
        save_btn.clicked.connect(self.accept)
        btn_row.addWidget(save_btn)

        close_btn = QPushButton("Cancel")
        close_btn.clicked.connect(self.reject)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    def get_font_choice(self):
        return self.family_combo.currentText(), self.size_spin.value()

