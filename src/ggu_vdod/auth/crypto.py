"""DPAPI & PBKDF2 HMAC-SHA256 salted encryption for GGU_VDOD."""

import base64
import ctypes
import hashlib
import hmac
import os
import secrets
import sys

if sys.platform == "win32":
    import ctypes.wintypes

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [
            ("cbData", ctypes.wintypes.DWORD),
            ("pbData", ctypes.POINTER(ctypes.c_byte)),
        ]


class DPAPIError(Exception):
    """Raised when Windows DPAPI protection fails and secrets must not be written."""


def protect_bytes(raw_data: bytes, description: str = "GGU_VDOD_DPAPI") -> bytes:
    """Encrypt raw bytes using Windows DPAPI (CryptProtectData)."""
    if not raw_data:
        return b""
    if sys.platform == "win32":
        try:
            buffer = (ctypes.c_byte * len(raw_data))(*raw_data)
            in_blob = DATA_BLOB(len(raw_data), buffer)
            out_blob = DATA_BLOB()
            if ctypes.windll.crypt32.CryptProtectData(
                ctypes.byref(in_blob),
                description,
                None,
                None,
                None,
                0,
                ctypes.byref(out_blob),
            ):
                protected = bytes(ctypes.string_at(out_blob.pbData, out_blob.cbData))
                ctypes.windll.kernel32.LocalFree(out_blob.pbData)
                return protected
        except Exception:
            pass
        raise DPAPIError("Windows DPAPI encryption failed; refusing to store secrets with a weak fallback.")
    # Obfuscation-only fallback for non-Windows development platforms.
    salt = secrets.token_bytes(16)
    key = hashlib.pbkdf2_hmac("sha256", b"GGU_VDOD_LOCAL_SECRET", salt, 100000)
    cipher = bytes([b ^ key[i % len(key)] for i, b in enumerate(raw_data)])
    return salt + cipher


def unprotect_bytes(protected_data: bytes) -> bytes:
    """Decrypt bytes using Windows DPAPI (CryptUnprotectData)."""
    if not protected_data:
        return b""
    if sys.platform == "win32":
        try:
            buffer = (ctypes.c_byte * len(protected_data))(*protected_data)
            in_blob = DATA_BLOB(len(protected_data), buffer)
            out_blob = DATA_BLOB()
            if ctypes.windll.crypt32.CryptUnprotectData(
                ctypes.byref(in_blob),
                None,
                None,
                None,
                None,
                0,
                ctypes.byref(out_blob),
            ):
                unprotected = bytes(ctypes.string_at(out_blob.pbData, out_blob.cbData))
                ctypes.windll.kernel32.LocalFree(out_blob.pbData)
                return unprotected
        except Exception:
            pass
        return b""
    try:
        if len(protected_data) > 16:
            salt = protected_data[:16]
            cipher = protected_data[16:]
            key = hashlib.pbkdf2_hmac("sha256", b"GGU_VDOD_LOCAL_SECRET", salt, 100000)
            return bytes([b ^ key[i % len(key)] for i, b in enumerate(cipher)])
    except Exception:
        pass
    return b""


def encrypt_string(plaintext: str) -> str:
    """Encrypt a string and return base64 encoded ciphertext string."""
    if not plaintext:
        return ""
    encrypted_bytes = protect_bytes(plaintext.encode("utf-8"))
    return base64.b64encode(encrypted_bytes).decode("ascii")


def decrypt_string(ciphertext_b64: str) -> str:
    """Decrypt base64 encoded ciphertext string and return plaintext."""
    if not ciphertext_b64:
        return ""
    try:
        raw_encrypted = base64.b64decode(ciphertext_b64.encode("ascii"))
        decrypted_bytes = unprotect_bytes(raw_encrypted)
        return decrypted_bytes.decode("utf-8")
    except Exception:
        return ""


def derive_key(passphrase: str, salt: bytes) -> bytes:
    """Derive 256-bit key from passphrase using PBKDF2 HMAC-SHA256."""
    return hashlib.pbkdf2_hmac("sha256", passphrase.encode("utf-8"), salt, 100000)
