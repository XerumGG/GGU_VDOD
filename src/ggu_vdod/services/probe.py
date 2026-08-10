"""FFprobe multimedia stream analyzer service module."""

import json
import os
import re
import subprocess
import sys
from typing import Any, Dict, List, Optional, Tuple

from ..config.paths import get_default_ffprobe_path


def get_ffprobe_binary_path() -> Optional[str]:
    """Return verified ffprobe.exe binary path."""
    exe = get_default_ffprobe_path()
    if exe and os.path.exists(exe):
        return exe
    return None


def parse_time_str_to_seconds(time_str: str) -> Optional[float]:
    """Parse time string like '90', '1:30', '01:30', or '00:01:30' into float seconds."""
    if not time_str or not isinstance(time_str, str):
        return None
    time_str = time_str.strip()
    if not time_str:
        return None
    try:
        parts = time_str.split(":")
        if len(parts) == 1:
            return float(parts[0])
        elif len(parts) == 2:
            mins, secs = float(parts[0]), float(parts[1])
            return mins * 60 + secs
        elif len(parts) == 3:
            hrs, mins, secs = float(parts[0]), float(parts[1]), float(parts[2])
            return hrs * 3600 + mins * 60 + secs
    except Exception:
        pass
    return None


def parse_fraction_fps(fps_str: str) -> str:
    """Convert fraction string like '60/1' or '30000/1001' into clean FPS display."""
    if not fps_str or fps_str == "0/0":
        return "—"
    try:
        if "/" in fps_str:
            num, den = fps_str.split("/")
            if float(den) > 0:
                val = float(num) / float(den)
                return f"{val:.2f}".rstrip("0").rstrip(".")
        val = float(fps_str)
        return f"{val:.2f}".rstrip("0").rstrip(".")
    except Exception:
        return str(fps_str)


def format_duration_seconds(sec_val: Any) -> str:
    """Format duration in seconds to HH:MM:SS or MM:SS."""
    if sec_val is None:
        return "—"
    try:
        secs = int(round(float(sec_val)))
        if secs <= 0:
            return "—"
        mins = secs // 60
        rem_secs = secs % 60
        if mins < 60:
            return f"{mins:02d}:{rem_secs:02d}"
        hours = mins // 60
        rem_mins = mins % 60
        return f"{hours:02d}:{rem_mins:02d}:{rem_secs:02d}"
    except Exception:
        return str(sec_val)


def probe_media_file(target: str, timeout: int = 10) -> Dict[str, Any]:
    """Inspect media file or stream URL using ffprobe.exe and return structured JSON dictionary."""
    if not target or not isinstance(target, str):
        return {"success": False, "error": "Invalid target path or URL"}

    ffprobe_exe = get_ffprobe_binary_path()
    if not ffprobe_exe:
        return {"success": False, "error": "ffprobe.exe binary not found"}

    cmd = [
        ffprobe_exe,
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        "-show_chapters",
        target,
    ]

    try:
        res = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        if res.returncode != 0:
            err_msg = res.stderr.strip() or f"ffprobe exited with code {res.returncode}"
            return {"success": False, "error": err_msg}

        raw_data = json.loads(res.stdout)
        format_obj = raw_data.get("format", {})
        streams_list = raw_data.get("streams", [])
        chapters_list = raw_data.get("chapters", [])

        video_streams: List[Dict[str, Any]] = []
        audio_streams: List[Dict[str, Any]] = []
        subtitle_streams: List[Dict[str, Any]] = []

        for st in streams_list:
            codec_type = st.get("codec_type")
            if codec_type == "video":
                # Skip attached picture embedded thumbnails unless main video stream
                disposition = st.get("disposition", {})
                is_attached_pic = bool(disposition.get("attached_pic"))
                video_streams.append({
                    "index": st.get("index"),
                    "codec_name": st.get("codec_name", "?").upper(),
                    "codec_long_name": st.get("codec_long_name", ""),
                    "profile": st.get("profile", "—"),
                    "width": st.get("width", 0),
                    "height": st.get("height", 0),
                    "resolution": f"{st.get('width', 0)}x{st.get('height', 0)}" if st.get("width") else "—",
                    "fps": parse_fraction_fps(st.get("r_frame_rate") or st.get("avg_frame_rate")),
                    "pix_fmt": st.get("pix_fmt", "—"),
                    "bit_rate": st.get("bit_rate"),
                    "aspect_ratio": st.get("display_aspect_ratio") or st.get("sample_aspect_ratio") or "—",
                    "attached_pic": is_attached_pic,
                })
            elif codec_type == "audio":
                audio_streams.append({
                    "index": st.get("index"),
                    "codec_name": st.get("codec_name", "?").upper(),
                    "codec_long_name": st.get("codec_long_name", ""),
                    "sample_rate": f"{st.get('sample_rate', '—')} Hz" if st.get("sample_rate") else "—",
                    "channels": st.get("channels", 0),
                    "channel_layout": st.get("channel_layout") or (
                        "Stereo" if st.get("channels") == 2 else ("Mono" if st.get("channels") == 1 else f"{st.get('channels', 0)}ch")
                    ),
                    "bit_rate": st.get("bit_rate"),
                    "language": st.get("tags", {}).get("language", "—") if isinstance(st.get("tags"), dict) else "—",
                })
            elif codec_type == "subtitle":
                subtitle_streams.append({
                    "index": st.get("index"),
                    "codec_name": st.get("codec_name", "?").upper(),
                    "language": st.get("tags", {}).get("language", "—") if isinstance(st.get("tags"), dict) else "—",
                })

        duration = format_obj.get("duration")
        size = format_obj.get("size")
        format_name = format_obj.get("format_long_name") or format_obj.get("format_name") or "—"
        tags = format_obj.get("tags", {}) if isinstance(format_obj.get("tags"), dict) else {}

        # Stream Health Check
        is_healthy = bool(
            (video_streams or audio_streams)
            and (duration is None or float(duration) > 0)
        )

        return {
            "success": True,
            "filename": os.path.basename(target),
            "filepath": target,
            "format_name": format_name,
            "duration": duration,
            "duration_formatted": format_duration_seconds(duration),
            "size": size,
            "overall_bitrate": format_obj.get("bit_rate"),
            "video_streams": video_streams,
            "audio_streams": audio_streams,
            "subtitle_streams": subtitle_streams,
            "chapters_count": len(chapters_list),
            "tags": tags,
            "is_healthy": is_healthy,
            "raw_json": raw_data,
        }
    except Exception as err:
        return {"success": False, "error": str(err)}
