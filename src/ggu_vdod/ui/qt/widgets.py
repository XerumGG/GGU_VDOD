"""Reusable PySide6 widgets that are independent of downloader logic."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QProgressBar

from ...core.version import DEVELOPMENT_BUILD_LABEL


class TransferStatusBar(QFrame):
    """qBittorrent-style status summary used by the Qt download screen."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("panel")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(14)

        self.status_label = QLabel("Ready")
        self.download_rate_label = QLabel("↓ Download: 0 B/s")
        self.upload_rate_label = QLabel("↑ Upload: 0 B/s")
        self.transferred_label = QLabel("Transferred: 0 B")
        self.eta_label = QLabel("ETA: —")
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setMinimumWidth(200)
        self.version_label = QLabel(DEVELOPMENT_BUILD_LABEL)
        self.version_label.setStyleSheet("color: #e5484d; font-weight: 700; font-size: 13px; padding-left: 10px;")
        self.version_label.setToolTip(f"GGU_VDOD Build Version: {DEVELOPMENT_BUILD_LABEL}")

        for widget in (
            self.status_label,
            self.download_rate_label,
            self.upload_rate_label,
            self.transferred_label,
            self.eta_label,
        ):
            layout.addWidget(widget)
        layout.addWidget(self.progress, 1)
        layout.addWidget(self.version_label, 0, Qt.AlignmentFlag.AlignRight)
        layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

    def set_transfer_state(self, status, download_rate="0 B/s", upload_rate="0 B/s", transferred="0 B", eta="—", progress=0):
        self.status_label.setText(f"Status: {status}")
        self.download_rate_label.setText(f"↓ Download: {download_rate}")
        self.upload_rate_label.setText(f"↑ Upload: {upload_rate}")
        self.transferred_label.setText(f"Transferred: {transferred}")
        self.eta_label.setText(f"ETA: {eta}")
        self.progress.setValue(max(0, min(100, int(progress))))
