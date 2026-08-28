"""Headless download engine: yt-dlp orchestration without any UI imports.

The UI submits a list of URLs plus a settings dict; the engine reports back
through plain callables (log/status/progress/error/item events). This keeps
the download pipeline testable and reusable without a running Qt loop.
"""

import os
import re
import subprocess
import sys
import time
import urllib.parse

from ..config.paths import (
    get_default_ffmpeg_dir, get_default_ffmpeg_path,
    get_default_output_dir, get_default_qjs_path,
)
from ..conversion.options import (
    FFmpegCustomAudioConvertPP, FFmpegCustomReencodePP, audio_conversion_args,
    clean_video_sidecars, output_template, video_conversion_args,
)
from ..core.constants import (
    AUDIO_FORMAT_EXTENSIONS, HEIGHT_MAP, MAX_RETRIES, RETRY_WAIT_SECONDS,
    VIDEO_FORMAT_EXTENSIONS,
)
from ..core.formatting import format_bytes, format_rate
from ..services.network import (
    explain_download_error, looks_like_bot_check, looks_like_connection_error,
    looks_like_cookie_database_error, looks_like_subtitle_rate_limit,
)


class DownloadCancelled(Exception):
    """Raised from a progress hook to stop the active yt-dlp operation."""


def kill_own_ffmpeg_children():
    """Terminate only ffmpeg/ffprobe processes spawned by this application,
    never unrelated system-wide instances owned by other programs."""
    if sys.platform != "win32":
        return
    try:
        my_pid = os.getpid()
        query = (
            "powershell", "-NoProfile", "-NonInteractive", "-Command",
            "Get-CimInstance Win32_Process -Filter \"Name='ffmpeg.exe' OR Name='ffprobe.exe'\" | "
            f"Where-Object {{ $_.ParentProcessId -eq {my_pid} }} | "
            "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }",
        )
        subprocess.run(query, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
    except Exception:
        pass


def format_eta_clean(eta_seconds) -> str:
    """Format ETA seconds into clean rounded figures (e.g. '5m 49s' or '45s')."""
    if not eta_seconds or float(eta_seconds) <= 0:
        return "—"
    try:
        secs = int(round(float(eta_seconds)))
        if secs < 60:
            return f"{secs}s"
        mins = secs // 60
        rem_secs = secs % 60
        if mins < 60:
            return f"{mins}m {rem_secs:02d}s"
        hours = mins // 60
        rem_mins = mins % 60
        return f"{hours}h {rem_mins:02d}m"
    except Exception:
        return f"{eta_seconds}s"


def load_yt_dlp():
    """Import yt-dlp lazily so cold start does not pay for it before a download.
    Honors a module-level injection (used by tests to supply fakes)."""
    global yt_dlp
    if yt_dlp is not None:
        return yt_dlp
    try:
        import yt_dlp as _yt_dlp
    except ImportError:
        return None
    yt_dlp = _yt_dlp
    return yt_dlp


yt_dlp = None

PLAYLIST_EXPANSION_CAP = 500


def expand_playlist_urls(urls, log=None, max_items=PLAYLIST_EXPANSION_CAP):
    """Expand playlist URLs into individual (title, url) pairs via cheap flat extraction.

    Non-playlist URLs pass through with an empty title. Anything that fails to
    expand is kept as-is so the normal download path can report a proper error.
    """
    yt_dlp_mod = load_yt_dlp()
    if yt_dlp_mod is None or not urls:
        return [("", u) for u in urls]
    expanded = []
    max_items = max(1, int(max_items or PLAYLIST_EXPANSION_CAP))
    seen_counts = {}
    try:
        with yt_dlp_mod.YoutubeDL({"quiet": True, "no_warnings": True, "extract_flat": True}) as ydl:
            for url in urls:
                info = None
                try:
                    info = ydl.extract_info(url, download=False)
                except Exception as error:
                    if log:
                        log(f"[INFO] Playlist pre-check skipped for {url}: {error}")
                if isinstance(info, dict) and info.get("_type") == "playlist" and info.get("entries"):
                    entries = []
                    for entry in info["entries"]:
                        if not isinstance(entry, dict):
                            continue
                        entry_url = (
                            entry.get("webpage_url")
                            or entry.get("original_url")
                            or entry.get("url")
                            or ""
                        )
                        if entry_url.startswith("//"):
                            entry_url = f"https:{entry_url}"
                        if not urllib.parse.urlparse(entry_url).scheme:
                            ie_key = str(entry.get("ie_key") or "").lower()
                            if "youtube" in ie_key:
                                entry_url = f"https://www.youtube.com/watch?v={entry_url}"
                        if not entry_url.startswith(("http://", "https://")):
                            continue
                        if not entry_url:
                            continue
                        entries.append((entry.get("title") or entry_url, entry_url))
                        if len(entries) >= max_items:
                            break
                    if log:
                        log(
                            f"[INFO] Playlist detected: expanding into {len(entries)} item(s)"
                            + (" (capped)" if len(info.get("entries") or []) > len(entries) else "")
                        )
                    for title, entry_url in entries:
                        seen_counts[entry_url] = seen_counts.get(entry_url, 0) + 1
                        suffix = f" #{seen_counts[entry_url]}" if seen_counts[entry_url] > 1 else ""
                        expanded.append((f"{title}{suffix}", entry_url))
                else:
                    expanded.append(("", url))
    except Exception:
        return [("", u) for u in urls]
    # Deduplicate identical media URLs while keeping the first title.
    result = []
    seen = set()
    for title, url in expanded:
        if url in seen:
            continue
        seen.add(url)
        result.append((title, url))
    return result


class YTDLPEventLogger:
    """Forward yt-dlp messages into a sink callable, throttled every 10 seconds."""

    def __init__(self, emit):
        self._emit = emit
        self._last_log_time = 0

    def debug(self, message):
        if not message:
            return
        text = str(message).strip()
        if text.startswith("[download]") or text.startswith("[debug]") or "frag" in text.lower():
            return
        now = time.time()
        if now - self._last_log_time >= 10.0:
            self._last_log_time = now
            clean_msg = re.sub(r"^\[[^\]]+\]\s*", "", text)
            self._emit(f"[STATUS] {clean_msg}")

    def warning(self, message):
        text = str(message or "").strip()
        if "No supported JavaScript runtime could be found" in text or "JavaScript runtime has been deprecated" in text:
            return
        clean_msg = re.sub(r"^\[[^\]]+\]\s*", "", text)
        self._emit(f"[WARNING] {clean_msg}")

    def error(self, message):
        clean_msg = re.sub(r"^\[[^\]]+\]\s*", "", str(message or "").strip())
        self._emit(f"[ERROR] {clean_msg}")


class DownloadEngine:
    """Runs a download queue and reports structured events through callables."""

    def __init__(self, settings, log=None, status=None, progress=None, error=None, cancel=None):
        self.settings = dict(settings or {})
        self._log = log or (lambda message: None)
        self.last_result = {}
        self._status = status or (lambda text: None)
        self._progress = progress or (lambda data: None)
        self._error = error or (lambda url, message: None)
        self._cancel = cancel or (lambda: False)

    def cancelled(self) -> bool:
        return bool(self._cancel())

    @staticmethod
    def _disk_guard_message(free_bytes, required_bytes):
        if free_bytes >= required_bytes:
            return ""
        return (
            "insufficient disk space: need "
            f"{format_bytes(required_bytes)}, only {format_bytes(free_bytes)} free on the target drive"
        )

    def _verify_integrity(self, final_file):
        """Fail broken or placeholder outputs instead of reporting false success."""
        if not final_file or not os.path.isfile(final_file):
            raise ValueError("media integrity check failed: output file was not created")
        size = os.path.getsize(final_file)
        if size < 32 * 1024:
            raise ValueError(
                f"media integrity check failed: output is only {format_bytes(size)} - likely a broken placeholder"
            )
        try:
            from ..services.probe import get_ffprobe_binary_path, probe_media_file
            if get_ffprobe_binary_path():
                res = probe_media_file(final_file, timeout=20)
                if res.get("success") and not res.get("is_healthy", True):
                    raise ValueError("media integrity check failed: ffprobe reports unhealthy streams")
        except ValueError:
            raise
        except Exception:
            pass

    def run_queue(self, urls):
        """Process every URL sequentially; returns (success_count, failure_count)."""
        urls = list(urls)
        if load_yt_dlp() is None:
            error_message = "yt-dlp library is missing."
            self._log(f"[ERROR] {error_message}")
            self._error("", error_message)
            return 0, len(urls)

        success_count = 0
        failure_count = 0

        for index, url in enumerate(urls, 1):
            if self.cancelled():
                self._log("[INFO] Download operation cancelled by user.")
                break

            self._on_item_started(url, index, len(urls))
            self._log(f"\n--- [Queue {index}/{len(urls)}] Processing {url} ---")
            self._status(f"Downloading item {index} of {len(urls)}...")

            success = self._download_with_retries(url)
            self._on_item_finished(url, success)
            if success:
                success_count += 1
            else:
                failure_count += 1

        return success_count, failure_count

    def _on_item_started(self, url, index, total):
        pass  # overridden by adapters that need per-item start events

    def _on_item_finished(self, url, success):
        pass  # overridden by adapters that need per-item completion events

    def _download_with_retries(self, url):
        """Retry recoverable failures while keeping the final error visible."""
        settings = dict(self.settings)
        self.last_result = {}
        cookie_fallback_used = False
        subtitle_fallback_used = False
        botcheck_fallback_used = False

        for attempt in range(1, MAX_RETRIES + 1):
            if self.cancelled():
                self._log("[INFO] Item cancelled.")
                return False
            try:
                self.process_url(url, settings)
                return True
            except DownloadCancelled:
                self._log("[INFO] Item cancelled.")
                return False
            except Exception as error:
                if (
                    not cookie_fallback_used
                    and settings.get("cookies_browser") not in (None, "", "None")
                    and looks_like_cookie_database_error(error)
                ):
                    cookie_fallback_used = True
                    settings["cookies_browser"] = "None"
                    self._log(
                        "[WARNING] Browser cookies could not be read; retrying without them. "
                        "Close the browser or use cookies.txt if sign-in is required."
                    )
                    continue
                if (
                    not subtitle_fallback_used
                    and settings.get("embed_subtitles")
                    and looks_like_subtitle_rate_limit(error)
                ):
                    subtitle_fallback_used = True
                    settings["embed_subtitles"] = False
                    self._log(
                        "[WARNING] Subtitle service rate-limited this request; retrying the media without subtitles."
                    )
                    continue
                if (
                    not botcheck_fallback_used
                    and settings.get("cookies_browser") in (None, "", "None")
                    and not settings.get("cookies_file")
                    and looks_like_bot_check(error)
                ):
                    botcheck_fallback_used = True
                    settings["youtube_alt_clients"] = True
                    self._log(
                        "[WARNING] Platform bot-check detected; retrying once with alternate "
                        "YouTube clients (TV/Safari). For reliable access configure browser cookies."
                    )
                    continue
                if looks_like_connection_error(error) and attempt < MAX_RETRIES:
                    self._status(f"Connection issue; retrying ({attempt}/{MAX_RETRIES})...")
                    self._log(
                        f"[WARNING] Network error. Retrying in {RETRY_WAIT_SECONDS}s "
                        f"({attempt}/{MAX_RETRIES})..."
                    )
                    for _ in range(RETRY_WAIT_SECONDS * 10):
                        if self.cancelled():
                            break
                        time.sleep(0.1)
                    continue
                self._log(f"[ERROR] Failed {url}: {explain_download_error(error)}")
                self._error(url, str(error))
                return False
        return False

    def process_url(self, url, settings):
        """Download and post-process one URL with the given flat settings dict."""
        output_dir = settings.get("output_dir") or get_default_output_dir()
        os.makedirs(output_dir, exist_ok=True)
        is_audio = settings.get("format") == "audio"
        target_ext = (AUDIO_FORMAT_EXTENSIONS if is_audio else VIDEO_FORMAT_EXTENSIONS).get(
            str(settings.get("output_format") or "").upper(), ""
        ).lower()
        if not target_ext:
            raise ValueError("Choose a valid output format before downloading.")

        last_emit = [0.0]
        disk_state = {"checked": False}

        def progress_hook(d):
            if self.cancelled():
                raise DownloadCancelled("Download cancelled by user")
            status = d.get("status")
            if status == "downloading":
                # yt-dlp fires this per fragment/chunk; cap UI updates at ~10 Hz
                now = time.monotonic()
                if now - last_emit[0] < 0.1:
                    return
                last_emit[0] = now
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                if total and not disk_state["checked"]:
                    # First time the real size is known: compare against free space.
                    disk_state["checked"] = True
                    try:
                        import shutil
                        free = shutil.disk_usage(output_dir).free
                        msg = self._disk_guard_message(free, int(total * 1.05) + (64 << 20))
                        if msg:
                            raise OSError(msg)
                    except OSError:
                        raise
                    except Exception:
                        pass
                downloaded = d.get("downloaded_bytes") or 0
                speed = d.get("speed") or 0
                eta = d.get("eta") or 0

                percent = (downloaded / total * 100.0) if total > 0 else 0
                self._progress({
                    "status": "Downloading...",
                    "progress": percent,
                    "download_rate": format_rate(speed),
                    "upload_rate": "0 B/s",
                    "transferred": f"{format_bytes(downloaded)} / {format_bytes(total)}" if total else format_bytes(downloaded),
                    "eta": format_eta_clean(eta),
                })
            elif status == "finished":
                self._log("[INFO] Primary download complete. Finalizing media file...")

        ydl_opts = {
            "outtmpl": output_template(settings, output_dir, target_ext),
            "progress_hooks": [progress_hook],
            "noplaylist": settings.get("single_only", True),
            "quiet": True,
            "no_warnings": False,
            "age_limit": 99,
            "logger": YTDLPEventLogger(self._log),
            "retries": MAX_RETRIES,
            "fragment_retries": MAX_RETRIES,
            "file_access_retries": MAX_RETRIES,
            "concurrent_fragment_downloads": 4,
            "postprocessors": [],
        }

        try:
            import shutil
            js_runtimes = {}
            qjs_bin = get_default_qjs_path()
            if qjs_bin and os.path.exists(qjs_bin):
                js_runtimes["quickjs"] = {"path": qjs_bin}
            for rt in ["node", "deno", "bun", "qjs"]:
                rt_path = shutil.which(rt)
                if rt_path:
                    key = "quickjs" if rt == "qjs" else rt
                    js_runtimes[key] = {"path": rt_path}
            if js_runtimes:
                ydl_opts["js_runtimes"] = js_runtimes
        except Exception:
            pass

        extractor_args = {}
        try:
            from yt_dlp.networking.impersonate import ImpersonateTarget
            target = ImpersonateTarget.from_str("chrome")
            from yt_dlp.networking._curlcffi import CurlCffiRH
            if CurlCffiRH.is_supported_target(target):
                ydl_opts["impersonate"] = target
                extractor_args["generic"] = ["impersonate"]
        except Exception:
            pass
        if extractor_args:
            ydl_opts["extractor_args"] = extractor_args
        if settings.get("youtube_alt_clients"):
            # Alternate clients frequently bypass YouTube's anonymous bot-check.
            ydl_opts.setdefault("extractor_args", {}).setdefault("youtube", {})["player_client"] = [
                "tv", "web_safari", "web_embedded",
            ]

        # Automatic DPAPI Account & Session Injection for current target URL
        try:
            target_domain = urllib.parse.urlparse(url).netloc
            if target_domain:
                from ..auth.manager import AuthManager
                session = AuthManager.resolve_domain_session(target_domain)
                if session:
                    account_lbl = session.get("account_label")
                    sec = session.get("secret")
                    if account_lbl and sec:
                        ydl_opts["username"] = account_lbl
                        ydl_opts["password"] = sec
                        self._log(f"[INFO] Injected stored DPAPI account credentials for domain: {target_domain} ({account_lbl})")
                    else:
                        self._log(f"[INFO] Injected active domain session for: {target_domain}")
        except Exception:
            pass

        ffmpeg_dir = get_default_ffmpeg_dir()
        ffmpeg_path = settings.get("ffmpeg_path") or get_default_ffmpeg_path()
        target_ffmpeg_dir = ffmpeg_dir if (os.path.isdir(ffmpeg_dir) and os.path.exists(os.path.join(ffmpeg_dir, "ffmpeg.exe"))) else (os.path.dirname(ffmpeg_path) if (ffmpeg_path and os.path.exists(ffmpeg_path)) else None)

        if target_ffmpeg_dir:
            path_entries = os.environ.get("PATH", "").split(os.pathsep)
            if target_ffmpeg_dir not in path_entries:
                os.environ["PATH"] = target_ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")
            ydl_opts["ffmpeg_location"] = target_ffmpeg_dir
            ffprobe_status = "(ffmpeg.exe & ffprobe.exe)" if os.path.exists(os.path.join(target_ffmpeg_dir, "ffprobe.exe")) else "(ffmpeg.exe)"
            self._log(f"[INFO] Using FFmpeg directory: {target_ffmpeg_dir} {ffprobe_status}")
        else:
            self._log("[WARNING] FFmpeg binary not found! Video merging and container conversion may be limited.")

        # Cookies configuration
        browser = settings.get("cookies_browser")
        cookies_file = settings.get("cookies_file")
        if cookies_file and os.path.exists(cookies_file):
            ydl_opts["cookiefile"] = cookies_file
        elif browser and browser not in ("None", "custom", "Custom cookies.txt file..."):
            ydl_opts["cookiesfrombrowser"] = (browser.lower(),)

        # Proxy configuration
        proxy = settings.get("proxy")
        if proxy:
            ydl_opts["proxy"] = proxy

        # Subtitles configuration
        if settings.get("embed_subtitles"):
            ydl_opts["writesubtitles"] = True
            if settings.get("auto_subtitles"):
                ydl_opts["writeautomaticsub"] = True
            sub_langs = [s.strip() for s in settings.get("subtitle_langs", "en").split(",") if s.strip()]
            ydl_opts["subtitleslangs"] = sub_langs or ["en"]
            ydl_opts["postprocessors"].append({"key": "FFmpegEmbedSubtitle"})

        # Metadata & thumbnail embedding
        if settings.get("embed_metadata", True):
            ydl_opts["postprocessors"].append({"key": "FFmpegMetadata", "add_chapters": True, "add_metadata": True})
        if settings.get("embed_thumbnail"):
            ydl_opts["writethumbnail"] = True
            ydl_opts["postprocessors"].append({"key": "FFmpegThumbnailsConvertor", "format": "jpg"})
            ydl_opts["postprocessors"].append({"key": "EmbedThumbnail"})

        # Live stream option
        if settings.get("live_start_from_beginning"):
            ydl_opts["live_from_start"] = True

        # Timestamp Cutter (start & end time range clipping)
        start_time_str = settings.get("start_time")
        end_time_str = settings.get("end_time")
        from ..services.probe import parse_time_str_to_seconds
        start_sec = parse_time_str_to_seconds(start_time_str)
        end_sec = parse_time_str_to_seconds(end_time_str)
        if start_sec is not None or end_sec is not None:
            s_val = start_sec if start_sec is not None else 0.0
            e_val = end_sec if end_sec is not None else None

            ffmpeg_trim_args = []
            if s_val > 0:
                ffmpeg_trim_args.extend(["-ss", str(s_val)])
            if e_val is not None:
                ffmpeg_trim_args.extend(["-to", str(e_val)])

            if ffmpeg_trim_args:
                ydl_opts["postprocessor_args"] = {"ffmpeg": ffmpeg_trim_args}
                self._log(f"[INFO] Video Timestamp Cutter active: Clipping range [{start_time_str or '00:00'} -> {end_time_str or 'END'}]")

        # Format & Quality selection
        exact_format_id = settings.get("exact_format_id")
        if exact_format_id:
            ydl_opts["format"] = exact_format_id
        elif is_audio:
            ydl_opts["format"] = "bestaudio/best"
        else:
            quality = settings.get("quality", "Best available")
            height = HEIGHT_MAP.get(quality)
            if height:
                ydl_opts["format"] = (
                    f"bestvideo[height={height}]+bestaudio/best[height={height}]"
                    f"/bestvideo[height<={height}]+bestaudio/best[height<={height}]"
                    f"/best[height<={height}]/best"
                )
            else:
                ydl_opts["format"] = "bestvideo+bestaudio/best"

        # Local output conversion. Audio uses the custom converter so every UI
        # target (including OGG, WMA, and AIFF) is handled consistently.
        if is_audio:
            audio_args = audio_conversion_args(settings, target_ext)
            video_args = []
        else:
            video_args = video_conversion_args(settings, target_ext)
            if not video_args:
                # No custom re-encode requested: let yt-dlp remux/recode directly.
                ydl_opts["recode_video"] = target_ext
                ydl_opts["merge_output_format"] = (
                    target_ext if target_ext in ("mp4", "mkv", "webm", "ogv", "flv", "avi", "mov", "m4v", "ts", "3gp") else "mkv"
                )

        started_at = time.time()
        yt_dlp_mod = load_yt_dlp()
        if not yt_dlp_mod:
            raise RuntimeError("yt-dlp library is missing.")
        with yt_dlp_mod.YoutubeDL(ydl_opts) as ydl:
            if is_audio:
                ydl.add_post_processor(FFmpegCustomAudioConvertPP(ydl, target_ext, audio_args))
            elif video_args:
                ydl.add_post_processor(FFmpegCustomReencodePP(ydl, target_ext, video_args))
            info = ydl.extract_info(url, download=True)

        if settings.get("clean_sidecars", True):
            clean_video_sidecars(output_dir, started_at, target_ext)
        final_file = info.get("filepath") if isinstance(info, dict) else ""
        self.last_result = {"output_dir": output_dir, "final_file": final_file or ""}
        self._verify_integrity(final_file)
        self._report_selected_format(info, settings, target_ext)
        self._log(f"[SUCCESS] Successfully processed: {url}")

    def _report_selected_format(self, info, settings, target_ext):
        """Make actual source and final conversion choices visible in the log."""
        if not isinstance(info, dict):
            return
        selected = info.get("requested_formats") or [info]
        stream_details = []
        selected_heights = []
        for item in selected:
            if not isinstance(item, dict):
                continue
            height = item.get("height")
            if height:
                selected_heights.append(height)
            role = "video" if item.get("vcodec") not in (None, "none") else "audio"
            resolution = item.get("resolution") or (f"{height}p" if height else "audio")
            codec = item.get("vcodec") if role == "video" else item.get("acodec")
            stream_details.append(
                f"{role}: id={item.get('format_id', '?')}, ext={item.get('ext', '?')}, "
                f"resolution={resolution}, codec={codec}"
            )
        if stream_details:
            self._log("[FORMAT] Selected source " + " | ".join(stream_details))
        requested_height = HEIGHT_MAP.get(settings.get("quality"))
        if requested_height and selected_heights and max(selected_heights) < requested_height:
            available = sorted(
                {int(f.get("height")) for f in (info.get("formats") or [])
                 if isinstance(f, dict) and f.get("height")}
            )
            closest = max([h for h in available if h <= requested_height], default=None)
            self._log(
                f"[FORMAT] Requested {requested_height}p; source only provided {max(selected_heights)}p. "
                "The highest accessible lower-quality stream was used."
            )
            if available:
                self._log(
                    f"[FORMAT] Available heights: {', '.join(map(str, available))}. "
                    f"Closest match to your request: {closest}p"
                )
        conversion_resolution = settings.get("conversion_resolution", "Source")
        if conversion_resolution != "Source":
            self._log(
                f"[FORMAT] Final output is intentionally scaled to {conversion_resolution}."
            )
        self._log(f"[FORMAT] Final container target: {target_ext.upper()}")
