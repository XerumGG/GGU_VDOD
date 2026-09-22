import time
from PySide6.QtCore import Qt, Signal, QUrl
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QProgressBar, QFrame
)
from PySide6.QtGui import QDesktopServices

class UpdateBanner(QFrame):
    """
    An inline banner that sits at the top or bottom of the main content area,
    showing update availability, progress, speed, and CTA buttons.
    """
    # Signals for user actions
    download_requested = Signal()
    install_requested = Signal(str)
    cancel_requested = Signal()
    dismiss_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("updateBanner")
        self.setStyleSheet("""
            QFrame#updateBanner {
                background-color: #2a2a35;
                border: 1px solid #3a3a4a;
                border-radius: 6px;
            }
            QLabel { color: #f0f0f0; font-size: 13px; }
            QLabel#title { font-weight: bold; font-size: 14px; }
            QLabel#status { color: #a0a0b0; }
        """)
        
        # State
        self.release_info = None
        self.installer_path = None
        self._last_progress_time = 0
        self._current_state = "hidden"
        
        self.hide()
        self._build_ui()
        
    def _build_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(16, 12, 16, 12)
        main_layout.setSpacing(16)
        
        # Left side: Icon
        icon_label = QLabel("🔄")
        icon_label.setStyleSheet("font-size: 24px;")
        main_layout.addWidget(icon_label, 0, Qt.AlignmentFlag.AlignTop)
        
        # Middle: Text and Progress
        mid_layout = QVBoxLayout()
        mid_layout.setSpacing(6)
        
        self.title_label = QLabel("Update available")
        self.title_label.setObjectName("title")
        mid_layout.addWidget(self.title_label)
        
        self.status_label = QLabel("Waiting...")
        self.status_label.setObjectName("status")
        mid_layout.addWidget(self.status_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.hide()
        mid_layout.addWidget(self.progress_bar)
        
        main_layout.addLayout(mid_layout, 1)
        
        # Right side: Buttons
        btn_layout = QVBoxLayout()
        btn_layout.setSpacing(8)
        
        self.primary_btn = QPushButton("Download Now")
        self.primary_btn.setObjectName("primary")
        self.primary_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.primary_btn.clicked.connect(self._on_primary_clicked)
        btn_layout.addWidget(self.primary_btn)
        
        self.secondary_btn = QPushButton("Dismiss")
        self.secondary_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.secondary_btn.clicked.connect(self._on_secondary_clicked)
        btn_layout.addWidget(self.secondary_btn)
        
        self.release_link_btn = QPushButton("Releases Page")
        self.release_link_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.release_link_btn.setFlat(True)
        self.release_link_btn.setStyleSheet("color: #64b5f6; text-decoration: underline;")
        self.release_link_btn.clicked.connect(self._open_releases)
        btn_layout.addWidget(self.release_link_btn)
        
        main_layout.addLayout(btn_layout, 0)
        
    def _open_releases(self):
        url = "https://github.com/XerumGG/GGU_VDOD/releases/latest"
        if self.release_info and self.release_info.get("html_url"):
            url = self.release_info["html_url"]
        QDesktopServices.openUrl(QUrl(url))
        
    def _on_primary_clicked(self):
        if self._current_state == "available":
            self.download_requested.emit()
        elif self._current_state == "downloading":
            self.cancel_requested.emit()
        elif self._current_state == "ready":
            self.install_requested.emit(self.installer_path)
        elif self._current_state == "error":
            self.download_requested.emit()
            
    def _on_secondary_clicked(self):
        if self._current_state == "downloading":
            self.cancel_requested.emit()
        else:
            self.dismiss_requested.emit()
            self.hide()
            self._current_state = "hidden"
            
    def show_available(self, release):
        self.release_info = release
        self._current_state = "available"
        tag = release.get("tag_name", "unknown")
        self.title_label.setText(f"Update available: {tag}")
        self.status_label.setText("A newer version of GGU_VDOD is available. Download and install it now?")
        self.status_label.show()
        self.progress_bar.hide()
        
        self.primary_btn.setText("Download Now")
        self.primary_btn.show()
        self.secondary_btn.setText("Dismiss")
        self.secondary_btn.show()
        
        self.show()
        
    def show_downloading(self):
        self._current_state = "downloading"
        tag = self.release_info.get("tag_name", "unknown") if self.release_info else ""
        self.title_label.setText(f"Downloading update {tag}...")
        self.status_label.setText("Connecting...")
        self.progress_bar.setValue(0)
        self.progress_bar.show()
        
        self.primary_btn.setText("Cancel")
        self.secondary_btn.hide()
        
        self.show()
        
    def update_progress(self, done, total, speed_bps):
        now = time.monotonic()
        if now - self._last_progress_time < 0.1 and done < total:
            return
        self._last_progress_time = now
        
        pct = int(done * 100 / total) if total else 0
        self.progress_bar.setValue(pct)
        
        done_mb = done / (1024 * 1024)
        total_mb = total / (1024 * 1024) if total else 0
        speed_mb = speed_bps / (1024 * 1024)
        
        eta_str = ""
        if speed_bps > 0 and total > done:
            eta_s = int((total - done) / speed_bps)
            eta_str = f" · ~{eta_s}s left"
            
        if total > 0:
            self.status_label.setText(f"{pct}% · {done_mb:.1f} / {total_mb:.1f} MB · {speed_mb:.1f} MB/s{eta_str}")
        else:
            self.status_label.setText(f"{done_mb:.1f} MB downloaded · {speed_mb:.1f} MB/s")
            
    def show_ready(self, installer_path):
        self._current_state = "ready"
        self.installer_path = installer_path
        self.title_label.setText("Ready to Install")
        self.status_label.setText("Download complete. The app will close while the setup runs.")
        self.progress_bar.hide()
        
        self.primary_btn.setText("Install & Restart")
        self.secondary_btn.setText("Dismiss")
        self.secondary_btn.show()
        self.show()
        
    def show_error(self, error_msg):
        self._current_state = "error"
        self.title_label.setText("Update Failed")
        self.status_label.setText(f"Error: {error_msg}")
        self.progress_bar.hide()
        
        self.primary_btn.setText("Retry")
        self.secondary_btn.setText("Dismiss")
        self.secondary_btn.show()
        self.show()
