"""Error classification and natural language translation service for GGU_VDOD."""

from dataclasses import dataclass
import os
import re
import sys
import traceback
from typing import Any, Dict, Optional, Tuple


@dataclass
class ErrorDetails:
    """Structured error details with natural language explanations and actions."""

    code: str
    title: str
    simple_message: str
    recommendation: str
    severity: str  # 'CRITICAL', 'WARNING', 'INFO'
    sound_type: str  # 'MB_ICONHAND', 'MB_ICONSTOP', 'MB_ICONEXCLAMATION', 'MB_ICONASTERISK'
    raw_log: str
    action_type: Optional[str] = None  # 'retry', 'change_dir', 'auth_setup', 'ffmpeg_browse', 'close_browser', 'change_quality'


_STATUS_CODE_PATTERNS = {
    code: re.compile(rf"(?<!\d){code}(?!\d)")
    for code in ("403", "404", "407", "429", "451")
}


def classify_error(error_input: Any, context: Optional[str] = None) -> ErrorDetails:
    """Classify runtime exceptions or error strings into natural language ErrorDetails."""
    if isinstance(error_input, Exception):
        raw_log = f"{type(error_input).__name__}: {str(error_input)}\n" + "".join(
            traceback.format_exception(type(error_input), error_input, error_input.__traceback__)
        )
        err_str = f"{type(error_input).__name__} {str(error_input)}".strip()
    else:
        raw_log = str(error_input or "Unknown runtime error")
        err_str = str(error_input or "").strip()

    err_lower = err_str.lower()
    ctx_lower = (context or "").lower()
    full_text = f"{err_lower} {ctx_lower}"

    def has_code(code: str) -> bool:
        return _STATUS_CODE_PATTERNS[code].search(full_text) is not None

    # 1. DISK SPACE FULL
    if (
        "no space left on device" in full_text
        or "errno 28" in full_text
        or "disk full" in full_text
        or "insufficient disk space" in full_text
    ):
        return ErrorDetails(
            code="ERR_DISK_FULL",
            title="Disk Space Full",
            simple_message="Your target hard drive does not have enough free space to save this media file.",
            recommendation="Delete unnecessary files to free up disk space, or click 'Change Save Folder' to select another drive.",
            severity="CRITICAL",
            sound_type="MB_ICONSTOP",
            raw_log=raw_log,
            action_type="change_dir",
        )

    # 2. NETWORK CONNECTION LOST
    if any(
        kw in full_text
        for kw in (
            "connectionreseterror",
            "urlerror",
            "socket.timeout",
            "dnslookuperror",
            "networkunreachable",
            "nameresolutionerror",
            "connection refused",
            "network is unreachable",
            "timed out",
            "temporary failure in name resolution",
        )
    ):
        return ErrorDetails(
            code="ERR_NET_DISCONNECTED",
            title="Network Connection Lost",
            simple_message="Your internet or network connection was interrupted while communicating with the server.",
            recommendation="Check your Wi-Fi or Ethernet connection, then click 'Retry Download' to resume.",
            severity="WARNING",
            sound_type="MB_ICONHAND",
            raw_log=raw_log,
            action_type="retry",
        )

    # 3. CLOUDFLARE ANTI-BOT CHALLENGE (HTTP 403)
    if "cloudflare anti-bot challenge" in full_text or (has_code("403") and "impersonate" in full_text):
        return ErrorDetails(
            code="ERR_CLOUDFLARE_403",
            title="Cloudflare Protection Blocked",
            simple_message="The site's security system blocked automated requests with a Cloudflare anti-bot challenge.",
            recommendation="Chrome TLS impersonation is active. Try importing browser cookies under 'Advanced > Browser cookies' to pass verification.",
            severity="WARNING",
            sound_type="MB_ICONEXCLAMATION",
            raw_log=raw_log,
            action_type="auth_setup",
        )

    # 3b. GITHUB API RATE LIMIT (HTTP 403 rate limit exceeded)
    if "rate limit" in full_text and (has_code("403") or "api.github.com" in full_text or "github" in full_text):
        return ErrorDetails(
            code="ERR_GITHUB_RATE_LIMIT",
            title="Update Check Temporarily Blocked",
            simple_message="GitHub is temporarily limiting update checks from your network. This is not a problem with your PC or your settings.",
            recommendation="Wait about an hour and click 'Check for Updates' again. To update right now, open the Releases page in your browser and download the latest installer manually.",
            severity="WARNING",
            sound_type="MB_ICONEXCLAMATION",
            raw_log=raw_log,
            action_type="retry",
        )

    # 4. HTTP 429 TOO MANY REQUESTS / RATE LIMITED
    if has_code("429") or "too many requests" in full_text or "rate limit" in full_text:
        return ErrorDetails(
            code="ERR_RATE_LIMITED_429",
            title="Server Rate Limited (HTTP 429)",
            simple_message="The website is temporarily limiting downloads because too many requests were sent in a short time.",
            recommendation="Wait 1 to 2 minutes for the site rate limit to cool down, then click 'Retry Download'.",
            severity="WARNING",
            sound_type="MB_ICONEXCLAMATION",
            raw_log=raw_log,
            action_type="retry",
        )

    # 5. 18+ AGE RESTRICTED CONTENT
    if any(
        kw in full_text
        for kw in (
            "agerestricted",
            "confirm your age",
            "sign in to confirm your age",
            "adult content",
            "age-verification required",
        )
    ):
        return ErrorDetails(
            code="ERR_AGE_RESTRICTED",
            title="18+ Age Verification Required",
            simple_message="This video is age-restricted and requires age confirmation before it can be downloaded.",
            recommendation="Click 'Setup Verification / Auth' to import browser cookies or connect to Mailpit test inbox.",
            severity="INFO",
            sound_type="MB_ICONASTERISK",
            raw_log=raw_log,
            action_type="auth_setup",
        )

    # 6. PRIVATE OR MEMBER-ONLY CONTENT
    if any(
        kw in full_text
        for kw in (
            "private video",
            "sign in if you have been granted access",
            "members-only content",
            "members only",
            "channel members",
        )
    ):
        return ErrorDetails(
            code="ERR_PRIVATE_VIDEO",
            title="Private or Member-Only Content",
            simple_message="This video is marked private or restricted to authorized channel members only.",
            recommendation="Ensure your account has access on the site, then load authenticated cookies under 'Advanced > Browser cookies'.",
            severity="WARNING",
            sound_type="MB_ICONEXCLAMATION",
            raw_log=raw_log,
            action_type="auth_setup",
        )

    # 7. PLATFORM BOT-CHECK / SIGN-IN WALL (e.g. YouTube "confirm you're not a bot")
    if any(
        kw in full_text
        for kw in (
            "confirm you're not a bot",
            "not a bot",
            "sign in to confirm",
            "--cookies-from-browser",
            "use --cookies",
        )
    ):
        return ErrorDetails(
            code="ERR_BOT_CHECK",
            title="Platform Sign-In Verification",
            simple_message="The platform wants proof of a real browser session before serving this media. This happens regularly on YouTube and similar sites.",
            recommendation="Pick your browser under 'Browser cookies' in the Advanced panel, or store a session in the 'Account & Sessions' tab - then start the download again.",
            severity="WARNING",
            sound_type="MB_ICONEXCLAMATION",
            raw_log=raw_log,
            action_type="auth_setup",
        )

    # 7b. GENERIC HTTP 403 FORBIDDEN (fallback after specific 403 handlers)
    if has_code("403") or "forbidden" in full_text or "http error 403" in full_text:
        # Special handling for YouTube's common 403
        if "youtube" in full_text or "youtu.be" in full_text or "unable to download video data" in full_text:
            return ErrorDetails(
                code="ERR_YOUTUBE_403",
                title="YouTube Blocked the Download (403)",
                simple_message="YouTube refused this download. This is YouTube's bot-check, not your internet. It happens on most anonymous downloads right now.",
                recommendation="1. Click 'Retry Download' — the app will automatically retry with alternate YouTube clients (Android/iOS/TV).\n2. If it still fails: Advanced → Browser cookies → pick your browser (Chrome/Edge/Firefox) OR paste the YouTube link without &list=... part.\n3. Update yt-dlp: Help → Check for Updates & Dependencies → Update.",
                severity="WARNING",
                sound_type="MB_ICONEXCLAMATION",
                raw_log=raw_log,
                action_type="auth_setup",
            )
        return ErrorDetails(
            code="ERR_HTTP_FORBIDDEN",
            title="Access Denied by Server (403)",
            simple_message="The server refused to serve this request, usually because it wants a signed-in session or blocks automated tools.",
            recommendation="Load your browser cookies under 'Advanced > Browser cookies' and try again. If the site still refuses, open the link in your browser to confirm it works there.",
            severity="WARNING",
            sound_type="MB_ICONEXCLAMATION",
            raw_log=raw_log,
            action_type="auth_setup",
        )

    # 8. VIDEO REMOVED OR DELETED (HTTP 404)
    if has_code("404") or "video unavailable" in full_text or "removed by the uploader" in full_text:
        return ErrorDetails(
            code="ERR_VIDEO_DELETED_404",
            title="Video Removed or Deleted (404)",
            simple_message="The requested video link is no longer available because it was deleted or removed by the uploader.",
            recommendation="Verify that the link is correct in your browser or search for an alternative mirror upload.",
            severity="WARNING",
            sound_type="MB_ICONHAND",
            raw_log=raw_log,
            action_type=None,
        )

    # 8. REGIONAL OR GEOGRAPHIC BLOCK
    if "not made this video available in your country" in full_text or "geoblocked" in full_text or has_code("451"):
        return ErrorDetails(
            code="ERR_GEOBLOCKED",
            title="Country / Regional Block",
            simple_message="The video uploader has restricted viewing to specific countries or geographical regions.",
            recommendation="Configure an allowed country proxy under 'Advanced > Proxy' or use a VPN.",
            severity="WARNING",
            sound_type="MB_ICONEXCLAMATION",
            raw_log=raw_log,
            action_type=None,
        )

    # 9. FFMPEG MISSING
    if "ffmpeg not found" in full_text or "ffmpeg/ffprobe binary missing" in full_text or "ffmpeg_location" in full_text:
        return ErrorDetails(
            code="ERR_FFMPEG_MISSING",
            title="FFmpeg / FFprobe Binary Missing",
            simple_message="The FFmpeg encoder binary is missing or could not be loaded for media merging.",
            recommendation="Verify that ffmpeg.exe and ffprobe.exe are inside 'D:\\GGU_VDOD\\ffmpeg\\', or click 'Browse FFmpeg'.",
            severity="CRITICAL",
            sound_type="MB_ICONSTOP",
            raw_log=raw_log,
            action_type="ffmpeg_browse",
        )

    # 10. FORMAT OR RESOLUTION UNAVAILABLE
    if "requested format is not available" in full_text or "no video/audio format matching" in full_text:
        return ErrorDetails(
            code="ERR_FORMAT_UNAVAILABLE",
            title="Format / Resolution Unavailable",
            simple_message="The exact requested video resolution or audio codec is not offered for this specific video.",
            recommendation="Change Quality to 'Best available' or use 'List Formats' under Advanced settings to choose a valid format ID.",
            severity="INFO",
            sound_type="MB_ICONASTERISK",
            raw_log=raw_log,
            action_type="change_quality",
        )

    # 11. PERMISSION DENIED (WinError 5)
    if "permissionerror" in full_text or "winerror 5" in full_text or "access is denied" in full_text:
        return ErrorDetails(
            code="ERR_PERMISSION_DENIED",
            title="Folder Access Denied (Permission Error)",
            simple_message="Windows denied permission to save files into the selected save directory.",
            recommendation="Click 'Change Save Folder' and pick a directory in your user folder (e.g., Downloads or Videos).",
            severity="CRITICAL",
            sound_type="MB_ICONSTOP",
            raw_log=raw_log,
            action_type="change_dir",
        )

    # 12. COOKIE DATABASE LOCKED (DPAPI)
    if (
        "failed to decrypt with dpapi" in full_text
        or "cookie database locked" in full_text
        or "could not copy chrome cookie database" in full_text
        or "could not copy edge cookie database" in full_text
    ):
        return ErrorDetails(
            code="ERR_DPAPI_COOKIE_LOCK",
            title="Browser Cookie Database Locked",
            simple_message="Chrome or your web browser is currently open and locking its cookie database file.",
            recommendation="Close Chrome/Edge completely, or use 'Import and validate' with a Netscape cookies.txt file.",
            severity="WARNING",
            sound_type="MB_ICONEXCLAMATION",
            raw_log=raw_log,
            action_type="close_browser",
        )

    # 13. PROXY FAILED
    if "proxyerror" in full_text or "proxy connection refused" in full_text or has_code("407"):
        return ErrorDetails(
            code="ERR_PROXY_FAILED",
            title="Proxy Connection Failed",
            simple_message="Could not connect to the proxy server configured in Advanced settings.",
            recommendation="Check that the proxy host, port, and credentials are correct, or clear the proxy field.",
            severity="WARNING",
            sound_type="MB_ICONHAND",
            raw_log=raw_log,
            action_type=None,
        )

    # 13b. FFMPEG POSTPROCESSING / MERGE FAILED
    if (
        "postprocessing:" in full_text
        or "postprocessing:" in err_lower
        or "error opening input files" in full_text
        or "invalid data found when processing input" in full_text
        or "muxing" in full_text and "error" in full_text
    ):
        return ErrorDetails(
            code="ERR_POSTPROCESS_FAILED",
            title="Conversion / Merge Step Failed",
            simple_message="The media was fetched but FFmpeg could not process or merge it. The downloaded data was likely incomplete, corrupted, or the site served an error page instead of the real stream.",
            recommendation="Click 'Retry Download' once. If it fails the same way again, switch to a different output format or quality (some sites serve broken streams for certain formats), and make sure the custom codec/bitrate fields are 'Auto' if you enabled conversion.",
            severity="WARNING",
            sound_type="MB_ICONEXCLAMATION",
            raw_log=raw_log,
            action_type="retry",
        )

    # 14. CORRUPTED STREAM OR FILE
    if "0-byte" in full_text or "integrity check failed" in full_text or "corrupt stream" in full_text:
        return ErrorDetails(
            code="ERR_CORRUPT_STREAM",
            title="Media Stream Integrity Failed",
            simple_message="The downloaded output file is incomplete, 0 bytes, or failed media health inspection.",
            recommendation="Click 'Retry Download' to re-fetch the stream segments from the server.",
            severity="WARNING",
            sound_type="MB_ICONHAND",
            raw_log=raw_log,
            action_type="retry",
        )

    # 15. FRAGMENT FAILED
    if "fragment download failed" in full_text or "hls/dash segment" in full_text:
        return ErrorDetails(
            code="ERR_FRAGMENT_FAILED",
            title="Stream Fragment Download Drop",
            simple_message="One or more live stream fragments (HLS/DASH) timed out during download.",
            recommendation="Click 'Retry Download'. Downloading will automatically resume from the last saved fragment.",
            severity="WARNING",
            sound_type="MB_ICONEXCLAMATION",
            raw_log=raw_log,
            action_type="retry",
        )

    # 16. UNHANDLED EXCEPTION (FALLBACK)
    return ErrorDetails(
        code="ERR_UNHANDLED_EXCEPTION",
        title="Unexpected Application Error",
        simple_message="An unexpected internal error occurred during the operation.",
        recommendation="A sanitized diagnostic log has been recorded. Click 'Copy Details' to share with support or try retrying.",
        severity="CRITICAL",
        sound_type="MB_ICONSTOP",
        raw_log=raw_log,
        action_type="retry",
    )
