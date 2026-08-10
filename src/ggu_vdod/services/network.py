"""Connectivity checks and user-facing download error explanations."""

import socket

from ..core.constants import CONNECTIVITY_ENDPOINTS


def is_internet_up(timeout=3):
    for host, port in CONNECTIVITY_ENDPOINTS:
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True
        except OSError:
            continue
    return False


class ConnectionLostError(Exception):
    """Raised when the network drops during a download."""


CONNECTION_ERROR_HINTS = (
    "urlopen error", "timed out", "connection reset", "connection aborted",
    "network is unreachable", "temporary failure in name resolution",
    "failed to establish a new connection", "remote end closed connection",
    "getaddrinfo failed", "10054", "10060", "10061",
)


def looks_like_connection_error(error):
    return any(hint in str(error).lower() for hint in CONNECTION_ERROR_HINTS)


def explain_download_error(error):
    """Turn common extractor failures into actionable messages."""
    text = str(error)
    lower = text.lower()
    if "drm" in lower or "encrypted" in lower:
        return "DRM-protected content cannot be downloaded by this app."
    if "members-only" in lower or "member only" in lower or "private video" in lower:
        return "This content requires account access. Select browser cookies or a cookies.txt file."
    if "sign in" in lower or "login" in lower or "age-restricted" in lower:
        return "This content requires sign-in or age verification. Select valid browser cookies or a cookies.txt file."
    if "not available in your country" in lower or "geo" in lower or "region" in lower:
        return "This content is region-restricted. Configure an appropriate proxy if you are authorized to access it."
    if "confirm you're not a bot" in lower or "captcha" in lower or "robot" in lower:
        return "The site requested bot verification. Try again later with valid browser cookies and an updated yt-dlp."
    if "live" in lower and "not currently available" in lower:
        return "This live stream is not currently available to the extractor."
    return text


def looks_like_cookie_database_error(error):
    text = str(error).lower()
    return (
        ("could not copy" in text and "cookie" in text)
        or "cookie database" in text
        or "failed to decrypt with dpapi" in text
        or "dpapi" in text
    )


def looks_like_subtitle_rate_limit(error):
    text = str(error).lower()
    return "subtitle" in text and ("429" in text or "too many requests" in text)
