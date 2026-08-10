"""Domain session registry with Windows Credential Manager & DPAPI integration."""

import json
import os
from pathlib import Path
import sys
import time

from ..config.paths import get_app_dir
from .credman import (
    delete_windows_credential, read_windows_credential, write_windows_credential,
)
from .crypto import decrypt_string, encrypt_string, protect_bytes, unprotect_bytes


def get_auth_store_path() -> Path:
    """Return path to auth_sessions.json in app data directory."""
    return Path(get_app_dir()) / "auth_sessions.json"


def load_auth_sessions() -> dict:
    """Load all saved domain sessions from auth_sessions.json (or dat fallback)."""
    store_path = get_auth_store_path()
    dat_path = Path(get_app_dir()) / "auth_sessions.dat"

    # Fallback to dat file if json doesn't exist yet
    if not store_path.is_file() and dat_path.is_file():
        try:
            raw_bytes = dat_path.read_bytes()
            if raw_bytes:
                decrypted_bytes = unprotect_bytes(raw_bytes)
                data = json.loads(decrypted_bytes.decode("utf-8"))
                if isinstance(data, dict):
                    save_auth_sessions(data)
                    return data
        except Exception:
            pass

    if not store_path.is_file():
        return {}
    try:
        data = json.loads(store_path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {}


def save_auth_sessions(sessions: dict) -> None:
    """Persist domain sessions to auth_sessions.json."""
    store_path = get_auth_store_path()
    try:
        os.makedirs(store_path.parent, exist_ok=True)
        store_path.write_text(json.dumps(sessions, indent=2), encoding="utf-8")
    except Exception:
        pass


def save_domain_session(
    domain: str,
    account_label: str,
    secret: str = "",
    auth_mode: str = "credentials",
    expires_in_days: int = 30,
) -> dict:
    """Save session metadata and store secret in Windows Credential Manager & DPAPI."""
    domain_key = domain.strip().lower()
    if not domain_key:
        raise ValueError("Domain cannot be empty.")

    now = int(time.time())
    expires_at = now + (expires_in_days * 86400) if expires_in_days > 0 else 0

    # Store in Windows Credential Manager if available
    if secret and sys.platform == "win32":
        write_windows_credential(domain_key, account_label.strip(), secret)

    sessions = load_auth_sessions()
    sessions[domain_key] = {
        "domain": domain_key,
        "account_label": account_label.strip(),
        "encrypted_secret": encrypt_string(secret) if secret else "",
        "auth_mode": auth_mode,
        "created_at": now,
        "expires_at": expires_at,
    }
    save_auth_sessions(sessions)
    return sessions[domain_key]


def get_domain_session(domain: str) -> dict | None:
    """Retrieve session metadata and secret from Windows Credential Manager / DPAPI."""
    domain_key = domain.strip().lower()
    sessions = load_auth_sessions()
    entry = sessions.get(domain_key)
    if not entry:
        return None

    now = int(time.time())
    expires_at = entry.get("expires_at", 0)
    is_expired = bool(expires_at and now > expires_at)

    secret = ""
    account_label = entry.get("account_label", "")

    # Try reading from Windows Credential Manager
    if sys.platform == "win32":
        cred_res = read_windows_credential(domain_key)
        if cred_res:
            account_label = cred_res[0] or account_label
            secret = cred_res[1]

    # Fallback to DPAPI decrypted string if Credential Manager did not return secret
    if not secret and entry.get("encrypted_secret"):
        secret = decrypt_string(entry.get("encrypted_secret", ""))

    return {
        "domain": entry.get("domain", domain_key),
        "account_label": account_label,
        "secret": secret,
        "auth_mode": entry.get("auth_mode", "credentials"),
        "created_at": entry.get("created_at", 0),
        "expires_at": expires_at,
        "is_expired": is_expired,
    }


def list_active_sessions() -> list[dict]:
    """Return summary list of all stored domain sessions without decrypted secrets."""
    sessions = load_auth_sessions()
    now = int(time.time())
    result = []
    for domain, entry in sessions.items():
        expires_at = entry.get("expires_at", 0)
        result.append({
            "domain": domain,
            "account_label": entry.get("account_label", ""),
            "auth_mode": entry.get("auth_mode", "credentials"),
            "created_at": entry.get("created_at", 0),
            "expires_at": expires_at,
            "is_expired": bool(expires_at and now > expires_at),
        })
    return result


def forget_domain_session(domain: str) -> bool:
    """Delete session entry from Windows Credential Manager and local store."""
    domain_key = domain.strip().lower()
    if sys.platform == "win32":
        delete_windows_credential(domain_key)

    sessions = load_auth_sessions()
    if domain_key in sessions:
        del sessions[domain_key]
        save_auth_sessions(sessions)
        return True
    return False


def clear_all_sessions() -> int:
    """Delete all stored domain sessions from Windows Credential Manager and store."""
    sessions = load_auth_sessions()
    count = len(sessions)
    if sys.platform == "win32":
        for domain in sessions:
            delete_windows_credential(domain)
    save_auth_sessions({})
    return count
