"""PySide6 dialog windows for preferences, help center, supported platforms, update checker, and shortcuts."""

import importlib.metadata
import html
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import threading
import urllib.parse
import urllib.request
from PySide6.QtCore import Qt, QThread, Signal, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QFont, QFontDatabase, QKeySequence
from PySide6.QtWidgets import (
    QApplication, QAbstractItemView, QCheckBox, QColorDialog, QComboBox, QDialog, QFileDialog, QFormLayout,
    QFrame, QGridLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QMessageBox, QPlainTextEdit, QPushButton, QScrollArea, QSlider, QSpinBox,
    QTableWidget, QTableWidgetItem, QTabWidget, QTextEdit, QVBoxLayout, QWidget,
)

from ...config.paths import get_app_dir, get_default_output_dir
from ...core.constants import (
    APP_NAME, DEFAULT_KEY_BINDINGS, KEY_BINDING_CHOICES, SCROLL_SPEED_DEFAULT,
    SCROLL_SPEED_MAX, SCROLL_SPEED_MIN, UPDATE_COMPONENTS, clamp_scroll_speed,
)
from ...core.version import DEVELOPMENT_BUILD_LABEL, PACKAGE_VERSION
from .theme import THEME_COLOR_FIELDS, THEME_PRESETS, is_valid_theme_color, normalize_theme, theme_name
from .widgets import detach_running_worker


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
        try:
            import yt_dlp
        except ImportError:
            yt_dlp = None
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
        from ...services.i18n import t

        self.setWindowTitle(t("menu.platforms", "Supported Platforms & Extractors"))
        self.resize(750, 550)
        self.setMinimumSize(600, 400)
        self.all_extractors = []

        self._build_ui()
        self._start_loading()

    def _build_ui(self):
        from ...services.i18n import t

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        header = QHBoxLayout()
        header.addWidget(QLabel(t("platforms.search_lbl", "Search Platform / Extractor:")))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(t("platforms.search_placeholder", "Filter platforms (e.g. youtube, vimeo, twitter, twitch)..."))
        self.search_input.textChanged.connect(self._filter_table)
        header.addWidget(self.search_input, 1)
        layout.addLayout(header)

        self.table = QTableWidget()
        self.table.setColumnCount(1)
        self.table.setHorizontalHeaderLabels([
            t("platforms.table_name", "Extractor / Platform Name"),
        ])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)

        layout.addWidget(self.table, 1)

        btn_row = QHBoxLayout()
        self.count_label = QLabel(t("platforms.loading", "Loading extractors..."))
        self.count_label.setObjectName("muted")
        btn_row.addWidget(self.count_label)
        btn_row.addStretch(1)
        close_btn = QPushButton(t("dialogs.close", "Close"))
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
        detach_running_worker(getattr(self, "worker", None))
        super().closeEvent(event)

    def _filter_table(self, query):
        query = query.strip().lower()
        filtered = [
            (name, desc) for name, desc in self.all_extractors
            if not query or query in name.lower()
        ]

        self.table.setRowCount(len(filtered))
        for row, (name, desc) in enumerate(filtered):
            self.table.setItem(row, 0, QTableWidgetItem(name))


def get_installed_component_version(name: str, module_name: str) -> str:
    """Return installed version of a python library or executable binary."""
    if name.lower() == "ffmpeg":
        from ...config.paths import get_default_ffmpeg_path
        exe = get_default_ffmpeg_path()
        if exe and os.path.exists(exe):
            try:
                res = subprocess.run([exe, "-version"], capture_output=True, text=True, timeout=4)
                m = re.search(r"ffmpeg version\s+([^\s]+)", res.stdout, re.IGNORECASE)
                if m:
                    return m.group(1)
            except Exception:
                pass
            return "Installed (Binary)"
        return "Not installed"

    if name.lower() == "ffprobe":
        from ...config.paths import get_default_ffprobe_path
        exe = get_default_ffprobe_path()
        if exe and os.path.exists(exe):
            try:
                res = subprocess.run([exe, "-version"], capture_output=True, text=True, timeout=4)
                m = re.search(r"ffprobe version\s+([^\s]+)", res.stdout, re.IGNORECASE)
                if m:
                    return m.group(1)
            except Exception:
                pass
            return "Installed (Binary)"
        return "Not installed"

    try:
        ver = importlib.metadata.version(name)
        if ver:
            return ver
    except Exception:
        pass

    try:
        mod = sys.modules.get(module_name) or __import__(module_name)
        if hasattr(mod, "version") and hasattr(mod.version, "__version__"):
            return str(mod.version.__version__)
        if hasattr(mod, "__version__"):
            return str(mod.__version__)
    except Exception:
        pass

    return "Not installed"


class UpdateCheckWorker(QThread):
    """Check installed package versions against PyPI in the background."""
    results_ready = Signal(list)

    def run(self):
        results = []
        for name, module_name, component_type in UPDATE_COMPONENTS:
            installed = get_installed_component_version(name, module_name)
            latest = "—"
            status = "Not installed" if installed == "Not installed" else "Up to date"
            if installed != "Not installed" and name.lower() not in ("ffmpeg", "ffprobe"):
                try:
                    package_name = urllib.parse.quote(name, safe="")
                    request = urllib.request.Request(
                        f"https://pypi.org/pypi/{package_name}/json",
                        headers={"User-Agent": f"{APP_NAME}/{installed}"},
                    )
                    with urllib.request.urlopen(request, timeout=8) as response:
                        latest = str(json.load(response)["info"]["version"])
                    if name == "curl_cffi" and self._version_key(latest) > (0, 15, 0):
                        latest = "0.15.0 (Max for yt-dlp)"
                        status = "Up to date"
                    else:
                        status = "Update available" if self._version_key(installed) < self._version_key(latest) else "Up to date"
                except Exception:
                    status = "Up to date"
            elif installed != "Not installed":
                latest = "Latest Build"
                status = "Ready"

            results.append((name, component_type, installed, latest, status))
        self.results_ready.emit(results)

    @staticmethod
    def _version_key(version):
        return tuple(int(part) for part in re.findall(r"\d+", version or "0"))


UPDATEABLE_PACKAGES = {
    "yt-dlp": "yt-dlp",
    "curl_cffi": "curl_cffi",
    "Pillow": "Pillow",
    "PySide6": "PySide6",
    "PyInstaller": "PyInstaller",
}


def find_project_python() -> str | None:
    """Find the project virtual-environment interpreter used for package updates."""
    candidates = []
    if not getattr(sys, "frozen", False):
        candidates.append(sys.executable)

    app_dir = Path(get_app_dir()).resolve()
    for folder in (app_dir, *app_dir.parents):
        candidates.append(str(folder / "venv" / "Scripts" / "python.exe"))

    for candidate in candidates:
        if candidate and os.path.isfile(candidate):
            return candidate
    return None


class PackageUpdateWorker(QThread):
    """Update checked Python packages without blocking the Qt interface."""

    package_completed = Signal(str, bool, str)
    all_completed = Signal(int, int)

    def __init__(self, packages, parent=None):
        super().__init__(parent)
        self.packages = list(packages)

    def run(self):
        python_executable = find_project_python()
        if not python_executable:
            message = "Could not find the project's venv\\Scripts\\python.exe interpreter."
            for package in self.packages:
                self.package_completed.emit(package, False, message)
            self.all_completed.emit(0, len(self.packages))
            return

        succeeded = 0
        failed = 0
        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0
        for package in self.packages:
            try:
                target_pkg = "curl_cffi==0.15.0" if package == "curl_cffi" else package
                cmd = [python_executable, "-m", "pip", "install", "--upgrade" if package != "curl_cffi" else "--force-reinstall", "--disable-pip-version-check", target_pkg]
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=180,
                    creationflags=creation_flags,
                )
                output = (result.stdout or result.stderr or "Package installer returned no details.").strip()
                if result.returncode == 0:
                    succeeded += 1
                    self.package_completed.emit(package, True, output)
                else:
                    failed += 1
                    self.package_completed.emit(package, False, output)
            except Exception as error:
                failed += 1
                self.package_completed.emit(package, False, str(error))
        self.all_completed.emit(succeeded, failed)


class UpdateCheckDialog(QDialog):
    """Dialog showing runtime component versions and update check."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Check for Updates & Dependencies")
        self.resize(600, 400)
        self.setMinimumSize(540, 360)
        self._results = []
        self._row_for_component = {}
        self._update_worker = None

        self._build_ui()
        self._check_versions()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(14)

        title = QLabel("Component & Dependency Status")
        title.setStyleSheet("font-size: 17px; font-weight: bold;")
        layout.addWidget(title)

        self.update_note = QLabel(
            "Updates apply to this project's Python environment. Rebuild GGU_VDOD after updating to include them in the EXE."
        )
        self.update_note.setObjectName("muted")
        self.update_note.setWordWrap(True)
        layout.addWidget(self.update_note)

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Component", "Type", "Installed", "Latest", "Status"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table, 1)

        btn_row = QHBoxLayout()
        self.update_btn = QPushButton("Update available components")
        self.update_btn.setObjectName("primary")
        self.update_btn.setEnabled(False)
        self.update_btn.clicked.connect(self._update_available_components)
        btn_row.addWidget(self.update_btn)

        self.refresh_btn = QPushButton("Check again")
        self.refresh_btn.clicked.connect(self._check_versions)
        btn_row.addWidget(self.refresh_btn)

        btn_row.addStretch(1)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    def _check_versions(self):
        if hasattr(self, "worker") and self.worker.isRunning():
            return
        self.refresh_btn.setEnabled(False)
        self.worker = UpdateCheckWorker(self)
        self.worker.results_ready.connect(self._populate_results)
        self.worker.start()

    def _populate_results(self, results):
        self._results = list(results)
        self._row_for_component = {}
        self.table.setRowCount(len(results))
        for row, (name, comp_type, installed, latest, status) in enumerate(results):
            self._row_for_component[name] = row
            self.table.setItem(row, 0, QTableWidgetItem(name))
            self.table.setItem(row, 1, QTableWidgetItem(comp_type))
            self.table.setItem(row, 2, QTableWidgetItem(installed))
            self.table.setItem(row, 3, QTableWidgetItem(latest))
            self.table.setItem(row, 4, QTableWidgetItem(status))
        available = [
            name for name, _kind, _installed, _latest, status in results
            if status == "Update available" and name in UPDATEABLE_PACKAGES and name != "PySide6"
        ]
        self.update_btn.setEnabled(bool(available))
        self.update_btn.setText(
            f"Update {len(available)} available component(s)" if available else "Everything is up to date"
        )
        self.refresh_btn.setEnabled(True)

    def _update_available_components(self):
        # PySide6 is deliberately excluded: replacing Qt DLLs under the running
        # process can break this session and the next launch. Update it manually
        # and rebuild instead.
        packages = [
            UPDATEABLE_PACKAGES[name]
            for name, _kind, _installed, _latest, status in self._results
            if status == "Update available" and name in UPDATEABLE_PACKAGES and name != "PySide6"
        ]
        if not packages:
            QMessageBox.information(
                self,
                "Update components",
                "Only PySide6 has an update, and it must be updated manually outside the running app "
                "(pip install --upgrade PySide6), followed by a rebuild.",
            )
            return

        answer = QMessageBox.question(
            self,
            "Update components",
            "Update the available Python components now?\n\n"
            "The app will stay open. Rebuild GGU_VDOD afterwards so the updated libraries are bundled into the EXE.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        self.update_btn.setEnabled(False)
        self.refresh_btn.setEnabled(False)
        for name, _kind, _installed, _latest, status in self._results:
            if status == "Update available" and name in UPDATEABLE_PACKAGES:
                row = self._row_for_component.get(name)
                if row is not None:
                    self.table.setItem(row, 4, QTableWidgetItem("Updating..."))

        self._update_worker = PackageUpdateWorker(packages, self)
        self._update_worker.package_completed.connect(self._on_package_updated)
        self._update_worker.all_completed.connect(self._on_updates_completed)
        self._update_worker.start()

    def _on_package_updated(self, package, succeeded, output):
        component = next((name for name, pip_name in UPDATEABLE_PACKAGES.items() if pip_name == package), package)
        row = self._row_for_component.get(component)
        if row is not None:
            self.table.setItem(row, 4, QTableWidgetItem("Updated - rebuild required" if succeeded else "Update failed"))
        if output:
            self.update_note.setText(
                f"{component}: {'updated successfully' if succeeded else 'update failed'}. "
                f"{output.splitlines()[-1]}"
            )

    def _on_updates_completed(self, succeeded, failed):
        self.refresh_btn.setEnabled(True)
        self.update_btn.setEnabled(False)
        QMessageBox.information(
            self,
            "Component updates finished",
            f"Updated: {succeeded}\nFailed: {failed}\n\nRebuild GGU_VDOD to bundle successful updates into the EXE.",
        )
        self._check_versions()

    def closeEvent(self, event):
        detach_running_worker(getattr(self, "worker", None))
        detach_running_worker(self._update_worker)
        super().closeEvent(event)


class MediaProbeWorker(QThread):
    """Background worker executing ffprobe.exe stream analysis."""
    probe_completed = Signal(dict)

    def __init__(self, target_path_or_url: str, parent=None):
        super().__init__(parent)
        self.target = target_path_or_url

    def run(self):
        from ...services.probe import probe_media_file
        res = probe_media_file(self.target, timeout=12)
        self.probe_completed.emit(res)


class DeepMediaInspectorDialog(QDialog):
    """Modern FFprobe Deep Media Inspector Dialog displaying detailed video, audio, and container streams."""

    def __init__(self, target_path_or_url: str, parent=None):
        super().__init__(parent)
        self.target = target_path_or_url
        self.setWindowTitle("FFprobe Deep Media Inspector")
        self.resize(750, 560)
        self.setMinimumSize(640, 440)
        self._raw_json_text = ""

        self._build_ui()
        self._start_probe()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        # Header Title
        hdr_frame = QFrame()
        hdr_frame.setObjectName("panel")
        hdr_frame.setStyleSheet("QFrame#panel { background: #141414; border: 1px solid #333; border-radius: 8px; }")
        hdr_layout = QHBoxLayout(hdr_frame)
        hdr_layout.setContentsMargins(16, 12, 16, 12)

        hdr_info = QVBoxLayout()
        self.title_lbl = QLabel("Inspecting Media Stream…", self)
        self.title_lbl.setStyleSheet("font-size: 16px; font-weight: 700; color: #ffffff;")
        self.target_lbl = QLabel(os.path.basename(self.target) or self.target, self)
        self.target_lbl.setObjectName("muted")
        hdr_info.addWidget(self.title_lbl)
        hdr_info.addWidget(self.target_lbl)
        hdr_layout.addLayout(hdr_info, 1)

        self.health_badge = QLabel("ANALYZING…", self)
        self.health_badge.setStyleSheet("background: #2a2a2a; color: #aaa; font-weight: 700; border-radius: 4px; padding: 6px 12px; font-size: 12px;")
        hdr_layout.addWidget(self.health_badge)
        layout.addWidget(hdr_frame)

        # Main Tab Widget
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs, 1)

        # Tab 1: Overview Summary
        self.summary_tab = QWidget()
        sum_layout = QVBoxLayout(self.summary_tab)
        sum_layout.setContentsMargins(12, 12, 12, 12)

        self.summary_text = QTextEdit()
        self.summary_text.setReadOnly(True)
        sum_layout.addWidget(self.summary_text)
        self.tabs.addTab(self.summary_tab, "Overview")

        # Tab 2: Video Streams Table
        self.video_tab = QWidget()
        vid_layout = QVBoxLayout(self.video_tab)
        vid_layout.setContentsMargins(12, 12, 12, 12)
        self.video_table = QTableWidget()
        self.video_table.setColumnCount(8)
        self.video_table.setHorizontalHeaderLabels(["Index", "Codec", "Profile", "Resolution", "FPS", "Pix Format", "Bitrate", "Aspect Ratio"])
        self.video_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.video_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        vid_layout.addWidget(self.video_table)
        self.tabs.addTab(self.video_tab, "Video Tracks")

        # Tab 3: Audio Streams Table
        self.audio_tab = QWidget()
        aud_layout = QVBoxLayout(self.audio_tab)
        aud_layout.setContentsMargins(12, 12, 12, 12)
        self.audio_table = QTableWidget()
        self.audio_table.setColumnCount(7)
        self.audio_table.setHorizontalHeaderLabels(["Index", "Codec", "Sample Rate", "Channels", "Layout", "Bitrate", "Language"])
        self.audio_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.audio_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        aud_layout.addWidget(self.audio_table)
        self.tabs.addTab(self.audio_tab, "Audio Tracks")

        # Tab 4: Raw JSON Report
        self.json_tab = QWidget()
        json_layout = QVBoxLayout(self.json_tab)
        json_layout.setContentsMargins(12, 12, 12, 12)
        self.json_edit = QTextEdit()
        self.json_edit.setReadOnly(True)
        json_layout.addWidget(self.json_edit)
        self.tabs.addTab(self.json_tab, "FFprobe JSON")

        # Button Row
        btn_row = QHBoxLayout()
        copy_json_btn = QPushButton("Copy JSON")
        copy_json_btn.setToolTip("Copy complete ffprobe JSON report to clipboard.")
        copy_json_btn.clicked.connect(self._copy_json)
        save_json_btn = QPushButton("Save JSON Report…")
        save_json_btn.clicked.connect(self._save_json)
        btn_row.addWidget(copy_json_btn)
        btn_row.addWidget(save_json_btn)
        btn_row.addStretch(1)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    def _start_probe(self):
        self.worker = MediaProbeWorker(self.target, self)
        self.worker.probe_completed.connect(self._on_probe_completed)
        self.worker.start()

    def _on_probe_completed(self, res: dict):
        if not res.get("success"):
            self.health_badge.setText("PROBE FAILED")
            self.health_badge.setStyleSheet("background: #5c1d1d; color: #ff9999; font-weight: 700; border-radius: 4px; padding: 6px 12px;")
            err_msg = res.get("error", "Unknown error inspecting media file")
            self.summary_text.setHtml(f"<p style='color: #ff6666;'><b>FFprobe Inspection Failed:</b> {err_msg}</p>")
            return

        is_healthy = res.get("is_healthy", True)
        if is_healthy:
            self.health_badge.setText("HEALTHY STREAM")
            self.health_badge.setStyleSheet("background: #1b4721; color: #75f086; font-weight: 700; border-radius: 4px; padding: 6px 12px;")
        else:
            self.health_badge.setText("CHECK REQUIRED")
            self.health_badge.setStyleSheet("background: #543714; color: #ffd166; font-weight: 700; border-radius: 4px; padding: 6px 12px;")

        filename = res.get("filename", "Media File")
        format_name = res.get("format_name", "—")
        duration_fmt = res.get("duration_formatted", "—")
        from ...core.formatting import format_bytes
        size_str = format_bytes(int(res.get("size") or 0)) if res.get("size") else "—"

        vid_streams = res.get("video_streams", [])
        aud_streams = res.get("audio_streams", [])

        # Summary Tab HTML
        summary_html = f"""
        <div style="font-family: 'Segoe UI', system-ui, sans-serif; line-height: 1.6;">
            <h3 style="margin-top: 0; color: #ffffff;">Media Container Overview</h3>
            <table style="width: 100%; border-collapse: collapse; color: #d0d0d0;">
                <tr><td style="padding: 4px 0; width: 140px;"><b>File Name:</b></td><td>{filename}</td></tr>
                <tr><td style="padding: 4px 0;"><b>Format Container:</b></td><td>{format_name}</td></tr>
                <tr><td style="padding: 4px 0;"><b>Duration:</b></td><td>{duration_fmt}</td></tr>
                <tr><td style="padding: 4px 0;"><b>File Size:</b></td><td>{size_str}</td></tr>
                <tr><td style="padding: 4px 0;"><b>Video Streams:</b></td><td>{len(vid_streams)} track(s)</td></tr>
                <tr><td style="padding: 4px 0;"><b>Audio Streams:</b></td><td>{len(aud_streams)} track(s)</td></tr>
            </table>
        </div>
        """
        self.summary_text.setHtml(summary_html)

        # Video Table
        self.video_table.setRowCount(len(vid_streams))
        for row, v in enumerate(vid_streams):
            self.video_table.setItem(row, 0, QTableWidgetItem(str(v.get("index", row))))
            self.video_table.setItem(row, 1, QTableWidgetItem(str(v.get("codec_name", "?"))))
            self.video_table.setItem(row, 2, QTableWidgetItem(str(v.get("profile", "—"))))
            self.video_table.setItem(row, 3, QTableWidgetItem(str(v.get("resolution", "—"))))
            self.video_table.setItem(row, 4, QTableWidgetItem(str(v.get("fps", "—"))))
            self.video_table.setItem(row, 5, QTableWidgetItem(str(v.get("pix_fmt", "—"))))
            self.video_table.setItem(row, 6, QTableWidgetItem(str(v.get("bit_rate") or "—")))
            self.video_table.setItem(row, 7, QTableWidgetItem(str(v.get("aspect_ratio", "—"))))

        # Audio Table
        self.audio_table.setRowCount(len(aud_streams))
        for row, a in enumerate(aud_streams):
            self.audio_table.setItem(row, 0, QTableWidgetItem(str(a.get("index", row))))
            self.audio_table.setItem(row, 1, QTableWidgetItem(str(a.get("codec_name", "?"))))
            self.audio_table.setItem(row, 2, QTableWidgetItem(str(a.get("sample_rate", "—"))))
            self.audio_table.setItem(row, 3, QTableWidgetItem(str(a.get("channels", "—"))))
            self.audio_table.setItem(row, 4, QTableWidgetItem(str(a.get("channel_layout", "—"))))
            self.audio_table.setItem(row, 5, QTableWidgetItem(str(a.get("bit_rate") or "—")))
            self.audio_table.setItem(row, 6, QTableWidgetItem(str(a.get("language", "—"))))

        # Raw JSON Tab
        raw_obj = res.get("raw_json", {})
        self._raw_json_text = json.dumps(raw_obj, indent=2)
        self.json_edit.setPlainText(self._raw_json_text)

    def _copy_json(self):
        if self._raw_json_text:
            QApplication.clipboard().setText(self._raw_json_text)
            QMessageBox.information(self, "Copied", "FFprobe JSON report copied to clipboard.")

    def _save_json(self):
        if not self._raw_json_text:
            return
        save_path, _ = QFileDialog.getSaveFileName(self, "Save FFprobe Report", f"{os.path.basename(self.target)}_probe.json", "JSON files (*.json)")
        if save_path:
            try:
                with open(save_path, "w", encoding="utf-8") as f:
                    f.write(self._raw_json_text)
                QMessageBox.information(self, "Saved", f"FFprobe report saved to:\n{save_path}")
            except Exception as err:
                QMessageBox.critical(self, "Error", f"Failed to save JSON report:\n{err}")

    def closeEvent(self, event):
        detach_running_worker(getattr(self, "worker", None))
        super().closeEvent(event)


class AboutDialog(QDialog):
    """Detailed About Dialog displaying App Info, Developer details (XerumGG), License, and Key Use Cases."""

    def __init__(self, parent=None):
        super().__init__(parent)
        from ...services.i18n import t

        self.setWindowTitle(t("menu.about_app", "About GGU_VDOD"))
        self.resize(650, 520)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        hdr = QFrame()
        hdr.setObjectName("panel")
        hdr.setStyleSheet("QFrame#panel { background: #141414; border: 1px solid #333; border-radius: 8px; }")
        hdr_layout = QVBoxLayout(hdr)
        hdr_layout.setContentsMargins(18, 14, 18, 14)

        title = QLabel(APP_NAME, self)
        title.setStyleSheet("font-size: 22px; font-weight: 700; color: #e5484d;")
        sub = QLabel(f"Developer: XerumGG\n{DEVELOPMENT_BUILD_LABEL} | Version: {PACKAGE_VERSION}", self)
        sub.setStyleSheet("font-size: 13px; color: #ffffff; margin-top: 4px; font-weight: 500;")
        hdr_layout.addWidget(title)
        hdr_layout.addWidget(sub)
        layout.addWidget(hdr)

        text_edit = QTextEdit(self)
        text_edit.setReadOnly(True)
        html = f"""
        <div style="font-family: 'Segoe UI', system-ui, sans-serif; line-height: 1.6; color: #d0d0d0;">
            <h3 style="color: #ffffff; margin-top: 0;">{t('about.summary_header', 'Application Summary')}</h3>
            <p><b>{APP_NAME}</b> {t('about.summary_body', 'is a high-performance desktop media downloader, batch queue processor, and local converter designed for video/audio streams, HLS/DASH fragments, and playlists.')}</p>
            
            <h3 style="color: #ffffff;">{t('about.dev_header', 'Developer & License Details')}</h3>
            <ul style="padding-left: 20px;">
                <li><b>Developer / Maintainer:</b> XerumGG</li>
                <li><b>License:</b> MIT License (Open Source Software)</li>
                <li><b>UI Framework:</b> PySide6 (Qt 6 for Python)</li>
                <li><b>Core Downloader & Muxer:</b> yt-dlp, curl_cffi, FFmpeg, & FFprobe</li>
            </ul>

            <h3 style="color: #ffffff;">{t('about.cap_header', 'Key Capabilities & Use Cases')}</h3>
            <ol style="padding-left: 20px;">
                <li><b>{t('about.cap1_title', 'High-Res Downloads & Transcoding:')}</b> {t('about.cap1_body', 'Bulk download 4K/2K/1080p videos or convert audio to MP3, WAV, FLAC, AAC, OPUS, and M4A.')}</li>
                <li><b>{t('about.cap2_title', 'Cloudflare Anti-Bot Impersonation:')}</b> {t('about.cap2_body', 'Uses native TLS Chrome browser impersonation to bypass HTTP 403 Cloudflare challenges.')}</li>
                <li><b>{t('about.cap3_title', 'DPAPI Encrypted Account Sessions:')}</b> {t('about.cap3_body', 'Saves domain credentials and tokens securely under Windows DPAPI encryption.')}</li>
                <li><b>{t('about.cap4_title', 'Age Verification & Local Test Inbox:')}</b> {t('about.cap4_body', 'Automatically detects 18+ age restrictions and integrates with local Mailpit (127.0.0.1:8025) for signups.')}</li>
                <li><b>{t('about.cap5_title', 'Automatic Component Update Check:')}</b> {t('about.cap5_body', 'Periodically verifies installed versions of yt-dlp, PySide6, Pillow, PyInstaller, curl_cffi, FFmpeg, and FFprobe.')}</li>
            </ol>
        </div>
        """
        text_edit.setHtml(html)
        layout.addWidget(text_edit, 1)

        btn_box = QHBoxLayout()
        btn_box.addStretch(1)
        close_btn = QPushButton(t("dialogs.close", "Close"), self)
        close_btn.clicked.connect(self.accept)
        btn_box.addWidget(close_btn)
        layout.addLayout(btn_box)


class HelpCenterDialog(QDialog):
    """Modern Help Center & User Guide Dialog."""

    def __init__(self, parent=None):
        super().__init__(parent)
        from ...services.i18n import t

        self.setWindowTitle(t("help.center_title", "GGU_VDOD Help Center & Quick Guide"))
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

        title = QLabel(t("help.doc_header", f"{APP_NAME} Documentation & User Guide"), self)
        title.setStyleSheet("font-size: 17px; font-weight: 700; color: #ffffff;")
        subtitle = QLabel(t("help.doc_subtitle", "Reference guide for account sessions, local mailpit testing, media downloads, and conversion options."), self)
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
        self.tabs.addTab(self._build_account_mailpit_tab(), t("help.tab_account", "Account Sessions & Local Inbox"))
        # Tab 2: How to Download Media
        self.tabs.addTab(self._build_download_tab(), t("help.tab_download", "Downloading Media"))
        # Tab 3: Complex Conversion Options
        self.tabs.addTab(self._build_complex_tab(), t("help.tab_complex", "Complex Options Guide"))
        # Tab 4: Shortcuts
        self.tabs.addTab(self._build_shortcuts_tab(), t("help.tab_shortcuts", "Keyboard Shortcuts"))

        layout.addWidget(self.tabs, 1)

        # Action bar
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        close_btn = QPushButton(t("dialogs.close", "Close Help"), self)
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
                <h3 style="margin-top: 0; color: #e5484d; font-size: 16px;">1. Account Sessions & Local Test Inbox Guide</h3>
                <p style="color: #a7a7a7; font-size: 12px; margin-top: -6px;"><i>Example Targets: Protected media platforms (e.g. <b>example.com</b> or <b>staging.local</b>)</i></p>
                
                <h4 style="color: #ffffff; margin-bottom: 6px; font-size: 14px;">B. Authentication Options for Age-Restricted Sites</h4>
                <ul style="margin-top: 4px; padding-left: 20px;">
                    <li><b>Option 1 (Auto-Import Browser Cookies):</b> Imports active session cookies from Chrome, Firefox, Edge, Brave, Vivaldi, etc., to bypass age verification gates automatically.</li>
                    <li><b>Option 2 (Account Sessions Tab):</b> Registers stored account credentials (username/password/token) under DPAPI encryption for the domain.</li>
                    <li><b>Option 3 (Local Test Inbox Mailpit):</b> Opens local email capture dashboard on <code>127.0.0.1:8025</code> for staging account signups.</li>
                    <li><b>Option 3 (Continue without sign-in):</b> Sets native <code>age_limit: 99</code> bypass flags in yt-dlp to extract public age-restricted streams without login.</li>
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
    """Dialog showing history of past media links with retry and open actions."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Link History")
        self.resize(850, 520)
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
        self.table.setHorizontalHeaderLabels(["Title / URL", "Status", "Format", "Date"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table, 1)

        btn_row = QHBoxLayout()

        copy_btn = QPushButton("Copy URL")
        copy_btn.clicked.connect(self._copy_selected)
        btn_row.addWidget(copy_btn)

        open_file_btn = QPushButton("Open File")
        open_file_btn.clicked.connect(self._open_selected_file)
        btn_row.addWidget(open_file_btn)

        open_folder_btn = QPushButton("Open Folder")
        open_folder_btn.clicked.connect(self._open_selected_folder)
        btn_row.addWidget(open_folder_btn)

        retry_sel_btn = QPushButton("Retry Selected")
        retry_sel_btn.setObjectName("primary")
        retry_sel_btn.clicked.connect(lambda: self._retry_to_queue(only_failed=False))
        btn_row.addWidget(retry_sel_btn)

        retry_failed_btn = QPushButton("Retry All Failed")
        retry_failed_btn.setObjectName("primary")
        retry_failed_btn.clicked.connect(lambda: self._retry_to_queue(only_failed=True))
        btn_row.addWidget(retry_failed_btn)

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
            title_item = QTableWidgetItem(item.get("title") or item.get("url") or "")
            title_item.setData(Qt.ItemDataRole.UserRole, item.get("url") or "")
            title_item.setData(Qt.ItemDataRole.UserRole + 1, item.get("final_file") or "")
            title_item.setToolTip(item.get("url") or "")
            status_item = QTableWidgetItem(item.get("status", ""))
            if str(item.get("status", "")).startswith("Failed"):
                from PySide6.QtGui import QColor
                status_item.setForeground(QColor("#ff6b6b"))
            elif item.get("status") == "Completed":
                from PySide6.QtGui import QColor
                status_item.setForeground(QColor("#57c26a"))
            self.table.setItem(row, 0, title_item)
            self.table.setItem(row, 1, status_item)
            self.table.setItem(row, 2, QTableWidgetItem(item.get("format", "")))
            self.table.setItem(row, 3, QTableWidgetItem(item.get("timestamp", "")))

    def _selected_url(self):
        row = self.table.currentRow()
        if row < 0:
            return "", ""
        item = self.table.item(row, 0)
        return (item.data(Qt.ItemDataRole.UserRole) or "", item.data(Qt.ItemDataRole.UserRole + 1) or "")

    def _copy_selected(self):
        url, _ = self._selected_url()
        if url:
            QApplication.clipboard().setText(url)
            QMessageBox.information(self, "Copied", "Link copied to clipboard!")

    def _open_selected_file(self):
        _, final_file = self._selected_url()
        if final_file and os.path.isfile(final_file):
            QDesktopServices.openUrl(QUrl.fromLocalFile(final_file))
        else:
            QMessageBox.information(self, "Not available", "The output file for this entry was not recorded or no longer exists.")

    def _open_selected_folder(self):
        _, final_file = self._selected_url()
        folder = os.path.dirname(final_file) if final_file else ""
        if folder and os.path.isdir(folder):
            QDesktopServices.openUrl(QUrl.fromLocalFile(folder))
        else:
            QMessageBox.information(self, "Not available", "The folder for this entry was not recorded or no longer exists.")

    def _retry_to_queue(self, only_failed: bool):
        parent = self.parent()
        if not parent or not hasattr(parent, "url_text"):
            return
        urls = []
        rows = range(self.table.rowCount())
        for row in rows:
            item = self.table.item(row, 0)
            status = self.table.item(row, 1)
            url = item.data(Qt.ItemDataRole.UserRole) if item else ""
            st = status.text() if status else ""
            if only_failed and not st.startswith("Failed"):
                continue
            if not only_failed:
                row_sel = self.table.currentRow()
                if row_sel != row:
                    continue
            if url:
                urls.append(url)
        if not urls:
            QMessageBox.information(self, "Nothing to retry", "Select a row (or use Retry All Failed).")
            return
        curr = parent.url_text.toPlainText().strip()
        parent.url_text.setPlainText("\n".join(filter(None, [curr, *urls])))
        self.accept()

    def _clear_history(self):
        from ...config.store import clear_history
        clear_history()
        self._load_data()


def scan_library_files(output_dir):
    """Walk the output directory and bucket files into videos/audios/images."""
    video_exts = {".mp4", ".mkv", ".mov", ".avi", ".webm", ".flv", ".mpeg", ".ts", ".m4v", ".ogv", ".3gp"}
    audio_exts = {".mp3", ".m4a", ".aac", ".wav", ".flac", ".opus", ".ogg", ".alac"}
    image_exts = {".jpg", ".jpeg", ".png", ".webp"}

    videos, audios, images = [], [], []
    if os.path.exists(output_dir):
        for root_path, _, filenames in os.walk(output_dir):
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
    return videos, audios, images


class LibraryScanWorker(QThread):
    """Scan the media library off the UI loop so large folders never freeze it."""

    scanned = Signal(list, list, list)

    def __init__(self, output_dir, parent=None):
        super().__init__(parent)
        self.output_dir = output_dir

    def run(self):
        videos, audios, images = scan_library_files(self.output_dir)
        self.scanned.emit(videos, audios, images)


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

        self.tabs.addTab(self.video_table, "Videos")
        self.tabs.addTab(self.audio_table, "Audios")
        self.tabs.addTab(self.image_table, "Thumbnails")

        layout.addWidget(self.tabs, 1)

        btn_row = QHBoxLayout()
        play_btn = QPushButton("Open / Play File")
        play_btn.setObjectName("primary")
        play_btn.clicked.connect(self._open_selected_file)
        btn_row.addWidget(play_btn)

        folder_btn = QPushButton("Show in Folder")
        folder_btn.clicked.connect(self._show_in_folder)
        btn_row.addWidget(folder_btn)

        probe_btn = QPushButton("Inspect Streams (FFprobe)")
        probe_btn.setToolTip("Inspect detailed video/audio stream properties using FFprobe.")
        probe_btn.clicked.connect(self._inspect_selected_file)
        btn_row.addWidget(probe_btn)

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
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        return table

    def _scan_files(self):
        if getattr(self, "_scan_worker", None) and self._scan_worker.isRunning():
            return
        self._scan_worker = LibraryScanWorker(self.output_dir, self)
        self._scan_worker.scanned.connect(self._on_library_scanned)
        self._scan_worker.finished.connect(
            lambda w=self._scan_worker: setattr(self, "_scan_worker", None)
        )
        self._scan_worker.start()

    def _on_library_scanned(self, videos, audios, images):
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

    def _inspect_selected_file(self):
        table = self._get_active_table()
        row = table.currentRow()
        if row >= 0:
            path = table.item(row, 0).data(Qt.ItemDataRole.UserRole)
            if path and os.path.exists(path):
                dlg = DeepMediaInspectorDialog(path, self)
                dlg.exec()
            else:
                QMessageBox.warning(self, "File Missing", f"The selected file does not exist:\n{path}")

    def closeEvent(self, event):
        detach_running_worker(getattr(self, "_scan_worker", None))
        super().closeEvent(event)


class ErrorAlertDialog(QDialog):
    """Interactive, user-friendly Error Alert Dialog with natural language explanations and actions."""

    def __init__(self, error_details, parent=None):
        super().__init__(parent)
        from ...services.errors import ErrorDetails
        self.details: ErrorDetails = error_details
        self.setWindowTitle(f"Alert: {self.details.title}")
        self.resize(640, 460)
        self.setMinimumSize(540, 360)

        from ...services.audio import play_error_sound
        play_error_sound(self.details.sound_type, self.details.code)

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(14)

        # Header Title Banner
        hdr_frame = QFrame()
        hdr_frame.setObjectName("panel")

        # Color accent based on severity
        border_color = "#e5484d" if self.details.severity == "CRITICAL" else ("#f5a623" if self.details.severity == "WARNING" else "#3b82f6")
        hdr_frame.setStyleSheet(f"QFrame#panel {{ background: #141414; border: 1px solid {border_color}; border-radius: 8px; }}")

        hdr_layout = QHBoxLayout(hdr_frame)
        hdr_layout.setContentsMargins(16, 12, 16, 12)

        hdr_info = QVBoxLayout()
        title_lbl = QLabel(self.details.title, self)
        title_lbl.setStyleSheet(f"font-size: 18px; font-weight: 700; color: {border_color};")
        code_lbl = QLabel(f"Category: {self.details.code}  |  Severity: {self.details.severity}", self)
        code_lbl.setObjectName("muted")
        hdr_info.addWidget(title_lbl)
        hdr_info.addWidget(code_lbl)
        hdr_layout.addLayout(hdr_info, 1)

        layout.addWidget(hdr_frame)

        # Simple Message & Recommended Solution Box
        msg_box = QTextEdit(self)
        msg_box.setReadOnly(True)
        html_content = f"""
        <div style="font-family: 'Segoe UI', system-ui, sans-serif; line-height: 1.6; color: #e0e0e0;">
            <h4 style="margin-top: 0; color: #ffffff;">What Happened?</h4>
            <p style="font-size: 14px; color: #ffffff;">{self.details.simple_message}</p>

            <h4 style="color: #ffffff; margin-top: 14px;">Recommended Fix Action</h4>
            <p style="font-size: 13px; color: #75f086; font-weight: 600;">{self.details.recommendation}</p>
        </div>
        """
        msg_box.setHtml(html_content)
        layout.addWidget(msg_box, 1)

        # Collapsible Raw Log Section
        self.raw_log_edit = QPlainTextEdit(self)
        self.raw_log_edit.setPlainText(self.details.raw_log)
        self.raw_log_edit.setReadOnly(True)
        self.raw_log_edit.setVisible(False)
        layout.addWidget(self.raw_log_edit, 1)

        # Button Bar
        btn_row = QHBoxLayout()
        self.toggle_log_btn = QPushButton("Show Technical Log [+]")
        self.toggle_log_btn.clicked.connect(self._toggle_raw_log)
        btn_row.addWidget(self.toggle_log_btn)

        copy_btn = QPushButton("Copy Technical Details")
        copy_btn.clicked.connect(self._copy_details)
        btn_row.addWidget(copy_btn)

        btn_row.addStretch(1)

        # Contextual Action Button if available
        if self.details.action_type == "retry":
            action_btn = QPushButton("Retry Download")
            action_btn.setObjectName("primary")
            action_btn.clicked.connect(lambda: self.done(2))  # 2 = Retry requested
            btn_row.addWidget(action_btn)
        elif self.details.action_type == "change_dir":
            action_btn = QPushButton("Change Save Folder")
            action_btn.setObjectName("primary")
            action_btn.clicked.connect(lambda: self.done(3))  # 3 = Change Dir requested
            btn_row.addWidget(action_btn)
        elif self.details.action_type == "auth_setup":
            action_btn = QPushButton("Setup Verification / Auth")
            action_btn.setObjectName("primary")
            action_btn.clicked.connect(lambda: self.done(4))  # 4 = Auth Setup requested
            btn_row.addWidget(action_btn)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)

        layout.addLayout(btn_row)

    def _toggle_raw_log(self):
        show = not self.raw_log_edit.isVisible()
        self.raw_log_edit.setVisible(show)
        self.toggle_log_btn.setText("Hide Technical Log [-]" if show else "Show Technical Log [+]")

    def _copy_details(self):
        diag_text = f"=== GGU_VDOD ERROR DIAGNOSTIC REPORT ===\nTitle: {self.details.title}\nCode: {self.details.code}\nSeverity: {self.details.severity}\nMessage: {self.details.simple_message}\nFix Action: {self.details.recommendation}\n\n--- RAW TECHNICAL LOG ---\n{self.details.raw_log}"
        QApplication.clipboard().setText(diag_text)
        QMessageBox.information(self, "Copied", "Technical diagnostic details copied to clipboard.")


COMMON_SUBTITLE_LANGUAGES = [
    ("en", "English", "Global / Primary"),
    ("es", "Spanish (EspaÃ±ol)", "International"),
    ("fr", "French (FranÃ§ais)", "International"),
    ("de", "German (Deutsch)", "International"),
    ("ja", "Japanese (æ—¥æœ¬èªž)", "Anime / East Asia"),
    ("zh-Hans", "Chinese Simplified (ç®€ä½“ä¸­æ–‡)", "East Asia"),
    ("zh-Hant", "Chinese Traditional (ç¹é«”ä¸­æ–‡)", "East Asia"),
    ("hi", "Hindi (à¤¹à¤¿à¤¨à¥à¤¦à¥€)", "South Asia"),
    ("ru", "Russian (Ð ÑƒÑÑÐºÐ¸Ð¹)", "Eurasia"),
    ("pt", "Portuguese (PortuguÃªs)", "International"),
    ("it", "Italian (Italiano)", "Europe"),
    ("ar", "Arabic (Ø§Ù„Ø¹Ø±Ø¨ÙŠØ©)", "Middle East"),
    ("ko", "Korean (í•œêµ­ì–´)", "East Asia"),
    ("tr", "Turkish (TÃ¼rkÃ§e)", "Eurasia"),
    ("nl", "Dutch (Nederlands)", "Europe"),
    ("pl", "Polish (Polski)", "Europe"),
    ("uk", "Ukrainian (Ð£ÐºÑ€Ð°Ñ—Ð½ÑÑŒÐºÐ°)", "Europe"),
    ("vi", "Vietnamese (Tiáº¿ng Viá»‡t)", "Southeast Asia"),
    ("th", "Thai (à¹„à¸—à¸¢)", "Southeast Asia"),
    ("id", "Indonesian (Bahasa Indonesia)", "Southeast Asia"),
    ("all", "All Available Languages", "Wildcard"),
]


class SubtitleLanguagesDialog(QDialog):
    """Searchable multi-select dialog for choosing subtitle language codes."""

    def __init__(self, current_selection: str = "en.*", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Subtitle Languages")
        self.resize(600, 480)
        self.selected_codes = []
        self._current_input = current_selection

        self._build_ui()
        self._preselect_current()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        hdr = QHBoxLayout()
        hdr.addWidget(QLabel("Filter Language:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Filter (e.g. english, es, ja, hindi)...")
        self.search_input.textChanged.connect(self._filter_table)
        hdr.addWidget(self.search_input, 1)
        layout.addLayout(hdr)

        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Select", "Language Code", "Language Name / Region"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(0, 70)
        self.table.setColumnWidth(1, 140)
        layout.addWidget(self.table, 1)

        btn_row = QHBoxLayout()
        select_all_btn = QPushButton("Select All")
        select_all_btn.clicked.connect(lambda: self._set_all_checks(True))
        deselect_all_btn = QPushButton("Clear All")
        deselect_all_btn.clicked.connect(lambda: self._set_all_checks(False))
        btn_row.addWidget(select_all_btn)
        btn_row.addWidget(deselect_all_btn)
        btn_row.addStretch(1)

        ok_btn = QPushButton("Apply Selection")
        ok_btn.setObjectName("primary")
        ok_btn.clicked.connect(self._accept_selection)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(ok_btn)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

        self._populate_table(COMMON_SUBTITLE_LANGUAGES)

    def _populate_table(self, languages):
        self.table.setRowCount(len(languages))
        for row, (code, name, region) in enumerate(languages):
            chk_item = QTableWidgetItem()
            chk_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            chk_item.setCheckState(Qt.CheckState.Unchecked)
            chk_item.setData(Qt.ItemDataRole.UserRole, code)

            self.table.setItem(row, 0, chk_item)
            self.table.setItem(row, 1, QTableWidgetItem(code))
            self.table.setItem(row, 2, QTableWidgetItem(f"{name} ({region})"))

    def _preselect_current(self):
        curr_tokens = [t.strip().lower() for t in self._current_input.split(",") if t.strip()]
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            code = item.data(Qt.ItemDataRole.UserRole)
            if any(token in code.lower() or code.lower() in token for token in curr_tokens):
                item.setCheckState(Qt.CheckState.Checked)

    def _filter_table(self, query):
        query = query.strip().lower()
        for row in range(self.table.rowCount()):
            code = self.table.item(row, 1).text().lower()
            name = self.table.item(row, 2).text().lower()
            match = not query or query in code or query in name
            self.table.setRowHidden(row, not match)

    def _set_all_checks(self, checked: bool):
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        for row in range(self.table.rowCount()):
            if not self.table.isRowHidden(row):
                self.table.item(row, 0).setCheckState(state)

    def _accept_selection(self):
        selected = []
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item.checkState() == Qt.CheckState.Checked:
                selected.append(item.data(Qt.ItemDataRole.UserRole))
        self.selected_codes = selected
        self.accept()

    def get_selected_string(self) -> str:
        if not self.selected_codes:
            return "en.*"
        return ",".join(self.selected_codes)


class FontPreferencesDialog(QDialog):
    """Preferences dialog to choose UI font family and size."""

    def __init__(self, current_font=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Preferences - UI Font Panel")
        self.resize(480, 260)
        self.font_family = current_font.family() if current_font and current_font.family() else "Segoe UI"
        self.font_size = current_font.pointSize() if current_font and current_font.pointSize() > 0 else 10
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)

        form = QFormLayout()

        self.family_combo = QComboBox()
        self.family_combo.addItems(self._font_choices())
        if self.family_combo.findText(self.font_family) < 0:
            self.family_combo.addItem(self.font_family)
        self.family_combo.setCurrentText(self.font_family)
        form.addRow(QLabel("Font Family:"), self.family_combo)

        self.size_spin = QSpinBox()
        self.size_spin.setRange(8, 18)
        self.size_spin.setValue(max(8, min(18, self.font_size)))
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

    @staticmethod
    def _font_choices():
        """Curated favorites first (including Comic Sans MS), then every font
        installed on the system, alphabetically."""
        preferred = [
            "Segoe UI", "Comic Sans MS", "Arial", "Verdana", "Tahoma",
            "Trebuchet MS", "Georgia", "Times New Roman", "Courier New",
            "Consolas", "Cascadia Mono", "Inter", "Roboto",
            "Segoe UI Variable Display",
        ]
        try:
            installed = set(QFontDatabase.families())
        except Exception:
            installed = set()
        choices = list(preferred)
        choices += sorted(f for f in installed if f not in choices)
        return choices

    def get_font_choice(self):
        return self.family_combo.currentText(), self.size_spin.value()


class ThemePreferencesDialog(QDialog):
    """Edit a safe, persistent Qt color theme without allowing malformed colors."""

    def __init__(self, current_theme=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Preferences - Themes and Colors")
        self.resize(620, 680)
        self.setMinimumSize(520, 500)
        self._draft = normalize_theme(current_theme)
        self._color_inputs = {}
        self._building = False
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        title = QLabel("Themes and colors")
        title.setStyleSheet("font-weight: 700;")
        layout.addWidget(title)

        summary = QLabel(
            "Choose a preset or edit individual colors. Invalid values are rejected, and Reset restores the pitch-black Dark theme."
        )
        summary.setObjectName("muted")
        summary.setWordWrap(True)
        layout.addWidget(summary)

        preset_row = QHBoxLayout()
        preset_row.addWidget(QLabel("Theme:"))
        self.preset_combo = QComboBox()
        self.preset_combo.addItems([*THEME_PRESETS.keys(), "Custom"])
        self.preset_combo.setCurrentText(theme_name(self._draft))
        self.preset_combo.currentTextChanged.connect(self._load_preset)
        preset_row.addWidget(self.preset_combo, 1)
        reset_btn = QPushButton("Reset theme")
        reset_btn.clicked.connect(self._reset_theme)
        preset_row.addWidget(reset_btn)
        layout.addLayout(preset_row)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        form_widget = QWidget()
        form = QFormLayout(form_widget)
        form.setContentsMargins(0, 0, 8, 0)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(8)

        for key, label in THEME_COLOR_FIELDS:
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(8)
            entry = QLineEdit(self._draft[key])
            entry.setMaxLength(7)
            entry.setPlaceholderText("#RRGGBB")
            entry.editingFinished.connect(self._mark_custom)
            choose = QPushButton("Choose")
            choose.clicked.connect(lambda _checked=False, field=key: self._choose_color(field))
            row_layout.addWidget(entry, 1)
            row_layout.addWidget(choose)
            form.addRow(QLabel(f"{label}:"), row)
            self._color_inputs[key] = entry

        scroll.setWidget(form_widget)
        layout.addWidget(scroll, 1)

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        apply_btn = QPushButton("Apply and save")
        apply_btn.setObjectName("primary")
        apply_btn.clicked.connect(self._accept_theme)
        button_row.addWidget(cancel_btn)
        button_row.addWidget(apply_btn)
        layout.addLayout(button_row)

    def _load_preset(self, preset_name):
        if self._building or preset_name not in THEME_PRESETS:
            return
        self._draft = normalize_theme(THEME_PRESETS[preset_name])
        self._set_inputs(self._draft)

    def _set_inputs(self, colors):
        self._building = True
        try:
            for key, _label in THEME_COLOR_FIELDS:
                self._color_inputs[key].setText(colors[key])
        finally:
            self._building = False

    def _mark_custom(self):
        if not self._building:
            self.preset_combo.setCurrentText("Custom")

    def _choose_color(self, key):
        current = self._color_inputs[key].text().strip()
        chosen = QColorDialog.getColor(QColor(current), self, f"Choose {key.replace('_', ' ')}")
        if chosen.isValid():
            self._color_inputs[key].setText(chosen.name().lower())
            self._mark_custom()

    def _reset_theme(self):
        self._draft = normalize_theme(THEME_PRESETS["Dark"])
        self._set_inputs(self._draft)
        self.preset_combo.setCurrentText("Dark")

    def _accept_theme(self):
        colors = {}
        for key, label in THEME_COLOR_FIELDS:
            value = self._color_inputs[key].text().strip()
            if not is_valid_theme_color(value):
                QMessageBox.warning(self, "Invalid color", f"{label} must be a color in the form #RRGGBB.")
                self._color_inputs[key].setFocus()
                return
            colors[key] = value.lower()
        self._draft = normalize_theme(colors)
        self.accept()

    def get_theme_settings(self):
        """Return the selected name and a complete validated theme dictionary."""
        return theme_name(self._draft), dict(self._draft)




