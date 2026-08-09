"""Advanced test suite for Phase 1 Authentication Manager components."""

from pathlib import Path
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from ggu_vdod.auth.credman import (
    delete_windows_credential, read_windows_credential, write_windows_credential,
)
from ggu_vdod.auth.crypto import decrypt_string, derive_key, encrypt_string
from ggu_vdod.auth.manager import AuthManager, extract_domain
from ggu_vdod.auth.sanitizer import sanitize_headers, sanitize_log_text
from ggu_vdod.auth.store import clear_all_sessions


class AdvancedAuthTests(unittest.TestCase):
    def setUp(self):
        clear_all_sessions()

    def tearDown(self):
        clear_all_sessions()

    def test_windows_credential_manager_api(self):
        domain = "test-windows-cred.local"
        user = "admin@test.local"
        secret = "SecretPass_999!"

        written = write_windows_credential(domain, user, secret)
        if sys.platform == "win32":
            self.assertTrue(written)
            read_res = read_windows_credential(domain)
            self.assertIsNotNone(read_res)
            self.assertEqual(read_res[0], user)
            self.assertEqual(read_res[1], secret)
            deleted = delete_windows_credential(domain)
            self.assertTrue(deleted)
            self.assertIsNone(read_windows_credential(domain))

    def test_pbkdf2_key_derivation(self):
        passphrase = "master_password_key"
        salt = b"0123456789abcdef"
        key1 = derive_key(passphrase, salt)
        key2 = derive_key(passphrase, salt)
        self.assertEqual(len(key1), 32)
        self.assertEqual(key1, key2)

    def test_auth_manager_domain_extraction_and_lifecycle(self):
        url = "https://subdomain.staging.local:8080/path/to/media?v=123"
        self.assertEqual(extract_domain(url), "subdomain.staging.local")

        AuthManager.authenticate_domain(url, "user@staging.local", "secret_pass_123", auth_mode="local_test")
        self.assertTrue(AuthManager.is_domain_authorized("subdomain.staging.local"))

        session = AuthManager.resolve_domain_session("https://subdomain.staging.local/video")
        self.assertIsNotNone(session)
        self.assertEqual(session["account_label"], "user@staging.local")
        self.assertEqual(session["secret"], "secret_pass_123")

        forgot = AuthManager.forget_session("subdomain.staging.local")
        self.assertTrue(forgot)
        self.assertFalse(AuthManager.is_domain_authorized("subdomain.staging.local"))

    def test_auth_manager_allowlist_validation(self):
        allowlist = ["localhost", "127.0.0.1", "*.local", "*.staging.dev"]
        self.assertTrue(AuthManager.validate_allowlist("http://localhost:8025/test", allowlist))
        self.assertTrue(AuthManager.validate_allowlist("https://api.staging.dev/auth", allowlist))
        self.assertTrue(AuthManager.validate_allowlist("http://app.test.local/media", allowlist))
        self.assertFalse(AuthManager.validate_allowlist("https://untrusted-public-site.com", allowlist))

    def test_advanced_header_and_log_sanitizer(self):
        headers = {
            "Authorization": "Bearer eyJhbGciOiJIUzI1NiJ9.test",
            "Cookie": "session_id=abcdef123456",
            "User-Agent": "GGU_VDOD/0.1.0",
        }
        clean = sanitize_headers(headers)
        self.assertEqual(clean["Authorization"], "***REDACTED***")
        self.assertEqual(clean["Cookie"], "***REDACTED***")
        self.assertEqual(clean["User-Agent"], "GGU_VDOD/0.1.0")

        log = "Connecting to https://api.site.com/get?access_token=secret_tok_123&api_key=key_999"
        sanitized_log = sanitize_log_text(log)
        self.assertNotIn("secret_tok_123", sanitized_log)
        self.assertNotIn("key_999", sanitized_log)


if __name__ == "__main__":
    unittest.main()
