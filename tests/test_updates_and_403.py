"""Regression coverage: GitHub rate-limit classification, generic 403, and update fallback."""

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


if __name__ == "__main__":
    unittest.main()
