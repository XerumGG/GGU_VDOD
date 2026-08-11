"""Unit test suite for ErrorClassifier, ErrorDetails, and Error System in GGU_VDOD."""

import unittest
from src.ggu_vdod.services.errors import classify_error, ErrorDetails
from src.ggu_vdod.services.audio import play_error_sound, play_success_sound, sound_pattern_for


class TestErrorClassification(unittest.TestCase):
    """Test suite for error categorization and natural language translation."""

    def test_disk_space_full_classification(self):
        err = OSError("[Errno 28] No space left on device")
        details = classify_error(err, context="D:\\Downloads")
        self.assertEqual(details.code, "ERR_DISK_FULL")
        self.assertEqual(details.severity, "CRITICAL")
        self.assertIn("hard drive", details.simple_message.lower())
        self.assertEqual(details.action_type, "change_dir")
        self.assertEqual(details.sound_type, "MB_ICONSTOP")

    def test_network_disconnected_classification(self):
        err = ConnectionResetError("Connection reset by peer during socket read")
        details = classify_error(err)
        self.assertEqual(details.code, "ERR_NET_DISCONNECTED")
        self.assertEqual(details.severity, "WARNING")
        self.assertIn("internet or network", details.simple_message.lower())
        self.assertEqual(details.action_type, "retry")

    def test_cloudflare_403_classification(self):
        err_msg = "ERROR: [generic] HTTP Error 403: Forbidden; impersonate required for Cloudflare anti-bot challenge"
        details = classify_error(err_msg)
        self.assertEqual(details.code, "ERR_CLOUDFLARE_403")
        self.assertEqual(details.severity, "WARNING")
        self.assertIn("cloudflare", details.simple_message.lower())
        self.assertEqual(details.action_type, "auth_setup")

    def test_rate_limited_429_classification(self):
        err_msg = "ERROR: [youtube] HTTP Error 429: Too Many Requests - rate limited by server"
        details = classify_error(err_msg)
        self.assertEqual(details.code, "ERR_RATE_LIMITED_429")
        self.assertEqual(details.severity, "WARNING")
        self.assertEqual(details.action_type, "retry")

    def test_age_restricted_classification(self):
        err_msg = "ERROR: [youtube] Sign in to confirm your age. This video is age-restricted"
        details = classify_error(err_msg)
        self.assertEqual(details.code, "ERR_AGE_RESTRICTED")
        self.assertEqual(details.severity, "INFO")
        self.assertEqual(details.action_type, "auth_setup")

    def test_private_video_classification(self):
        err_msg = "ERROR: [youtube] Private video. Sign in if you have been granted access to this video"
        details = classify_error(err_msg)
        self.assertEqual(details.code, "ERR_PRIVATE_VIDEO")
        self.assertEqual(details.severity, "WARNING")

    def test_video_deleted_404_classification(self):
        err_msg = "ERROR: [youtube] HTTP Error 404: Not Found - Video unavailable. This video has been removed"
        details = classify_error(err_msg)
        self.assertEqual(details.code, "ERR_VIDEO_DELETED_404")
        self.assertEqual(details.severity, "WARNING")

    def test_geoblocked_classification(self):
        err_msg = "ERROR: [youtube] The uploader has not made this video available in your country"
        details = classify_error(err_msg)
        self.assertEqual(details.code, "ERR_GEOBLOCKED")
        self.assertEqual(details.severity, "WARNING")

    def test_ffmpeg_missing_classification(self):
        err_msg = "ERROR: ffmpeg not found. Please install ffmpeg or set ffmpeg_location"
        details = classify_error(err_msg)
        self.assertEqual(details.code, "ERR_FFMPEG_MISSING")
        self.assertEqual(details.severity, "CRITICAL")
        self.assertEqual(details.action_type, "ffmpeg_browse")

    def test_format_unavailable_classification(self):
        err_msg = "ERROR: [youtube] Requested format is not available. Use --list-formats to see available formats"
        details = classify_error(err_msg)
        self.assertEqual(details.code, "ERR_FORMAT_UNAVAILABLE")
        self.assertEqual(details.severity, "INFO")
        self.assertEqual(details.action_type, "change_quality")

    def test_permission_denied_classification(self):
        err = PermissionError("[WinError 5] Access is denied: 'C:\\Program Files\\Protected'")
        details = classify_error(err)
        self.assertEqual(details.code, "ERR_PERMISSION_DENIED")
        self.assertEqual(details.severity, "CRITICAL")
        self.assertEqual(details.action_type, "change_dir")

    def test_dpapi_cookie_lock_classification(self):
        err_msg = "ERROR: Failed to decrypt with DPAPI. See https://github.com/yt-dlp/yt-dlp/issues/10927"
        details = classify_error(err_msg)
        self.assertEqual(details.code, "ERR_DPAPI_COOKIE_LOCK")
        self.assertEqual(details.severity, "WARNING")

    def test_chrome_cookie_copy_error_is_classified_for_user_action(self):
        details = classify_error("Could not copy Chrome cookie database. See yt-dlp issue 7271")
        self.assertEqual(details.code, "ERR_DPAPI_COOKIE_LOCK")
        self.assertEqual(details.action_type, "close_browser")

    def test_proxy_failed_classification(self):
        err_msg = "ERROR: ProxyError: Unable to connect to SOCKS proxy server at 127.0.0.1:9050"
        details = classify_error(err_msg)
        self.assertEqual(details.code, "ERR_PROXY_FAILED")
        self.assertEqual(details.severity, "WARNING")

    def test_corrupt_stream_classification(self):
        err_msg = "ERROR: Output file is 0-byte or media health verification failed"
        details = classify_error(err_msg)
        self.assertEqual(details.code, "ERR_CORRUPT_STREAM")
        self.assertEqual(details.severity, "WARNING")

    def test_fragment_failed_classification(self):
        err_msg = "ERROR: Fragment download failed (HTTP Error 503: Service Unavailable)"
        details = classify_error(err_msg)
        self.assertEqual(details.code, "ERR_FRAGMENT_FAILED")
        self.assertEqual(details.severity, "WARNING")

    def test_unhandled_fallback_classification(self):
        err = RuntimeError("Unexpected custom failure string")
        details = classify_error(err)
        self.assertEqual(details.code, "ERR_UNHANDLED_EXCEPTION")
        self.assertEqual(details.severity, "CRITICAL")

    def test_audio_sound_triggers_without_error(self):
        try:
            play_error_sound("MB_ICONHAND")
            play_error_sound("MB_ICONSTOP")
            play_error_sound("MB_ICONEXCLAMATION")
            play_error_sound("MB_ICONASTERISK")
            play_success_sound()
        except Exception as e:
            self.fail(f"Audio sound trigger raised exception: {e}")

    def test_error_categories_have_distinct_sound_patterns(self):
        self.assertNotEqual(
            sound_pattern_for("MB_ICONSTOP", "ERR_DISK_FULL"),
            sound_pattern_for("MB_ICONHAND", "ERR_NET_DISCONNECTED"),
        )
        self.assertNotEqual(
            sound_pattern_for("MB_ICONEXCLAMATION", "ERR_RATE_LIMITED_429"),
            sound_pattern_for("MB_ICONASTERISK", "ERR_AGE_RESTRICTED"),
        )


if __name__ == "__main__":
    unittest.main()
