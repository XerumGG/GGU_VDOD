"""Unit tests for DPAPI encryption, domain session store, and log sanitizer."""

from pathlib import Path
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from ggu_vdod.auth.crypto import decrypt_string, encrypt_string, protect_bytes, unprotect_bytes
from ggu_vdod.auth.sanitizer import sanitize_log_text
from ggu_vdod.auth.store import (
    clear_all_sessions, forget_domain_session, get_domain_session,
    list_active_sessions, save_domain_session,
)


class AuthCryptoAndStoreTests(unittest.TestCase):
    def setUp(self):
        clear_all_sessions()

    def tearDown(self):
        clear_all_sessions()

    def test_dpapi_string_encryption_decryption(self):
        raw_text = "super_secret_password_123!@#"
        ciphertext = encrypt_string(raw_text)
        self.assertNotEqual(raw_text, ciphertext)
        decrypted = decrypt_string(ciphertext)
        self.assertEqual(raw_text, decrypted)

    def test_domain_session_store_save_get_and_forget(self):
        domain = "test-staging.local"
        label = "test_user@staging.local"
        secret = "secret_auth_token_999"

        save_domain_session(domain, label, secret, auth_mode="local_test", expires_in_days=7)
        session = get_domain_session(domain)

        self.assertIsNotNone(session)
        self.assertEqual(session["domain"], domain)
        self.assertEqual(session["account_label"], label)
        self.assertEqual(session["secret"], secret)
        self.assertEqual(session["auth_mode"], "local_test")
        self.assertFalse(session["is_expired"])

        sessions_list = list_active_sessions()
        self.assertEqual(len(sessions_list), 1)
        self.assertEqual(sessions_list[0]["domain"], domain)
        # Secret should not be present in summary listing
        self.assertNotIn("secret", sessions_list[0])

        forget_success = forget_domain_session(domain)
        self.assertTrue(forget_success)
        self.assertIsNone(get_domain_session(domain))

    def test_log_sanitizer_masks_credentials(self):
        raw_log = "Error connecting with password=MySecretPassword123 and Authorization: Bearer eyJhbGciOiJIUzI1NiJ9"
        sanitized = sanitize_log_text(raw_log)
        self.assertNotIn("MySecretPassword123", sanitized)
        self.assertIn("***REDACTED***", sanitized)


if __name__ == "__main__":
    unittest.main()
