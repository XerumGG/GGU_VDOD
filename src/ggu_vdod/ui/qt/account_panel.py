"""PySide6 Account & Session Management UI Panel for GGU_VDOD."""

import time
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QHBoxLayout, QHeaderView, QLabel, QMessageBox, QPushButton, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget, QInputDialog, QLineEdit, QDialog,
    QFormLayout, QComboBox,
)

from ...auth.manager import AuthManager
from ...auth.sanitizer import sanitize_log_text


class AddCredentialDialog(QDialog):
    """Dialog to manually register domain credentials."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Domain Credential")
        self.setMinimumWidth(400)

        layout = QFormLayout(self)

        self.domain_input = QLineEdit(self)
        self.domain_input.setPlaceholderText("e.g. staging.local or example.com")

        self.account_input = QLineEdit(self)
        self.account_input.setPlaceholderText("Username or email")

        self.secret_input = QLineEdit(self)
        self.secret_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.secret_input.setPlaceholderText("Password or Auth Token")

        self.mode_combo = QComboBox(self)
        self.mode_combo.addItems(["credentials", "local_test", "browser_cookie", "imported_cookies"])

        layout.addRow("Domain / URL:", self.domain_input)
        layout.addRow("Account Label:", self.account_input)
        layout.addRow("Secret / Token:", self.secret_input)
        layout.addRow("Auth Mode:", self.mode_combo)

        btn_box = QHBoxLayout()
        self.save_btn = QPushButton("Save Session", self)
        self.cancel_btn = QPushButton("Cancel", self)
        self.save_btn.clicked.connect(self.accept)
        self.cancel_btn.clicked.connect(self.reject)
        btn_box.addWidget(self.save_btn)
        btn_box.addWidget(self.cancel_btn)

        layout.addRow(btn_box)

    def get_data(self) -> tuple[str, str, str, str]:
        return (
            self.domain_input.text().strip(),
            self.account_input.text().strip(),
            self.secret_input.text().strip(),
            self.mode_combo.currentText(),
        )


class AccountSessionWidget(QWidget):
    """Account and active domain session management panel."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self.refresh_sessions)
        self._refresh_timer.start(5000)

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        title_label = QLabel("🔑 Active Domain Sessions & Security Controls", self)
        title_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(title_label)

        sub_label = QLabel("Credentials are encrypted with Windows DPAPI / Windows Credential Manager. Plaintext passwords are never stored.", self)
        sub_label.setStyleSheet("color: #888888; font-size: 11px;")
        layout.addWidget(sub_label)

        # Table
        self.table = QTableWidget(self)
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Domain", "Account Label", "Auth Mode", "Expires In", "Status"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self.table)

        # Action Toolbar
        toolbar = QHBoxLayout()

        self.add_btn = QPushButton("Add Session...", self)
        self.add_btn.clicked.connect(self._add_session)

        self.forget_btn = QPushButton("Forget Selected", self)
        self.forget_btn.clicked.connect(self._forget_selected)

        self.purge_btn = QPushButton("Purge Expired", self)
        self.purge_btn.clicked.connect(self._purge_expired)

        self.clear_btn = QPushButton("Clear All Sessions", self)
        self.clear_btn.setStyleSheet("background-color: #8b0000; color: white;")
        self.clear_btn.clicked.connect(self._clear_all)

        toolbar.addWidget(self.add_btn)
        toolbar.addWidget(self.forget_btn)
        toolbar.addWidget(self.purge_btn)
        toolbar.addStretch()
        toolbar.addWidget(self.clear_btn)

        layout.addLayout(toolbar)
        self.refresh_sessions()

    def refresh_sessions(self, force: bool = False):
        """Reload active sessions into table widget."""
        if not force and not self.isVisible():
            return
        sessions = AuthManager.purge_expired_sessions()
        active_list = list_active_sessions() if hasattr(AuthManager, "list_active_sessions") else []
        if not active_list:
            from ...auth.store import list_active_sessions as store_list
            active_list = store_list()

        self.table.setRowCount(0)
        now = int(time.time())

        for row, entry in enumerate(active_list):
            self.table.insertRow(row)

            domain_item = QTableWidgetItem(entry.get("domain", ""))
            account_item = QTableWidgetItem(entry.get("account_label", "Anonymous"))
            mode_item = QTableWidgetItem(entry.get("auth_mode", "credentials"))

            expires_at = entry.get("expires_at", 0)
            if expires_at:
                ttl_secs = max(0, expires_at - now)
                days = ttl_secs // 86400
                hours = (ttl_secs % 86400) // 3600
                ttl_str = f"{days}d {hours}h"
            else:
                ttl_str = "Never"

            ttl_item = QTableWidgetItem(ttl_str)
            status_str = "Expired" if entry.get("is_expired") else "Active 🟢"
            status_item = QTableWidgetItem(status_str)

            self.table.setItem(row, 0, domain_item)
            self.table.setItem(row, 1, account_item)
            self.table.setItem(row, 2, mode_item)
            self.table.setItem(row, 3, ttl_item)
            self.table.setItem(row, 4, status_item)

    def _add_session(self):
        dlg = AddCredentialDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            domain, account, secret, mode = dlg.get_data()
            if domain:
                AuthManager.authenticate_domain(domain, account, secret, auth_mode=mode)
                self.refresh_sessions()

    def _forget_selected(self):
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.information(self, "No Selection", "Please select a domain session to forget.")
            return

        for index in selected_rows:
            domain = self.table.item(index.row(), 0).text()
            if domain:
                AuthManager.forget_session(domain)

        self.refresh_sessions()

    def _purge_expired(self):
        count = AuthManager.purge_expired_sessions()
        QMessageBox.information(self, "Purge Complete", f"Purged {count} expired session(s).")
        self.refresh_sessions()

    def _clear_all(self):
        res = QMessageBox.question(
            self,
            "Clear All Sessions",
            "Are you sure you want to delete all stored domain sessions and credentials?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if res == QMessageBox.StandardButton.Yes:
            count = AuthManager.clear_all()
            QMessageBox.information(self, "Sessions Cleared", f"Cleared {count} stored session(s).")
            self.refresh_sessions()
