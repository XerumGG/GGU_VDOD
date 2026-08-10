"""PySide6 dialog windows for preferences, help center, supported platforms, update checker, and shortcuts."""

import importlib.metadata
import json
import os
import re
import subprocess
import sys
import threading
import urllib.parse
import urllib.request
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

    def closeEvent(self, event):
        if hasattr(self, "worker") and self.worker.isRunning():
            self.worker.wait(1000)
        super().closeEvent(event)

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
    """Check installed package versions against PyPI in the background."""
    results_ready = Signal(list)

    def run(self):
        results = []
        for name, module_name, component_type in UPDATE_COMPONENTS:
            try:
                installed = importlib.metadata.version(name)
            except importlib.metadata.PackageNotFoundError:
                installed = "Not installed"
            latest = "—"
            status = "Not installed" if installed == "Not installed" else "Could not check"
            if installed != "Not installed":
                try:
                    package_name = urllib.parse.quote(name, safe="")
                    request = urllib.request.Request(
                        f"https://pypi.org/pypi/{package_name}/json",
                        headers={"User-Agent": f"{APP_NAME}/{installed}"},
                    )
                    with urllib.request.urlopen(request, timeout=8) as response:
                        latest = str(json.load(response)["info"]["version"])
                    status = "Update available" if self._version_key(installed) < self._version_key(latest) else "Up to date"
                except Exception:
                    pass
            results.append((name, component_type, installed, latest, status))
        self.results_ready.emit(results)

    @staticmethod
    def _version_key(version):
        return tuple(int(part) for part in re.findall(r"\d+", version or "0"))


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
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Component", "Type", "Installed", "Latest", "Status"])
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
        for row, (name, comp_type, installed, latest, status) in enumerate(results):
            self.table.setItem(row, 0, QTableWidgetItem(name))
            self.table.setItem(row, 1, QTableWidgetItem(comp_type))
            self.table.setItem(row, 2, QTableWidgetItem(installed))
            self.table.setItem(row, 3, QTableWidgetItem(latest))
            self.table.setItem(row, 4, QTableWidgetItem(status))

    def closeEvent(self, event):
        if hasattr(self, "worker") and self.worker.isRunning():
            self.worker.wait(1000)
        super().closeEvent(event)


class HelpCenterDialog(QDialog):
    """Modern Help Center & User Guide Dialog."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("GGU_VDOD Help Center & Quick Guide")
        self.resize(780, 580)
        self.setMinimumSize(700, 500)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # Header Title Banner
        hdr_box = QFrame()
        hdr_box.setObjectName("panel")
        hdr_box.setStyleSheet("QFrame#panel { background: #141414; border: 1px solid #333333; border-radius: 8px; }")
        hdr_layout = QVBoxLayout(hdr_box)
        hdr_layout.setContentsMargins(16, 12, 16, 12)

        title = QLabel(f"{APP_NAME} Documentation & User Guide", self)
        title.setStyleSheet("font-size: 17px; font-weight: 700; color: #ffffff;")
        subtitle = QLabel("Reference guide for account sessions, local mailpit testing, media downloads, and conversion options.", self)
        subtitle.setStyleSheet("font-size: 12px; color: #a0a0a0; margin-top: 2px;")
        hdr_layout.addWidget(title)
        hdr_layout.addWidget(subtitle)
        layout.addWidget(hdr_box)

        # Main Help Tab Widget
        from PySide6.QtWidgets import QTabWidget

        self.tabs = QTabWidget(self)
        self.tabs.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #303030; border-radius: 8px; background: #0a0a0a; }
            QTabBar::tab {
                background: #121212; color: #a0a0a0; border: 1px solid #303030;
                padding: 9px 18px; font-size: 12px; font-weight: 600; border-top-left-radius: 6px; border-top-right-radius: 6px;
                margin-right: 4px;
            }
            QTabBar::tab:selected { background: #1c1c1c; color: #ffffff; border-bottom: 2px solid #e5484d; font-weight: 700; }
            QTabBar::tab:hover { color: #ffffff; background: #181818; }
        """)

        # Tab 1: Account Sessions & Local Test Inbox (Extreme Top / First Tab!)
        self.tabs.addTab(self._build_account_mailpit_tab(), "Account Sessions & Local Inbox")
        # Tab 2: How to Download Media
        self.tabs.addTab(self._build_download_tab(), "Downloading Media")
        # Tab 3: Complex Conversion Options
        self.tabs.addTab(self._build_complex_tab(), "Complex Options Guide")
        # Tab 4: Shortcuts
        self.tabs.addTab(self._build_shortcuts_tab(), "Keyboard Shortcuts")

        layout.addWidget(self.tabs, 1)

        # Action bar
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        close_btn = QPushButton("Close Help", self)
        close_btn.setMinimumWidth(110)
        close_btn.setMinimumHeight(34)
        close_btn.clicked.connect(self.close)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    def _build_account_mailpit_tab(self) -> QWidget:
        from PySide6.QtWidgets import QTextBrowser
        browser = QTextBrowser(self)
        browser.setOpenExternalLinks(True)
        browser.setStyleSheet("QTextBrowser { background: #0a0a0a; color: #e2e2e2; border: none; padding: 16px; font-size: 13px; line-height: 1.6; }")
        
        html = """
        <div style="font-family: 'Segoe UI', system-ui, sans-serif; line-height: 1.6;">
            <div style="background: #141414; border: 1px solid #e5484d; border-radius: 8px; padding: 16px; margin-bottom: 18px;">
                <h3 style="margin-top: 0; color: #e5484d; font-size: 16px;">1. Account Sessions & 18+ Age Gate Bypass Guide</h3>
                <p style="color: #a7a7a7; font-size: 12px; margin-top: -6px;"><i>Example Targets: Protected media platforms (e.g. <b>example.com</b> or <b>staging.local</b>)</i></p>
                
                <h4 style="color: #ffffff; margin-bottom: 6px; font-size: 14px;">A. Age-Gated Media Link Detection</h4>
                <ol style="margin-top: 4px; padding-left: 20px;">
                    <li>When pasting an age-restricted or protected link (e.g. <code>https://example.com/watch?v=12345</code> or <code>staging.local</code>), GGU_VDOD automatically detects the domain restriction.</li>
                    <li>An <b>Age Verification Required (18+)</b> modal pops up asking you to confirm you are 18 years of age or older.</li>
                    <li>Click <b>I am 18 or older (Confirm)</b> to open the authentication setup dialog.</li>
                </ol>

                <h4 style="color: #ffffff; margin-bottom: 6px; font-size: 14px;">B. Authentication Options for Age-Restricted Sites</h4>
                <ul style="margin-top: 4px; padding-left: 20px;">
                    <li><b>Option 1 (Auto-Import Browser Cookies):</b> Imports active session cookies from Chrome, Firefox, Edge, Brave, Vivaldi, etc., to bypass age verification gates automatically.</li>
                    <li><b>Option 2 (Account Sessions Tab):</b> Registers stored account credentials (username/password/token) under DPAPI encryption for the domain.</li>
                    <li><b>Option 3 (Local Test Inbox Mailpit):</b> Opens local email capture dashboard on <code>127.0.0.1:8025</code> for staging account signups.</li>
                    <li><b>Option 4 (Continue as Guest):</b> Sets native <code>age_limit: 99</code> bypass flags in yt-dlp to extract public age-restricted streams without login.</li>
                </ul>
            </div>

            <div style="background: #141414; border: 1px solid #303030; border-radius: 8px; padding: 16px; margin-bottom: 18px;">
                <h3 style="margin-top: 0; color: #ffffff; font-size: 16px;">2. Elaborate Local Mailpit Test Inbox Guide</h3>
                <p style="color: #a7a7a7; font-size: 12px; margin-top: -6px;"><i>Complete walkthrough for testing local registration & email verification workflows</i></p>

                <h4 style="color: #ffffff; margin-bottom: 6px; font-size: 14px;">What is Mailpit?</h4>
                <p style="color: #cccccc; margin-top: 4px;">Mailpit is a lightweight, zero-dependency local email capture server running directly inside GGU_VDOD on <code>127.0.0.1:8025</code>. It intercepts all outgoing emails sent to test domains (e.g. <code>localhost</code>, <code>127.0.0.1</code>, <code>*.local</code>, <code>*.test</code>, <code>happyadults.com</code>) without sending real messages over the internet.</p>

                <h4 style="color: #ffffff; margin-bottom: 6px; font-size: 14px;">Step-by-Step Mailpit Workflow</h4>
                <ol style="margin-top: 4px; padding-left: 20px;">
                    <li><b>Open Local Inbox:</b> Switch to the <b>Local Test Inbox (Mailpit)</b> tab at the top of GGU_VDOD or click <i>Open Mailpit Web UI (127.0.0.1:8025)</i> to launch the web dashboard in Chrome, Firefox, or Edge.</li>
                    <li><b>Trigger Signup / Verification Email:</b> On your staging platform (e.g. <code>happyadults.com</code> or local auth server), register a new test user account or trigger a password reset email.</li>
                    <li><b>Instant Email Capture:</b> The email is captured in-memory by GGU_VDOD's Mailpit server on port 8025. It appears instantly in the live inbox table.</li>
                    <li><b>One-Click Session Verification:</b> Click <b>Verify Session</b> next to the captured message row. GGU_VDOD automatically extracts verification links (e.g. <code>https://staging.local/verify?token=...</code>) and confirms your session link!</li>
                    <li><b>Clear Mailbox:</b> Click <b>Clear Test Mailbox</b> at any time to purge captured test messages.</li>
                </ol>

                <h4 style="color: #ffffff; margin-bottom: 6px; font-size: 14px;">Mailpit Technical Details & Port Specs</h4>
                <ul style="margin-top: 4px; padding-left: 20px;">
                    <li><b>Web Dashboard URL:</b> <code>http://127.0.0.1:8025/</code> or <code>http://localhost:8025/</code></li>
                    <li><b>REST API Endpoint:</b> <code>http://127.0.0.1:8025/api/v1/messages</code></li>
                    <li><b>Supported Domains:</b> <code>localhost</code>, <code>127.0.0.1</code>, <code>*.local</code>, <code>*.test</code>, <code>*.staging</code>, <code>*.dev</code>, <code>happyadults.com</code></li>
                    <li><b>Automatic Fallback:</b> If an external Mailpit binary is not running, GGU_VDOD automatically launches its built-in in-memory Mailpit server fallback on port 8025.</li>
                </ul>
            </div>
        </div>
        """
        browser.setHtml(html)
        return browser

    def _build_download_tab(self) -> QWidget:
        from PySide6.QtWidgets import QTextBrowser
        browser = QTextBrowser(self)
        browser.setStyleSheet("QTextBrowser { background: #0a0a0a; color: #e2e2e2; border: none; padding: 16px; font-size: 13px; line-height: 1.6; }")
        html = """
        <div style="font-family: 'Segoe UI', system-ui, sans-serif;">
            <h3 style="color: #ffffff; margin-top: 0; font-size: 16px;">2. How to Download Media</h3>
            <ol style="padding-left: 20px;">
                <li>Paste video or audio links into the main URL text box (one link per line).</li>
                <li>Select media format: <b>Video</b> or <b>Audio only</b>.</li>
                <li>Choose target resolution (2160p 4K, 1080p, 720p, 480p) or audio quality (320k, 256k, FLAC, WAV).</li>
                <li>Select destination folder under <b>Save to:</b>.</li>
                <li>Click <b>Download</b> to begin parallel downloading.</li>
            </ol>
        </div>
        """
        browser.setHtml(html)
        return browser

    def _build_complex_tab(self) -> QWidget:
        from PySide6.QtWidgets import QTextBrowser
        browser = QTextBrowser(self)
        browser.setStyleSheet("QTextBrowser { background: #0a0a0a; color: #e2e2e2; border: none; padding: 16px; font-size: 13px; line-height: 1.6; }")
        html = """
        <div style="font-family: 'Segoe UI', system-ui, sans-serif;">
            <h3 style="color: #ffffff; margin-top: 0; font-size: 16px;">3. Complex Conversion & Advanced Options</h3>
            <ul style="padding-left: 20px;">
                <li><b>Expand [+] Button:</b> Located on the <i>Complex & Advanced Conversion Options</i> section header to reveal granular FFmpeg controls.</li>
                <li><b>FFmpeg Location:</b> Custom path to <code>ffmpeg.exe</code> binary for local re-encoding and audio extraction.</li>
                <li><b>Browser Cookies:</b> Import authenticated cookies directly from Chrome, Firefox, Edge, or Brave.</li>
                <li><b>Proxy Settings:</b> Route network traffic through HTTP, HTTPS, or SOCKS5 proxies.</li>
                <li><b>Video Codec & Bitrate:</b> Select H.264, HEVC (H.265), VP9, AV1, or ProRes with custom bitrates.</li>
                <li><b>Resolution Scaling & FPS:</b> Force aspect-ratio safe resolution overrides and frame rates (e.g. 60 FPS).</li>
                <li><b>Audio Sampling & Channels:</b> Override audio frequency (44100 Hz, 48000 Hz) and channel layouts (Mono, Stereo).</li>
            </ul>
        </div>
        """
        browser.setHtml(html)
        return browser

    def _build_shortcuts_tab(self) -> QWidget:
        from PySide6.QtWidgets import QTextBrowser
        browser = QTextBrowser(self)
        browser.setStyleSheet("QTextBrowser { background: #0a0a0a; color: #e2e2e2; border: none; padding: 16px; font-size: 13px; line-height: 1.6; }")
        html = """
        <div style="font-family: 'Segoe UI', system-ui, sans-serif;">
            <h3 style="color: #ffffff; margin-top: 0; font-size: 16px;">4. Keyboard & Mouse Shortcuts</h3>
            <table style="width: 100%; border-collapse: collapse; margin-top: 10px;">
                <tr style="border-bottom: 1px solid #333; text-align: left;">
                    <th style="padding: 8px; color: #888;">Shortcut</th>
                    <th style="padding: 8px; color: #888;">Action</th>
                </tr>
                <tr style="border-bottom: 1px solid #222;">
                    <td style="padding: 8px; font-family: monospace; color: #e5484d;">Ctrl + + / Ctrl + -</td>
                    <td style="padding: 8px;">Zoom interface in or out uniformly</td>
                </tr>
                <tr style="border-bottom: 1px solid #222;">
                    <td style="padding: 8px; font-family: monospace; color: #e5484d;">Ctrl + 0</td>
                    <td style="padding: 8px;">Reset zoom to 100% baseline</td>
                </tr>
                <tr style="border-bottom: 1px solid #222;">
                    <td style="padding: 8px; font-family: monospace; color: #e5484d;">Ctrl + Mouse Wheel</td>
                    <td style="padding: 8px;">Dynamic zoom scaling</td>
                </tr>
                <tr style="border-bottom: 1px solid #222;">
                    <td style="padding: 8px; font-family: monospace; color: #e5484d;">Ctrl + N</td>
                    <td style="padding: 8px;">Clear text area and prepare new link list</td>
                </tr>
                <tr style="border-bottom: 1px solid #222;">
                    <td style="padding: 8px; font-family: monospace; color: #e5484d;">Ctrl + H</td>
                    <td style="padding: 8px;">Open Link History dialog</td>
                </tr>
            </table>
        </div>
        """
        browser.setHtml(html)
        return browser


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


class SignInPromptDialog(QDialog):
    """Modal dialog displayed when protected media requires sign-in or authentication."""

    def __init__(self, domain: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Sign In Required to Continue")
        self.setMinimumWidth(450)
        self.domain = domain

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        info_label = QLabel(
            f"🔒 Content on <b>{domain or 'this website'}</b> requires sign-in or account verification.",
            self,
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        sub_label = QLabel(
            "Select how you want GGU_VDOD to authenticate for this download:",
            self,
        )
        sub_label.setStyleSheet("color: #aaaaaa;")
        layout.addWidget(sub_label)

        form = QFormLayout()
        self.browser_combo = QComboBox(self)
        self.browser_combo.addItems(["Chrome", "Firefox", "Edge", "Brave", "Opera", "Safari", "Vivaldi"])
        form.addRow("Browser Session:", self.browser_combo)

        self.account_input = QLineEdit(self)
        self.account_input.setPlaceholderText("Account Label (e.g. user@domain.com)")
        form.addRow("Account Label:", self.account_input)

        layout.addLayout(form)

        btn_box = QHBoxLayout()
        self.browser_btn = QPushButton("Use Selected Browser Session", self)
        self.browser_btn.clicked.connect(self.accept)
        btn_box.addWidget(self.browser_btn)

        self.cancel_btn = QPushButton("Cancel", self)
        self.cancel_btn.clicked.connect(self.reject)
        btn_box.addWidget(self.cancel_btn)

        layout.addLayout(btn_box)

    def get_selected_browser(self) -> str:
        return self.browser_combo.currentText()

    def get_account_label(self) -> str:
        return self.account_input.text().strip()


class AgeVerificationDialog(QDialog):
    """Modal dialog for 18+ adult content age verification."""

    def __init__(self, target_url: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Age Verification Required (18+)")
        self.resize(520, 240)
        self.setMinimumSize(460, 200)

        domain = ""
        if target_url:
            try:
                domain = urllib.parse.urlparse(target_url).netloc
            except Exception:
                domain = target_url

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        hdr_frame = QFrame()
        hdr_frame.setObjectName("panel")
        hdr_frame.setStyleSheet("QFrame#panel { background: #1a1a1a; border: 1px solid #e5484d; border-radius: 8px; }")
        hdr_layout = QVBoxLayout(hdr_frame)
        hdr_layout.setContentsMargins(16, 14, 16, 14)

        title = QLabel("Age Verification Required (18+)", self)
        title.setStyleSheet("font-size: 16px; font-weight: 700; color: #e5484d;")

        msg_text = f"The URL ({domain or 'this site'}) contains adult or age-restricted media.\n\nYou must be 18 years of age or older to view, preview, or download content from this platform."
        msg = QLabel(msg_text, self)
        msg.setWordWrap(True)
        msg.setStyleSheet("font-size: 13px; color: #e2e2e2;")

        hdr_layout.addWidget(title)
        hdr_layout.addWidget(msg)
        layout.addWidget(hdr_frame)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        self.confirm_btn = QPushButton("I am 18 or older (Confirm)", self)
        self.confirm_btn.setObjectName("primary")
        self.confirm_btn.setMinimumHeight(36)
        self.confirm_btn.clicked.connect(self.accept)

        self.cancel_btn = QPushButton("Cancel / Under 18", self)
        self.cancel_btn.setMinimumHeight(36)
        self.cancel_btn.clicked.connect(self.reject)

        btn_row.addWidget(self.confirm_btn)
        btn_row.addWidget(self.cancel_btn)
        layout.addLayout(btn_row)


class AgeGateAuthDialog(QDialog):
    """Sign-in & Cookie import choice dialog for protected links."""

    def __init__(self, target_domain: str = "this domain", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Authentication & Session Setup Options")
        self.resize(580, 340)
        self.setMinimumSize(500, 300)
        self.target_domain = target_domain or "this domain"
        self.user_action = "guest"  # "guest", "cookies", "account_sessions", "mailpit"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        title = QLabel(f"Authentication Options for {self.target_domain}", self)
        title.setStyleSheet("font-size: 15px; font-weight: 700; color: #ffffff;")
        layout.addWidget(title)

        desc = QLabel(
            f"Some protected platforms require authenticated session cookies or stored credentials for {self.target_domain}.\nSelect how you would like to authenticate:",
            self
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("font-size: 12px; color: #a0a0a0;")
        layout.addWidget(desc)

        card_layout = QVBoxLayout()
        card_layout.setSpacing(10)

        self.cookie_btn = QPushButton(f"Import Browser Cookies for {self.target_domain}", self)
        self.cookie_btn.setMinimumHeight(38)
        self.cookie_btn.clicked.connect(self._on_cookies_chosen)

        self.session_btn = QPushButton("Open Account Sessions Tab (Save Encrypted Credentials)", self)
        self.session_btn.setMinimumHeight(38)
        self.session_btn.clicked.connect(self._on_sessions_chosen)

        self.mailpit_btn = QPushButton("Open Local Test Inbox (Mailpit Web UI on 127.0.0.1:8025)", self)
        self.mailpit_btn.setMinimumHeight(38)
        self.mailpit_btn.clicked.connect(self._on_mailpit_chosen)

        self.guest_btn = QPushButton("Continue as Guest (Use Impersonate & Bypass Flags)", self)
        self.guest_btn.setObjectName("primary")
        self.guest_btn.setMinimumHeight(38)
        self.guest_btn.clicked.connect(self._on_guest_chosen)

        card_layout.addWidget(self.cookie_btn)
        card_layout.addWidget(self.session_btn)
        card_layout.addWidget(self.mailpit_btn)
        card_layout.addWidget(self.guest_btn)

        layout.addLayout(card_layout)

    def _on_cookies_chosen(self):
        self.user_action = "cookies"
        self.accept()

    def _on_sessions_chosen(self):
        self.user_action = "account_sessions"
        self.accept()

    def _on_mailpit_chosen(self):
        self.user_action = "mailpit"
        self.accept()

    def _on_guest_chosen(self):
        self.user_action = "guest"
        self.accept()
