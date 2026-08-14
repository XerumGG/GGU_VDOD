"""PySide6 Local Test Inbox (Mailpit) UI Widget for GGU_VDOD."""

from PySide6.QtCore import Qt, QThread, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QHBoxLayout, QHeaderView, QLabel, QMessageBox, QPlainTextEdit,
    QPushButton, QSplitter, QTableWidget, QTableWidgetItem, QVBoxLayout,
    QWidget,
)

from ...auth.mailpit import MailpitClient, is_staging_domain


class MailpitPollThread(QThread):
    """Background worker to check Mailpit status and messages off the UI loop."""

    poll_completed = Signal(bool, list)

    def __init__(self, client: MailpitClient, parent=None):
        super().__init__(parent)
        self.client = client

    def run(self):
        is_running = self.client.is_server_running()
        messages = []
        if is_running:
            messages = self.client.list_messages()
        self.poll_completed.emit(is_running, messages)


class MailpitTestInboxWidget(QWidget):
    """Built-in Local Test Inbox panel displaying captured Mailpit emails."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.client = MailpitClient()
        self._active_poll_thread = None
        self._current_message_id = None
        self._extracted_links = []
        self._init_ui()

        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self.trigger_poll)
        self._poll_timer.start(5000)

    def shutdown(self):
        if hasattr(self, "_poll_timer"):
            self._poll_timer.stop()
        if self._active_poll_thread and self._active_poll_thread.isRunning():
            self._active_poll_thread.wait(1000)

    def closeEvent(self, event):
        self.shutdown()
        super().closeEvent(event)

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        from ...services.i18n import i18n, t

        # Header Status Row
        header_row = QHBoxLayout()
        self.title_label = QLabel(t("mailpit.title", "📬 Local Test Inbox (Mailpit - Owned Staging Only)"), self)
        self.title_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        header_row.addWidget(self.title_label)
        header_row.addStretch()

        self.status_label = QLabel("Mailpit: Checking...", self)
        self.status_label.setStyleSheet("font-weight: 600; color: #ffa500;")
        header_row.addWidget(self.status_label)
        layout.addLayout(header_row)

        self.sub_label = QLabel(
            t("mailpit.subtitle", "Captures local test verification emails for user-owned staging sites (localhost, *.local, *.test). Never used for external public sites."),
            self,
        )
        self.sub_label.setStyleSheet("color: #888888; font-size: 11px;")
        layout.addWidget(self.sub_label)

        # Main Splitter (Message Table + Email Preview Box)
        splitter = QSplitter(Qt.Orientation.Vertical, self)

        # Message List Table
        self.table = QTableWidget(self)
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels([
            t("mailpit.table_from", "From"),
            t("mailpit.table_to", "To"),
            t("mailpit.table_subject", "Subject"),
            t("mailpit.table_created", "Created"),
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.itemSelectionChanged.connect(self._on_message_selected)
        splitter.addWidget(self.table)

        # Email Detail & Extracted Links Box
        preview_container = QWidget(self)
        prev_layout = QVBoxLayout(preview_container)
        prev_layout.setContentsMargins(0, 8, 0, 0)
        prev_layout.setSpacing(6)

        prev_header = QHBoxLayout()
        self.prev_lbl = QLabel(t("mailpit.email_content", "Email Content & Verification Links:"), self)
        prev_header.addWidget(self.prev_lbl)
        prev_header.addStretch()

        self.open_link_btn = QPushButton(t("mailpit.open_link_btn", "Open Verification Link in Browser"), self)
        self.open_link_btn.setEnabled(False)
        self.open_link_btn.clicked.connect(self._open_selected_verification_link)
        prev_header.addWidget(self.open_link_btn)

        prev_layout.addLayout(prev_header)

        self.preview_box = QPlainTextEdit(self)
        self.preview_box.setReadOnly(True)
        self.preview_box.setStyleSheet("font-family: Consolas, monospace; font-size: 12px; background: #111;")
        prev_layout.addWidget(self.preview_box)

        splitter.addWidget(preview_container)
        layout.addWidget(splitter, 1)

        # Action Toolbar
        toolbar = QHBoxLayout()

        self.refresh_btn = QPushButton(t("mailpit.refresh_btn", "Refresh Inbox"), self)
        self.refresh_btn.clicked.connect(self.trigger_poll)

        self.open_webui_btn = QPushButton(t("mailpit.open_webui_btn", "Open Mailpit Web UI (127.0.0.1:8025)"), self)
        self.open_webui_btn.setToolTip("Open Mailpit web dashboard in your default web browser.")
        self.open_webui_btn.clicked.connect(self._open_webui)

        self.clear_btn = QPushButton(t("mailpit.clear_btn", "Clear Test Mailbox"), self)
        self.clear_btn.setStyleSheet("background-color: #8b0000; color: white;")
        self.clear_btn.clicked.connect(self._clear_mailbox)

        toolbar.addWidget(self.refresh_btn)
        toolbar.addWidget(self.open_webui_btn)
        toolbar.addStretch()
        toolbar.addWidget(self.clear_btn)

        layout.addLayout(toolbar)
        i18n.language_changed.connect(self._retranslate_ui)

    def _retranslate_ui(self):
        from ...services.i18n import t
        self.title_label.setText(t("mailpit.title", "📬 Local Test Inbox (Mailpit - Owned Staging Only)"))
        self.sub_label.setText(t("mailpit.subtitle", "Captures local test verification emails for user-owned staging sites (localhost, *.local, *.test). Never used for external public sites."))
        self.table.setHorizontalHeaderLabels([
            t("mailpit.table_from", "From"),
            t("mailpit.table_to", "To"),
            t("mailpit.table_subject", "Subject"),
            t("mailpit.table_created", "Created"),
        ])
        self.prev_lbl.setText(t("mailpit.email_content", "Email Content & Verification Links:"))
        self.open_link_btn.setText(t("mailpit.open_link_btn", "Open Verification Link in Browser"))
        self.refresh_btn.setText(t("mailpit.refresh_btn", "Refresh Inbox"))
        self.open_webui_btn.setText(t("mailpit.open_webui_btn", "Open Mailpit Web UI (127.0.0.1:8025)"))
        self.clear_btn.setText(t("mailpit.clear_btn", "Clear Test Mailbox"))

    def _open_webui(self):
        import webbrowser
        target_url = getattr(self.client, "base_url", "http://127.0.0.1:8025") or "http://127.0.0.1:8025"
        try:
            if not webbrowser.open(target_url):
                QDesktopServices.openUrl(QUrl(target_url))
        except Exception:
            QDesktopServices.openUrl(QUrl(target_url))

    def trigger_poll(self):
        """Poll Mailpit asynchronously off the UI thread."""
        if not self.isVisible():
            return
        if self._active_poll_thread and self._active_poll_thread.isRunning():
            return
        self._active_poll_thread = MailpitPollThread(self.client, self)
        self._active_poll_thread.poll_completed.connect(self._on_poll_completed)
        self._active_poll_thread.start()

    def _on_poll_completed(self, is_running: bool, messages: list):
        if not is_running:
            self.status_label.setText("Mailpit: Offline 🔴 (Run Mailpit on localhost:8025)")
            self.status_label.setStyleSheet("font-weight: 600; color: #ff4444;")
            self.table.setRowCount(0)
            return

        self.status_label.setText("Mailpit: Online 🟢 (localhost:8025)")
        self.status_label.setStyleSheet("font-weight: 600; color: #00cc66;")

        self.table.setRowCount(0)
        for row, msg in enumerate(messages):
            self.table.insertRow(row)

            msg_id = msg.get("ID", "")
            from_str = msg.get("From", {}).get("Address", "") or "Unknown"
            to_list = msg.get("To", [])
            to_str = to_list[0].get("Address", "") if to_list else "Unknown"
            subject = msg.get("Subject", "(No Subject)")
            created = msg.get("Created", "")[:19].replace("T", " ")

            item_from = QTableWidgetItem(from_str)
            item_from.setData(Qt.ItemDataRole.UserRole, msg_id)

            self.table.setItem(row, 0, item_from)
            self.table.setItem(row, 1, QTableWidgetItem(to_str))
            self.table.setItem(row, 2, QTableWidgetItem(subject))
            self.table.setItem(row, 3, QTableWidgetItem(created))

    def _on_message_selected(self):
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            self.preview_box.clear()
            self.open_link_btn.setEnabled(False)
            self._current_message_id = None
            self._extracted_links = []
            return

        row = selected_rows[0].row()
        item = self.table.item(row, 0)
        if not item:
            return

        msg_id = item.data(Qt.ItemDataRole.UserRole)
        if not msg_id:
            return

        self._current_message_id = msg_id
        detail = self.client.get_message(msg_id)
        links = self.client.extract_verification_links(msg_id)
        self._extracted_links = links

        if detail:
            body = detail.get("Text") or detail.get("HTML") or "(Empty Email Body)"
            preview_text = f"Subject: {detail.get('Subject')}\nFrom: {detail.get('From', {}).get('Address')}\nDate: {detail.get('Created')}\n"
            preview_text += f"\n--- Verification Links ({len(links)}) ---\n"
            for link in links:
                preview_text += f"🔗 {link}\n"
            preview_text += f"\n--- Email Body ---\n{body}"
            self.preview_box.setPlainText(preview_text)
            self.open_link_btn.setEnabled(bool(links))

    def _open_selected_verification_link(self):
        if self._extracted_links:
            target_link = self._extracted_links[0]
            QDesktopServices.openUrl(QUrl(target_link))

    def _clear_mailbox(self):
        from ...services.i18n import t

        res = QMessageBox.question(
            self,
            t("mailpit.clear_title", "Clear Mailpit Mailbox"),
            t("mailpit.clear_confirm", "Are you sure you want to delete all captured messages in local Mailpit?"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if res == QMessageBox.StandardButton.Yes:
            self.client.delete_all_messages()
            self.trigger_poll()
            self.preview_box.clear()
            self.open_link_btn.setEnabled(False)
