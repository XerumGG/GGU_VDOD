"""Media metadata retrieval shared by present and future desktop interfaces."""

import html
import json
import re
import urllib.parse
import urllib.request

import yt_dlp

from ..core.constants import APP_NAME
from ..services.network import looks_like_cookie_database_error
from .metadata import (
    best_thumbnail_url, download_thumbnail_bytes, format_duration,
    friendly_source_name, preview_target_url, youtube_video_id,
)


class PreviewError(Exception):
    """Raised when neither extractor nor public metadata can produce a preview."""


def fetch_preview(url, browser="None", cookies_file="", proxy=""):
    """Fetch public metadata without downloading media or expanding playlists."""
    target_url = preview_target_url(url)
    options = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
        "socket_timeout": 12,
        "extractor_retries": 1,
    }
    if browser != "None":
        options["cookiesfrombrowser"] = (browser.lower(), None, None, None)
    if cookies_file:
        options["cookiefile"] = cookies_file
    if proxy:
        options["proxy"] = proxy

    try:
        with yt_dlp.YoutubeDL(options) as downloader:
            info = downloader.extract_info(target_url, download=False)
    except Exception as error:
        final_error = error
        if browser != "None" and looks_like_cookie_database_error(error):
            options.pop("cookiesfrombrowser", None)
            try:
                with yt_dlp.YoutubeDL(options) as downloader:
                    info = downloader.extract_info(target_url, download=False)
            except Exception as retry_error:
                final_error = retry_error
            else:
                final_error = None
        if final_error is not None:
            public_preview = get_public_title_preview(target_url)
            if public_preview:
                return public_preview
            raise PreviewError(str(final_error)) from final_error

    if info.get("_type") == "playlist":
        entries = info.get("entries") or []
        selected_video_id = youtube_video_id(url)
        info = next(
            (entry for entry in entries if entry and (
                not selected_video_id or entry.get("id") == selected_video_id
            )),
            next((entry for entry in entries if entry), info),
        )

    thumbnail_url = best_thumbnail_url(info)
    thumbnail_data = download_thumbnail_bytes(thumbnail_url)
    height = info.get("height")
    abr = info.get("abr")
    resolution = info.get("resolution") or (f"{height}p" if height else "")
    if not resolution and abr:
        resolution = f"{abr:.0f} kbps"
    return {
        "title": info.get("title") or "Untitled media",
        "details": "  •  ".join(filter(None, [
            info.get("uploader") or info.get("channel"),
            format_duration(info.get("duration")),
            resolution,
        ])) or "Metadata available",
        "thumbnail_data": thumbnail_data,
        "thumbnail_url": thumbnail_url,
        "source": friendly_source_name(info.get("extractor_key") or info.get("extractor")),
    }


def get_public_title_preview(url):
    """Retrieve public oEmbed/Open Graph metadata without bypassing access checks."""
    title = ""
    uploader = ""
    thumbnail_url = ""
    source = ""
    try:
        host = urllib.parse.urlsplit(url).netloc.casefold().split(":")[0]
        source = host.removeprefix("www.")
        if host in {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com", "youtu.be"}:
            oembed_url = "https://www.youtube.com/oembed?" + urllib.parse.urlencode({
                "url": url,
                "format": "json",
            })
            request = urllib.request.Request(oembed_url, headers={"User-Agent": APP_NAME})
            with urllib.request.urlopen(request, timeout=8) as response:
                oembed = json.loads(response.read(512 * 1024).decode("utf-8", errors="replace"))
            title = str(oembed.get("title") or "").strip()
            uploader = str(oembed.get("author_name") or "").strip()
            thumbnail_url = str(oembed.get("thumbnail_url") or "").strip()
    except Exception:
        pass

    if not title:
        try:
            request = urllib.request.Request(url, headers={
                "User-Agent": f"Mozilla/5.0 ({APP_NAME} public title preview)",
                "Accept": "text/html,application/xhtml+xml",
            })
            with urllib.request.urlopen(request, timeout=8) as response:
                page = response.read(1024 * 1024).decode("utf-8", errors="replace")
            metadata = {}
            for tag in re.findall(r"<meta\b[^>]*>", page, flags=re.IGNORECASE):
                attributes = {
                    name.casefold(): value
                    for name, value in re.findall(r'''([:\w-]+)\s*=\s*["']([^"']*)["']''', tag)
                }
                key = (attributes.get("property") or attributes.get("name") or "").casefold()
                value = attributes.get("content") or ""
                if key and value:
                    metadata[key] = html.unescape(value).strip()
            title = metadata.get("og:title") or metadata.get("twitter:title") or ""
            uploader = metadata.get("og:site_name") or ""
            thumbnail_url = metadata.get("og:image") or metadata.get("twitter:image") or thumbnail_url
            if not title:
                match = re.search(r"<title[^>]*>(.*?)</title>", page, flags=re.IGNORECASE | re.DOTALL)
                if match:
                    title = html.unescape(re.sub(r"<[^>]+>", "", match.group(1))).strip()
        except Exception:
            return None

    title = re.sub(r"\s+", " ", title).strip()
    if not title:
        return None
    return {
        "title": title,
        "details": "  •  ".join(filter(None, [uploader, "Public page metadata only"])),
        "thumbnail_data": download_thumbnail_bytes(thumbnail_url),
        "thumbnail_url": thumbnail_url,
        "source": friendly_source_name(source),
        "status": "Title preview only — sign-in or age verification may be required to download.",
    }
