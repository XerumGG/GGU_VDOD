"""Mailpit REST API client, local staging domain allowlist validator, and built-in embedded test mail server with Web UI for GGU_VDOD."""

from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import re
import socketserver
import threading
import time
import urllib.parse
import urllib.request

DEFAULT_MAILPIT_URL = "http://127.0.0.1:8025"
DEFAULT_TEST_DOMAIN_ALLOWLIST = ["localhost", "127.0.0.1", "*.local", "*.test", "*.staging", "*.dev"]

# Regex matcher for verification/confirmation links inside captured emails
VERIFICATION_LINK_REGEX = re.compile(
    r"https?://[^\s\"'>]+\b(?:verify|confirm|activate|register|token|login|auth|session)[^\s\"'>]*",
    re.IGNORECASE,
)

MAILPIT_HTML_WEB_UI = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Mailpit - Local Test Inbox (GGU_VDOD)</title>
    <style>
        body { background-color: #0d0d0d; color: #e2e2e2; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 0; padding: 24px; }
        .header { display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid #2a2a2a; padding-bottom: 16px; margin-bottom: 20px; }
        .title { font-size: 20px; font-weight: 700; color: #ffffff; display: flex; align-items: center; gap: 10px; }
        .badge { background: #e5484d; color: #fff; padding: 4px 10px; border-radius: 12px; font-size: 12px; font-weight: 600; }
        .status { color: #57c26a; font-weight: 600; font-size: 14px; }
        table { width: 100%; border-collapse: collapse; margin-top: 10px; background: #141414; border-radius: 8px; overflow: hidden; border: 1px solid #282828; }
        th, td { text-align: left; padding: 12px 16px; border-bottom: 1px solid #222222; }
        th { background: #1a1a1a; color: #888888; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; }
        tr:hover { background: #1f1f1f; }
        .verify-btn { background: #e5484d; color: white; text-decoration: none; padding: 6px 14px; border-radius: 4px; font-weight: 600; font-size: 12px; display: inline-block; }
        .verify-btn:hover { background: #c53f43; }
        .btn-clear { background: #222; color: #ff6b6b; border: 1px solid #444; padding: 8px 16px; border-radius: 6px; cursor: pointer; font-weight: 600; }
        .btn-clear:hover { background: #333; }
        .empty-msg { text-align: center; padding: 40px; color: #666666; font-style: italic; }
    </style>
</head>
<body>
    <div class="header">
        <div class="title">Mailpit Web Inbox <span class="badge">GGU_VDOD Local Staging</span></div>
        <div style="display:flex; gap:12px; align-items:center;">
            <span class="status">Local Capture Running (127.0.0.1:8025)</span>
            <button class="btn-clear" onclick="clearMailbox()">Clear Mailbox</button>
        </div>
    </div>
    <p style="color: #888; font-size: 13px;">Capturing local test emails & account verification tokens for staging sites (localhost, 127.0.0.1, *.local, *.test).</p>
    <div id="mailbox-container">Loading captured messages...</div>

    <script>
        async function loadMessages() {
            try {
                const res = await fetch('/api/v1/messages');
                const data = await res.json();
                const container = document.getElementById('mailbox-container');
                if (!data.messages || data.messages.length === 0) {
                    container.innerHTML = '<table><tr><th>From</th><th>To</th><th>Subject</th><th>Action / Verification</th></tr><tr><td colspan="4" class="empty-msg">No captured messages in mailbox. Send a local test verification email to see it here.</td></tr></table>';
                    return;
                }
                let html = '<table><tr><th>From</th><th>To</th><th>Subject</th><th>Date</th><th>Action / Verification</th></tr>';
                const esc = (s) => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
                for (const msg of data.messages) {
                    const detailRes = await fetch('/api/v1/message/' + encodeURIComponent(msg.ID));
                    const detail = await detailRes.json();
                    const body = (detail.Text || detail.HTML || '');
                    const linkMatch = body.match(/https?:\\/\\/[^\\s"'<>]+\\b(?:verify|confirm|activate|register|token|login|auth|session)[^\\s"'<>]*/i);
                    let actionHtml = '-';
                    if (linkMatch) {
                        const safeLink = esc(linkMatch[0]);
                        actionHtml = `<a class="verify-btn" href="${safeLink}" target="_blank" rel="noopener noreferrer">Verify Session</a>`;
                    }
                    html += `<tr><td>${esc(msg.From.Address)}</td><td>${esc(msg.To[0].Address)}</td><td><strong>${esc(msg.Subject)}</strong></td><td>${esc(msg.Created)}</td><td>${actionHtml}</td></tr>`;
                }
                html += '</table>';
                container.innerHTML = html;
            } catch (err) {
                document.getElementById('mailbox-container').innerHTML = '<div style="color:red; padding:20px;">Error connecting to local Mailpit server.</div>';
            }
        }
        async function clearMailbox() {
            if (confirm("Clear all captured messages?")) {
                await fetch('/api/v1/messages', { method: 'DELETE' });
                loadMessages();
            }
        }
        loadMessages();
        setInterval(loadMessages, 3000);
    </script>
</body>
</html>
"""


def is_staging_domain(domain: str, allowlist: list[str] = None) -> bool:
    """Check if domain is explicitly allowed for local Mailpit test automation."""
    if not domain:
        return False
    clean_domain = domain.strip().lower()
    patterns = allowlist or DEFAULT_TEST_DOMAIN_ALLOWLIST

    import fnmatch

    for pattern in patterns:
        p = pattern.strip().lower()
        if fnmatch.fnmatch(clean_domain, p) or clean_domain == p:
            return True
    return False


class _EmbeddedMailpitHandler(BaseHTTPRequestHandler):
    """HTTP handler serving Mailpit REST API (/api/v1/...) and Web UI Dashboard (/ index.html)."""

    captured_messages = []

    def log_message(self, format, *args):
        pass  # Silent server logging

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path in ("/", "/index.html"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(MAILPIT_HTML_WEB_UI.encode("utf-8"))
        elif path == "/api/v1/info":
            self._send_json(200, {
                "v": "v1.1.0-embedded",
                "messages": len(self.captured_messages),
                "unread": len(self.captured_messages),
                "tags": ["GGU_VDOD"],
            })
        elif path == "/api/v1/messages":
            msg_list = []
            for msg in reversed(self.captured_messages):
                msg_list.append({
                    "ID": msg["ID"],
                    "From": {"Address": msg.get("From", "test@local")},
                    "To": [{"Address": msg.get("To", "user@local")}],
                    "Subject": msg.get("Subject", "Local Test Verification"),
                    "Created": msg.get("Created", time.strftime("%Y-%m-%dT%H:%M:%SZ")),
                    "Snippet": msg.get("Snippet", ""),
                })
            self._send_json(200, {"messages": msg_list, "total": len(msg_list)})
        elif path.startswith("/api/v1/message/"):
            msg_id = path.split("/")[-1]
            found = next((m for m in self.captured_messages if m["ID"] == msg_id), None)
            if found:
                self._send_json(200, found)
            else:
                self._send_json(404, {"error": "Message not found"})
        else:
            self._send_json(404, {"error": "Not Found"})

    def do_DELETE(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        if path == "/api/v1/messages":
            self.captured_messages.clear()
            self._send_json(200, {"status": "ok"})
        elif path.startswith("/api/v1/message/"):
            msg_id = path.split("/")[-1]
            self.captured_messages[:] = [m for m in self.captured_messages if m["ID"] != msg_id]
            self._send_json(200, {"status": "ok"})
        else:
            self._send_json(404, {"error": "Not Found"})

    def _send_json(self, status_code, data):
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "http://127.0.0.1:8025")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))


class EmbeddedMailpitServer:
    """Built-in local test mail server running on 127.0.0.1:8025 if external Mailpit is missing."""

    _server_thread = None
    _httpd = None

    @classmethod
    def start_if_needed(cls, port=8025):
        if cls._httpd is not None:
            return True
        try:
            cls._httpd = HTTPServer(("127.0.0.1", port), _EmbeddedMailpitHandler)
            cls._server_thread = threading.Thread(target=cls._httpd.serve_forever, daemon=True)
            cls._server_thread.start()
            return True
        except Exception:
            cls._httpd = None
            return False

    @classmethod
    def add_sample_test_message(cls, subject="Local Staging Account Verification", from_addr="auth@staging.local", to_addr="test@local", body="Welcome! Click https://staging.local/verify?token=ggu_test_token_123 to activate your session."):
        import uuid
        msg = {
            "ID": str(uuid.uuid4())[:8],
            "From": from_addr,
            "To": to_addr,
            "Subject": subject,
            "Created": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "Text": body,
            "HTML": f"<p>{body}</p>",
            "Snippet": body[:60],
        }
        _EmbeddedMailpitHandler.captured_messages.append(msg)


class MailpitClient:
    """HTTP REST API client for local Mailpit capture server."""

    def __init__(self, base_url: str = DEFAULT_MAILPIT_URL):
        self.base_url = base_url.rstrip("/")

    def is_server_running(self) -> bool:
        """Check if Mailpit server is running on 127.0.0.1 or localhost (starts embedded fallback if offline)."""
        for candidate in (self.base_url, "http://127.0.0.1:8025", "http://localhost:8025"):
            if not candidate:
                continue
            try:
                url = candidate.rstrip("/")
                req = urllib.request.Request(f"{url}/api/v1/info", headers={"User-Agent": "GGU_VDOD/0.1"})
                with urllib.request.urlopen(req, timeout=1.2) as resp:
                    if resp.status == 200:
                        self.base_url = url
                        return True
            except Exception:
                continue

        # If external server is offline, auto-start embedded Mailpit server fallback
        if EmbeddedMailpitServer.start_if_needed(8025):
            self.base_url = "http://127.0.0.1:8025"
            return True

        return False

    def list_messages(self, limit: int = 50) -> list[dict]:
        """Fetch summary of captured messages from Mailpit."""
        try:
            req = urllib.request.Request(f"{self.base_url}/api/v1/messages?limit={limit}", headers={"User-Agent": "GGU_VDOD/0.1"})
            with urllib.request.urlopen(req, timeout=3) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    return data.get("messages", [])
        except Exception:
            pass
        return []

    def get_message(self, message_id: str) -> dict | None:
        """Fetch detailed content for a captured message."""
        try:
            req = urllib.request.Request(f"{self.base_url}/api/v1/message/{message_id}", headers={"User-Agent": "GGU_VDOD/0.1"})
            with urllib.request.urlopen(req, timeout=3) as resp:
                if resp.status == 200:
                    return json.loads(resp.read().decode("utf-8"))
        except Exception:
            pass
        return None

    def extract_verification_links(self, message_id: str) -> list[str]:
        """Extract verification/confirmation URLs from a captured email."""
        msg = self.get_message(message_id)
        if not msg:
            return []

        text_content = msg.get("Text", "") or ""
        html_content = msg.get("HTML", "") or ""
        combined = f"{text_content}\n{html_content}"

        matches = VERIFICATION_LINK_REGEX.findall(combined)
        unique_links = list(dict.fromkeys(matches))
        return unique_links

    def delete_message(self, message_id: str) -> bool:
        """Delete a message from Mailpit inbox."""
        try:
            req = urllib.request.Request(f"{self.base_url}/api/v1/message/{message_id}", method="DELETE", headers={"User-Agent": "GGU_VDOD/0.1"})
            with urllib.request.urlopen(req, timeout=3) as resp:
                return resp.status in (200, 204)
        except Exception:
            return False

    def delete_all_messages(self) -> bool:
        """Clear all messages from Mailpit inbox."""
        try:
            req = urllib.request.Request(f"{self.base_url}/api/v1/messages", method="DELETE", headers={"User-Agent": "GGU_VDOD/0.1"})
            with urllib.request.urlopen(req, timeout=3) as resp:
                return resp.status in (200, 204)
        except Exception:
            return False
