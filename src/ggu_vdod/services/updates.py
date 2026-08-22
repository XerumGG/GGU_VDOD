"""GitHub Releases update service for GGU_VDOD."""

import json
import os
import re
import urllib.request

RELEASES_API = "https://api.github.com/repos/XerumGG/GGU_VDOD/releases/latest"
RELEASES_PAGE = "https://github.com/XerumGG/GGU_VDOD/releases/latest"


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
    """Return dict(tag_name, version_tuple, installer_url, installer_size) or raise."""
    request = urllib.request.Request(
        RELEASES_API,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "GGU_VDOD-Updater"},
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


def is_newer(latest_tuple):
    return latest_tuple > current_version_tuple()


def download_installer(url, dest_path, progress_cb=None, timeout=30):
    """Stream the setup exe to dest_path; progress_cb(bytes_done, total_bytes)."""
    request = urllib.request.Request(url, headers={"User-Agent": "GGU_VDOD-Updater"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        total = int(response.headers.get("Content-Length") or 0)
        done = 0
        with open(dest_path, "wb") as f:
            while True:
                chunk = response.read(65536)
                if not chunk:
                    break
                f.write(chunk)
                done += len(chunk)
                if progress_cb:
                    progress_cb(done, total)
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
