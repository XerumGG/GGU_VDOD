"""GitHub Releases update service for GGU_VDOD."""

import json
import os
import re
import urllib.parse
import urllib.request

RELEASES_API = "https://api.github.com/repos/XerumGG/GGU_VDOD/releases/latest"
RELEASES_PAGE = "https://github.com/XerumGG/GGU_VDOD/releases/latest"
EXPANDED_ASSETS = "https://github.com/XerumGG/GGU_VDOD/releases/expanded_assets/{tag}"
USER_AGENT = "GGU_VDOD-Updater"


def parse_version(text):
    """Extract a comparable tuple from strings like 'v0.2.12' or '0.02.12'."""
    parts = re.findall(r"\d+", str(text or ""))[:3]
    while len(parts) < 3:
        parts.append("0")
    return tuple(int(p) for p in parts)


def current_version_tuple():
    from ..core.version import PACKAGE_VERSION
    return parse_version(PACKAGE_VERSION)


def fetch_latest_release(timeout=10):
    """Return dict(tag_name, version_tuple, installer_url, installer_size) or raise.

    The REST API allows only ~60 unauthenticated requests per hour per IP and
    answers HTTP 403 'rate limit exceeded' beyond that, so on any API failure
    we fall back to the public Releases page, which has no such quota.
    """
    try:
        return _fetch_via_api(timeout)
    except Exception as api_error:
        try:
            return _fetch_via_releases_page(timeout)
        except Exception:
            raise api_error


def _fetch_via_api(timeout):
    request = urllib.request.Request(
        RELEASES_API,
        headers={"Accept": "application/vnd.github+json", "User-Agent": USER_AGENT},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = json.loads(response.read(1024 * 1024).decode("utf-8"))

    installer_url = ""
    installer_size = 0
    for asset in data.get("assets", []):
        name = asset.get("name", "")
        if name.startswith("GGU_VDOD-setup-") and name.endswith(".exe"):
            installer_url = asset.get("browser_download_url", "")
            installer_size = asset.get("size", 0)
            break
    return {
        "tag_name": data.get("tag_name", ""),
        "version_tuple": parse_version(data.get("tag_name")),
        "installer_url": installer_url,
        "installer_size": installer_size,
        "html_url": data.get("html_url") or RELEASES_PAGE,
    }


def _fetch_via_releases_page(timeout):
    """Rate-limit-free fallback: /releases/latest 302s to /releases/tag/<tag>."""
    request = urllib.request.Request(RELEASES_PAGE, headers={"User-Agent": USER_AGENT}, method="HEAD")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        final_url = response.geturl() or ""

    match = re.search(r"/releases/tag/([^/?#]+)", final_url)
    if not match:
        raise RuntimeError("Could not resolve the latest release tag from the Releases page")
    tag = urllib.parse.unquote(match.group(1))

    installer_url = ""
    try:
        assets_request = urllib.request.Request(
            EXPANDED_ASSETS.format(tag=tag), headers={"User-Agent": USER_AGENT}
        )
        with urllib.request.urlopen(assets_request, timeout=timeout) as response:
            html = response.read(1024 * 1024).decode("utf-8", "ignore")
        asset_match = re.search(r'href="(/[^"]*GGU_VDOD-setup-[^"]*\.exe|https://github\.com[^"]*GGU_VDOD-setup-[^"]*\.exe)"', html)
        if asset_match:
            href = asset_match.group(1)
            installer_url = "https://github.com" + href if href.startswith("/") else href
    except Exception:
        pass

    if not installer_url:
        installer_url = f"https://github.com/XerumGG/GGU_VDOD/releases/download/{tag}/GGU_VDOD-setup-{tag}.exe"

    return {
        "tag_name": tag,
        "version_tuple": parse_version(tag),
        "installer_url": installer_url,
        "installer_size": 0,
        "html_url": f"https://github.com/XerumGG/GGU_VDOD/releases/tag/{tag}",
    }


def is_newer(latest_tuple):
    return latest_tuple > current_version_tuple()


MIN_INSTALLER_BYTES = 5 * 1024 * 1024


def verify_installer_file(path, min_bytes=MIN_INSTALLER_BYTES):
    """True only if path exists, is plausibly large, and starts with the MZ exe header.

    Catches truncated downloads and HTML error pages saved with an .exe name.
    """
    try:
        if not path or not os.path.isfile(path):
            return False
        if os.path.getsize(path) < min_bytes:
            return False
        with open(path, "rb") as f:
            return f.read(2) == b"MZ"
    except OSError:
        return False


def download_installer(url, dest_path, progress_cb=None, timeout=30,
                       stall_deadline_s=90, should_stop=None):
    """Stream the setup exe to dest_path; progress_cb(bytes_done, total_bytes).

    Raises TimeoutError if no bytes arrive for stall_deadline_s seconds, and
    InterruptedError if should_stop() returns True (partial file is removed).
    """
    import time as _time
    request = urllib.request.Request(url, headers={"User-Agent": "GGU_VDOD-Updater"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        total = int(response.headers.get("Content-Length") or 0)
        done = 0
        last_activity = _time.monotonic()
        try:
            with open(dest_path, "wb") as f:
                while True:
                    if should_stop is not None and should_stop():
                        raise InterruptedError("cancelled")
                    if _time.monotonic() - last_activity > stall_deadline_s:
                        raise TimeoutError(
                            f"no data received for {stall_deadline_s}s (stalled connection)"
                        )
                    chunk = response.read(65536)
                    if not chunk:
                        break
                    f.write(chunk)
                    done += len(chunk)
                    last_activity = _time.monotonic()
                    if progress_cb:
                        progress_cb(done, total)
        except BaseException:
            if should_stop is not None and should_stop():
                try:
                    if os.path.exists(dest_path):
                        os.remove(dest_path)
                except OSError:
                    pass
                raise InterruptedError("cancelled")
            raise
    return dest_path


def find_installed_uninstaller():
    """Path of Inno's unins000.exe beside this exe, or '' in dev/portable mode."""
    if getattr(__import__("sys"), "frozen", False):
        candidate = os.path.join(os.path.dirname(os.path.abspath(__import__("sys").executable)), "unins000.exe")
        if os.path.isfile(candidate):
            return candidate
    return ""


def get_config_dir():
    from ..config.paths import get_config_dir as _gcd
    return _gcd()
