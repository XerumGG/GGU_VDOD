"""High-level Authentication Manager service for domain resolution and session TTL enforcement."""

import fnmatch
from urllib.parse import urlparse

from .store import (
    clear_all_sessions, forget_domain_session, get_domain_session,
    list_active_sessions, save_domain_session,
)


def extract_domain(url_or_domain: str) -> str:
    """Extract clean domain name from URL or domain string."""
    if not url_or_domain:
        return ""
    text = url_or_domain.strip().lower()
    if "://" in text:
        parsed = urlparse(text)
        return parsed.hostname or ""
    return text.split("/")[0].split(":")[0]


class AuthManager:
    """Authentication lifecycle manager for GGU_VDOD."""

    @staticmethod
    def extract_domain(url_or_domain: str) -> str:
        return extract_domain(url_or_domain)

    @classmethod
    def authenticate_domain(
        cls,
        domain_or_url: str,
        account_label: str,
        secret: str = "",
        auth_mode: str = "credentials",
        expires_in_days: int = 30,
    ) -> dict:
        """Register or update an authenticated domain session."""
        domain = extract_domain(domain_or_url)
        if not domain:
            raise ValueError("Invalid domain name or URL.")
        return save_domain_session(domain, account_label, secret, auth_mode, expires_in_days)

    @classmethod
    def resolve_domain_session(cls, domain_or_url: str) -> dict | None:
        """Fetch active session for domain if valid and not expired."""
        domain = extract_domain(domain_or_url)
        if not domain:
            return None
        session = get_domain_session(domain)
        if session and session.get("is_expired"):
            return None
        return session

    @classmethod
    def is_domain_authorized(cls, domain_or_url: str) -> bool:
        """Check if an unexpired session exists for domain."""
        session = cls.resolve_domain_session(domain_or_url)
        return session is not None

    @classmethod
    def forget_session(cls, domain_or_url: str) -> bool:
        """Forget session for specified domain or URL."""
        domain = extract_domain(domain_or_url)
        return forget_domain_session(domain)

    @classmethod
    def clear_all(cls) -> int:
        """Clear all active stored sessions."""
        return clear_all_sessions()

    @classmethod
    def purge_expired_sessions(cls) -> int:
        """Purge all expired domain sessions."""
        sessions = list_active_sessions()
        purged = 0
        for s in sessions:
            if s.get("is_expired"):
                forget_domain_session(s["domain"])
                purged += 1
        return purged

    @classmethod
    def validate_allowlist(cls, domain_or_url: str, allowlist: list[str]) -> bool:
        """Check if domain matches any pattern in domain allowlist."""
        domain = extract_domain(domain_or_url)
        if not domain or not allowlist:
            return False
        for pattern in allowlist:
            p = pattern.strip().lower()
            if fnmatch.fnmatch(domain, p) or domain == p:
                return True
        return False
