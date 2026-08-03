"""Pure and low-level helpers for media preview metadata."""

import os
import re
import urllib.parse
import urllib.request

from ..core.constants import APP_NAME


def youtube_video_id(url):
    """Return the selected YouTube video ID, even when playlist parameters exist."""
    try:
        parsed = urllib.parse.urlsplit(url)
        host = parsed.netloc.casefold().split(":", 1)[0]
        if host in {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com"}:
            return urllib.parse.parse_qs(parsed.query).get("v", [""])[0]
        if host in {"youtu.be", "www.youtu.be"}:
            return parsed.path.strip("/").split("/", 1)[0]
    except (TypeError, ValueError):
        pass
    return ""


def preview_target_url(url):
    """Strip YouTube playlist context while preserving the selected video."""
    video_id = youtube_video_id(url)
    if video_id:
        return f"https://www.youtube.com/watch?v={urllib.parse.quote(video_id)}"
    return url


def best_thumbnail_url(info):
    thumbnails = [item for item in (info.get("thumbnails") or []) if item.get("url")]
    if thumbnails:
        def size_score(item):
            try:
                width = int(item.get("width") or 0)
                height = int(item.get("height") or 0)
                preference = float(item.get("preference") or 0)
            except (TypeError, ValueError):
                width = height = preference = 0
            return width * height, width, height, preference
        return max(thumbnails, key=size_score).get("url")
    return info.get("thumbnail") or ""


def download_thumbnail_bytes(thumbnail_url, max_bytes=12 * 1024 * 1024):
    if not thumbnail_url:
        return None
    try:
        request = urllib.request.Request(thumbnail_url, headers={"User-Agent": APP_NAME})
        with urllib.request.urlopen(request, timeout=8) as response:
            return response.read(max_bytes)
    except Exception:
        return None


def friendly_source_name(source):
    normalized = (source or "").casefold()
    source_names = {
        "youtube": "YouTube", "twitter": "X (Twitter)", "facebook": "Facebook",
        "instagram": "Instagram", "tiktok": "TikTok", "vimeo": "Vimeo", "twitch": "Twitch",
        "reddit": "Reddit", "dailymotion": "Dailymotion", "soundcloud": "SoundCloud",
    }
    for key, label in source_names.items():
        if key in normalized:
            return label
    return re.sub(r"[_-]+", " ", source or "Unknown source").strip().title()


def format_duration(seconds):
    if not seconds:
        return ""
    try:
        seconds = int(seconds)
    except (TypeError, ValueError):
        return ""
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes}:{seconds:02d}"
