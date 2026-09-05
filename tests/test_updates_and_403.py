"""Regression coverage: GitHub rate-limit classification, generic 403, and update fallback."""

import os
import sys
import unittest
from pathlib import Path
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from ggu_vdod.services.errors import classify_error  # noqa: E402
from ggu_vdod.services import updates  # noqa: E402


class ForbiddenClassificationTests(unittest.TestCase):
    def test_github_rate_limit_is_not_reported_as_http_429(self):
        details = classify_error(
            "Could not reach GitHub Releases: HTTP Error 403: rate limit exceeded",
            context="update check",
        )
        self.assertEqual(details.code, "ERR_GITHUB_RATE_LIMIT")
        self.assertIn("not a problem with your PC", details.simple_message)
        self.assertIn("Releases page", details.recommendation)

    def test_plain_403_forbidden_gets_friendly_auth_guidance(self):
        details = classify_error("HTTP Error 403: Forbidden")
        self.assertEqual(details.code, "ERR_HTTP_FORBIDDEN")
        self.assertEqual(details.action_type, "auth_setup")

    def test_cloudflare_403_still_wins_over_generic_403(self):
        details = classify_error(
            "HTTP Error 403: Forbidden; impersonate required for Cloudflare anti-bot challenge"
        )
        self.assertEqual(details.code, "ERR_CLOUDFLARE_403")

    def test_plain_429_still_maps_to_rate_limited_429(self):
        details = classify_error("HTTP Error 429: Too Many Requests")
        self.assertEqual(details.code, "ERR_RATE_LIMITED_429")

    def test_ffmpeg_postprocessing_failure_gets_dedicated_category(self):
        details = classify_error(
            "ERROR: Postprocessing: Error opening input files: Invalid data found when processing input"
        )
        self.assertEqual(details.code, "ERR_POSTPROCESS_FAILED")
        self.assertIn("FFmpeg", details.simple_message)
        self.assertEqual(details.action_type, "retry")


class FakeResponse:
    def __init__(self, url="", body=b"", headers=None):
        self._url = url
        self._body = body
        self.headers = headers or {}

    def geturl(self):
        return self._url

    def read(self, _n=-1):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class UpdateFallbackTests(unittest.TestCase):
    def test_api_403_falls_back_to_releases_page(self):
        import urllib.error

        api_error = urllib.error.HTTPError(
            updates.RELEASES_API, 403, "rate limit exceeded", hdrs={}, fp=None
        )
        html = (
            '<a href="/XerumGG/GGU_VDOD/releases/download/v9.9.9/GGU_VDOD-setup-v9.9.9.exe">x</a>'
        ).encode()

        def fake_urlopen(request, timeout=10):
            target = request.full_url if hasattr(request, "full_url") else request
            if "api.github.com" in target:
                raise api_error
            if target.rstrip("/").endswith("/releases/latest"):
                return FakeResponse(url="https://github.com/XerumGG/GGU_VDOD/releases/tag/v9.9.9")
            return FakeResponse(url=target, body=html)

        with mock.patch.object(updates.urllib.request, "urlopen", side_effect=fake_urlopen):
            release = updates.fetch_latest_release()

        self.assertEqual(release["tag_name"], "v9.9.9")
        self.assertEqual(release["version_tuple"], (9, 9, 9))
        self.assertEqual(
            release["installer_url"],
            "https://github.com/XerumGG/GGU_VDOD/releases/download/v9.9.9/GGU_VDOD-setup-v9.9.9.exe",
        )

    def test_api_success_is_untouched(self):
        payload = (
            b'{"tag_name": "v1.2.3", "assets": [{"name": "GGU_VDOD-setup-v1.2.3.exe",'
            b' "browser_download_url": "https://x/s.exe", "size": 123}]}'
        )

        def fake_urlopen(request, timeout=10):
            return FakeResponse(url=request.full_url, body=payload)

        with mock.patch.object(updates.urllib.request, "urlopen", side_effect=fake_urlopen):
            release = updates.fetch_latest_release()

        self.assertEqual(release["tag_name"], "v1.2.3")
        self.assertEqual(release["installer_size"], 123)


class ChunkedResponse(FakeResponse):
    """Fake response that yields the body in small chunks like a real download."""

    def read(self, n=-1):
        if not self._body:
            return b""
        out, self._body = self._body[:64], self._body[64:]
        return out


class InstallerDownloadTests(unittest.TestCase):
    def _run_download(self, fake_urlopen, **kwargs):
        import tempfile

        dest = os.path.join(tempfile.gettempdir(), "ggu_test_setup.exe")
        try:
            if os.path.exists(dest):
                os.remove(dest)
        except OSError:
            pass
        with mock.patch.object(updates.urllib.request, "urlopen", side_effect=fake_urlopen):
            result = updates.download_installer("https://x/s.exe", dest, **kwargs)
        return dest, result

    def test_successful_download_reports_progress(self):
        seen = []
        body = b"MZ" + b"\x00" * 500

        def fake_urlopen(request, timeout=30):
            return ChunkedResponse(url=request.full_url, body=body,
                                   headers={"Content-Length": str(len(body))})

        dest, result = self._run_download(
            fake_urlopen, progress_cb=lambda done, total: seen.append((done, total))
        )
        try:
            self.assertEqual(result, dest)
            self.assertTrue(seen)
            self.assertEqual(seen[-1][0], len(body))
        finally:
            os.remove(dest)

    def test_cancel_removes_partial_file(self):
        body = b"MZ" + b"\x00" * 500

        def fake_urlopen(request, timeout=30):
            return ChunkedResponse(url=request.full_url, body=body)

        import tempfile
        dest = os.path.join(tempfile.gettempdir(), "ggu_test_cancel.exe")
        with mock.patch.object(updates.urllib.request, "urlopen", side_effect=fake_urlopen):
            with self.assertRaises(InterruptedError):
                updates.download_installer(
                    "https://x/s.exe", dest, should_stop=lambda: True
                )
        self.assertFalse(os.path.exists(dest))

    def test_stalled_connection_raises_timeout(self):
        body = b"MZ" + b"\x00" * 500

        def fake_urlopen(request, timeout=30):
            return ChunkedResponse(url=request.full_url, body=body)

        import tempfile
        dest = os.path.join(tempfile.gettempdir(), "ggu_test_stall.exe")
        try:
            with mock.patch.object(updates.urllib.request, "urlopen", side_effect=fake_urlopen):
                with self.assertRaises(TimeoutError):
                    updates.download_installer(
                        "https://x/s.exe", dest, stall_deadline_s=0
                    )
        finally:
            if os.path.exists(dest):
                os.remove(dest)


class VerifyInstallerTests(unittest.TestCase):
    def test_missing_and_small_and_html_files_rejected(self):
        import tempfile

        self.assertFalse(updates.verify_installer_file(""))
        self.assertFalse(updates.verify_installer_file(os.path.join(tempfile.gettempdir(), "nope.exe")))
        small = os.path.join(tempfile.gettempdir(), "ggu_small.exe")
        html = os.path.join(tempfile.gettempdir(), "ggu_html.exe")
        try:
            with open(small, "wb") as f:
                f.write(b"MZ" + b"\x00" * 100)
            with open(html, "wb") as f:
                f.write(b"<html>Not Found</html>" + b" " * (6 * 1024 * 1024))
            self.assertFalse(updates.verify_installer_file(small))
            self.assertFalse(updates.verify_installer_file(html))
        finally:
            for path in (small, html):
                if os.path.exists(path):
                    os.remove(path)

    def test_realistic_installer_accepted(self):
        import tempfile

        path = os.path.join(tempfile.gettempdir(), "ggu_good.exe")
        try:
            with open(path, "wb") as f:
                f.write(b"MZ" + b"\x00" * (6 * 1024 * 1024))
            self.assertTrue(updates.verify_installer_file(path))
        finally:
            if os.path.exists(path):
                os.remove(path)


if __name__ == "__main__":
    unittest.main()
