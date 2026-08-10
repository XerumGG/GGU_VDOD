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


ADULT_SITE_DOMAINS = [
    "pornhub.com", "pornhub.org", "xvideos.com", "xnxx.com",
    "redtube.com", "youporn.com", "xhamster.com", "stripchat.com",
    "onlyfans.com", "brazzers.com", "eporner.com", "spankbang.com",
    "tnaflix.com", "tube8.com", "chaturbate.com", "cam4.com",
    "livejasmin.com", "myfreecams.com", "fansly.com", "fetlife.com",
]


def is_adult_or_age_restricted_url(url: str) -> bool:
    """Check if URL points to an adult/18+ age-restricted domain."""
    if not url:
        return False
    lower_url = str(url).lower()
    return any(domain in lower_url for domain in ADULT_SITE_DOMAINS)
