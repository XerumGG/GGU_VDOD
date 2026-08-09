"""Comprehensive log output and header sanitizer for GGU_VDOD."""

import re

SENSITIVE_PATTERNS = [
    (r"(?i)(password|pass|secret|token|api_key|access_token|auth_token|sig|signature|key)=([^\s&]+)", r"\1=***REDACTED***"),
    (r"(?i)(\"password\"|\"secret\"|\"token\"|\"access_token\"|\"api_key\"):\s*\"[^\"]+\"", r'\1: "***REDACTED***"'),
    (r"(?i)bearer\s+[a-zA-Z0-9_\-\.]{10,}", r"Bearer ***REDACTED***"),
    (r"(?i)cookie:\s*[^\r\n]+", r"Cookie: ***REDACTED***"),
    (r"(?i)authorization:\s*[^\r\n]+", r"Authorization: ***REDACTED***"),
]


def sanitize_log_text(text: str) -> str:
    """Sanitize log text by masking sensitive credentials, tokens, and cookie strings."""
    if not text:
        return ""
    sanitized = text
    for pattern, replacement in SENSITIVE_PATTERNS:
        sanitized = re.sub(pattern, replacement, sanitized)
    return sanitized


def sanitize_headers(headers: dict) -> dict:
    """Return a copy of HTTP headers dictionary with sensitive headers redacted."""
    if not headers or not isinstance(headers, dict):
        return {}
    clean_headers = {}
    for k, v in headers.items():
        key_lower = str(k).lower()
        if key_lower in {"authorization", "cookie", "proxy-authorization", "x-auth-token", "x-api-key"}:
            clean_headers[k] = "***REDACTED***"
        else:
            clean_headers[k] = sanitize_log_text(str(v))
    return clean_headers
