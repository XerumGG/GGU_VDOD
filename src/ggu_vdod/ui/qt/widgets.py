"""Reusable PySide6 widgets that are independent of downloader logic."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QProgressBar

from ...core.version import DEVELOPMENT_BUILD_LABEL
from ...services.i18n import i18n, t


class TransferStatusBar(QFrame):
    """qBittorrent-style status summary used by the Qt download screen."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("panel")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(14)

        self._last_status = "Ready"
        self._last_dl = "0 B/s"
        self._last_ul = "0 B/s"
        self._last_transferred = "0 B"
        self._last_eta = "—"

        self.status_label = QLabel(t("home.status_idle", "Ready"))
        self.download_rate_label = QLabel(f"↓ {t('status.download', 'Download')}: 0 B/s")
        self.upload_rate_label = QLabel(f"↑ {t('status.upload', 'Upload')}: 0 B/s")
        self.transferred_label = QLabel(f"{t('status.transferred', 'Transferred')}: 0 B")
        self.eta_label = QLabel(f"{t('status.eta', 'ETA')}: —")
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setMinimumWidth(200)
        self.version_label = QLabel(DEVELOPMENT_BUILD_LABEL)
        self.version_label.setObjectName("version")
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

        i18n.language_changed.connect(self._retranslate_ui)

    def set_transfer_state(self, status, download_rate="0 B/s", upload_rate="0 B/s", transferred="0 B", eta="—", progress=0):
        self._last_status = status
        self._last_dl = download_rate
        self._last_ul = upload_rate
        self._last_transferred = transferred
        self._last_eta = eta
        self._update_text()
        self.progress.setValue(max(0, min(100, int(progress))))

    def _update_text(self):
        st = t("home.status_idle", "Ready") if self._last_status == "Ready" else self._last_status
        self.status_label.setText(st)
        self.download_rate_label.setText(f"↓ {t('status.download', 'Download')}: {self._last_dl}")
        self.upload_rate_label.setText(f"↑ {t('status.upload', 'Upload')}: {self._last_ul}")
        self.transferred_label.setText(f"{t('status.transferred', 'Transferred')}: {self._last_transferred}")
        self.eta_label.setText(f"{t('status.eta', 'ETA')}: {self._last_eta}")
        self.version_label.setText(DEVELOPMENT_BUILD_LABEL)

    def _retranslate_ui(self):
        self._update_text()
