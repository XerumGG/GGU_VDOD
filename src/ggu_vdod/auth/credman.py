"""Native Windows Credential Manager (advapi32.dll) wrapper for GGU_VDOD."""

import ctypes
import sys

if sys.platform == "win32":
    from ctypes import wintypes

    class CREDENTIAL_ATTRIBUTE(ctypes.Structure):
        _fields_ = [
            ("Keyword", wintypes.LPWSTR),
            ("Flags", wintypes.DWORD),
            ("ValueSize", wintypes.DWORD),
            ("Value", ctypes.c_char_p),
        ]

    class CREDENTIAL(ctypes.Structure):
        _fields_ = [
            ("Flags", wintypes.DWORD),
            ("Type", wintypes.DWORD),
            ("TargetName", wintypes.LPWSTR),
            ("Comment", wintypes.LPWSTR),
            ("LastWritten", wintypes.FILETIME),
            ("CredentialBlobSize", wintypes.DWORD),
            ("CredentialBlob", ctypes.POINTER(ctypes.c_byte)),
            ("Persist", wintypes.DWORD),
            ("AttributeCount", wintypes.DWORD),
            ("Attributes", ctypes.POINTER(CREDENTIAL_ATTRIBUTE)),
            ("TargetAlias", wintypes.LPWSTR),
            ("UserName", wintypes.LPWSTR),
        ]

    CRED_TYPE_GENERIC = 1
    CRED_PERSIST_LOCAL_MACHINE = 2


def build_target_name(domain: str) -> str:
    """Format domain name into GGU_VDOD target key."""
    clean_domain = domain.strip().lower()
    return f"GGU_VDOD:{clean_domain}"


def write_windows_credential(domain: str, username: str, secret: str) -> bool:
    """Store domain credential in Windows Credential Manager."""
    if sys.platform != "win32" or not domain or not secret:
        return False
    try:
        target_name = build_target_name(domain)
        secret_bytes = secret.encode("utf-16le")
        blob = (ctypes.c_byte * len(secret_bytes)).from_buffer_copy(secret_bytes)

        cred = CREDENTIAL(
            Flags=0,
            Type=CRED_TYPE_GENERIC,
            TargetName=target_name,
            Comment="GGU_VDOD Domain Credential",
            CredentialBlobSize=len(secret_bytes),
            CredentialBlob=ctypes.cast(blob, ctypes.POINTER(ctypes.c_byte)),
            Persist=CRED_PERSIST_LOCAL_MACHINE,
            AttributeCount=0,
            Attributes=None,
            TargetAlias=None,
            UserName=username,
        )
        res = ctypes.windll.advapi32.CredWriteW(ctypes.byref(cred), 0)
        return bool(res)
    except Exception:
        return False


def read_windows_credential(domain: str) -> tuple[str, str] | None:
    """Retrieve username and secret from Windows Credential Manager."""
    if sys.platform != "win32" or not domain:
        return None
    try:
        target_name = build_target_name(domain)
        cred_ptr = ctypes.POINTER(CREDENTIAL)()
        res = ctypes.windll.advapi32.CredReadW(
            target_name, CRED_TYPE_GENERIC, 0, ctypes.byref(cred_ptr)
        )
        if res and cred_ptr:
            cred = cred_ptr.contents
            blob_bytes = bytes(ctypes.string_at(cred.CredentialBlob, cred.CredentialBlobSize))
            secret = blob_bytes.decode("utf-16le")
            username = cred.UserName or ""
            ctypes.windll.advapi32.CredFree(cred_ptr)
            return username, secret
    except Exception:
        pass
    return None


def delete_windows_credential(domain: str) -> bool:
    """Delete domain credential from Windows Credential Manager."""
    if sys.platform != "win32" or not domain:
        return False
    try:
        target_name = build_target_name(domain)
        res = ctypes.windll.advapi32.CredDeleteW(target_name, CRED_TYPE_GENERIC, 0)
        return bool(res)
    except Exception:
        return False
