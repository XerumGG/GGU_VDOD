"""Pure conversion and output-file policy helpers."""

import os
import re

from ..core.constants import (
    BITRATE_MAP, COMPRESSION_OPTIONS, FRAME_RATE_OPTIONS, SAMPLE_RATE_OPTIONS,
    VIDEO_CODEC_ARGS, VIDEO_RESOLUTION_OPTIONS, VIDEO_SIDECAR_EXTENSIONS,
)


def valid_bitrate(value):
    value = (value or "").strip()
    return value if re.fullmatch(r"\d+(?:\.\d+)?[kKmMgG]?", value) else ""


def video_fallback_args(target_ext):
    return {
        "mp4": ["-c:v", "libx264", "-c:a", "aac"],
        "mkv": ["-c:v", "libx264", "-c:a", "aac"],
        "mov": ["-c:v", "libx264", "-c:a", "aac"],
        "m4v": ["-c:v", "libx264", "-c:a", "aac"],
        "webm": ["-c:v", "libvpx-vp9", "-c:a", "libopus"],
        "avi": ["-c:v", "libxvid", "-c:a", "libmp3lame"],
        "flv": ["-c:v", "libx264", "-c:a", "aac"],
        "mpeg": ["-c:v", "mpeg2video", "-c:a", "mp2"],
        "ts": ["-c:v", "libx264", "-c:a", "aac"],
        "ogv": ["-c:v", "libtheora", "-c:a", "libvorbis"],
        "3gp": ["-c:v", "libx264", "-c:a", "aac"],
    }.get(target_ext, ["-c:v", "libx264", "-c:a", "aac"])


def audio_fallback_args(target_ext, output_format=""):
    codecs = {
        "mp3": "libmp3lame", "wav": "pcm_s16le", "aac": "aac", "flac": "flac",
        "ogg": "libvorbis", "opus": "libopus", "m4a": "aac", "wma": "wmav2",
        "aiff": "pcm_s16be", "alac": "alac",
    }
    codec = "alac" if output_format == "ALAC" else codecs[target_ext]
    return ["-vn", "-c:a", codec]


def video_conversion_args(settings, target_ext):
    codec_name = settings.get("video_codec", "Auto")
    selected_codec_args = list(VIDEO_CODEC_ARGS.get(codec_name, []))
    resolution = settings.get("conversion_resolution", "Source")
    frame_rate = settings.get("frame_rate", "Source")
    bitrate = valid_bitrate(settings.get("video_bitrate"))
    sample_rate = settings.get("sample_rate", "Source")
    channels = settings.get("channels", "Source")

    needs_reencode = (
        bool(selected_codec_args)
        or resolution != "Source"
        or frame_rate != "Source"
        or bool(bitrate)
        or sample_rate != "Source"
        or channels != "Source"
    )
    if not needs_reencode:
        return []

    fallback_args = video_fallback_args(target_ext)
    args = selected_codec_args or fallback_args[:2]
    args += fallback_args[2:]

    if resolution != "Source":
        res_match = re.search(r"(\d+)x(\d+)", str(resolution))
        if res_match:
            w, h = res_match.group(1), res_match.group(2)
            args += ["-vf", f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad=ceil(iw/2)*2:ceil(ih/2)*2"]
        else:
            h_match = re.search(r"\d+", str(resolution))
            if h_match:
                h = h_match.group(0)
                args += ["-vf", f"scale=-2:{h}"]

    fps_match = re.search(r"\d+", str(frame_rate))
    if fps_match and frame_rate != "Source":
        args += ["-r", fps_match.group(0)]

    if bitrate:
        args += ["-b:v", bitrate]

    sr_match = re.search(r"\d+", str(sample_rate))
    if sr_match and sample_rate != "Source":
        args += ["-ar", sr_match.group(0)]
    if channels == "Mono":
        args += ["-ac", "1"]
    elif channels == "Stereo":
        args += ["-ac", "2"]

    return args


def audio_conversion_args(settings, target_ext):
    output_format = str(settings.get("output_format") or "").upper()
    args = list(audio_fallback_args(target_ext, output_format))
    if target_ext not in {"wav", "flac", "aiff", "alac"}:
        raw_quality = str(settings.get("quality") or "")
        bitrate_val = BITRATE_MAP.get(raw_quality) or re.search(r"\d+", raw_quality)
        bitrate_str = bitrate_val.group(0) if hasattr(bitrate_val, "group") else (bitrate_val or "320")
        args += ["-b:a", f"{bitrate_str}k"]
    sample_rate = settings.get("sample_rate", "Source")
    sr_match = re.search(r"\d+", str(sample_rate))
    if sr_match and sample_rate != "Source":
        # libopus supports only 48/24/16/12/8 kHz. It rejects the two other
        # sample-rate options exposed by the interface, so use its native 48 kHz.
        effective_rate = "48000" if target_ext == "opus" else sr_match.group(0)
        args += ["-ar", effective_rate]
    channels = settings.get("channels", "Source")
    if channels == "Mono":
        args += ["-ac", "1"]
    elif channels == "Stereo":
        args += ["-ac", "2"]
    compression = settings.get("compression_level", "Auto")
    if compression in COMPRESSION_OPTIONS and compression != "Auto" and target_ext in {"flac", "opus"}:
        args += ["-compression_level", str(compression)]
    return args


try:
    from yt_dlp.postprocessor.ffmpeg import FFmpegPostProcessor
except ImportError:
    FFmpegPostProcessor = object


def _safe_replace_file(src, dst):
    """Safely replace destination file with retry handling for transient Windows file locks."""
    import time
    for attempt in range(5):
        try:
            if os.path.exists(dst) and src != dst:
                try:
                    os.remove(dst)
                except OSError:
                    pass
            os.replace(src, dst)
            return True
        except OSError:
            time.sleep(0.15 * (attempt + 1))
    return False


class FFmpegCustomReencodePP(FFmpegPostProcessor):
    """Convert a video file locally when advanced conversion options are used."""
    def __init__(self, downloader, target_ext, ffmpeg_args):
        super().__init__(downloader)
        self.target_ext = target_ext
        self.ffmpeg_args = ffmpeg_args

    def run(self, info):
        filename = info.get("filepath")
        if not filename or not os.path.exists(filename):
            return [], info
        dir_name, base_name = os.path.split(filename)
        stem = os.path.splitext(base_name)[0]
        out_filename = os.path.join(dir_name, f"{stem}.ggu-conv.{self.target_ext}")
        self.to_screen(f"[FFmpeg] Re-encoding media to {self.target_ext} with custom parameters...")
        self.run_ffmpeg(filename, out_filename, self.ffmpeg_args)
        final_filename = _available_final_path(dir_name, stem, self.target_ext, filename)
        if os.path.exists(out_filename):
            if _safe_replace_file(out_filename, final_filename):
                info["filepath"] = final_filename
            else:
                info["filepath"] = out_filename
            info["ext"] = self.target_ext
        return [], info


class FFmpegCustomAudioConvertPP(FFmpegPostProcessor):
    """Convert any supported audio target with ffmpeg, including WMA, AIFF, and OGG."""

    def __init__(self, downloader, target_ext, ffmpeg_args):
        super().__init__(downloader)
        self.target_ext = target_ext
        self.ffmpeg_args = ffmpeg_args

    def run(self, info):
        filename = info.get("filepath")
        if not filename or not os.path.exists(filename):
            return [], info

        dir_name, base_name = os.path.split(filename)
        stem = os.path.splitext(base_name)[0]
        out_filename = os.path.join(dir_name, f"{stem}.ggu-conv.{self.target_ext}")
        final_filename = _available_final_path(dir_name, stem, self.target_ext, filename)
        self.to_screen(f"[FFmpeg] Converting audio to {self.target_ext}...")
        self.run_ffmpeg(filename, out_filename, self.ffmpeg_args)
        if os.path.exists(out_filename):
            if _safe_replace_file(out_filename, final_filename):
                info["filepath"] = final_filename
            else:
                info["filepath"] = out_filename
            info["ext"] = self.target_ext
        return [], info


def _available_final_path(directory, stem, target_ext, source_filename):
    """Avoid replacing a completed file that happens to share the target name."""
    candidate = os.path.join(directory, f"{stem}.{target_ext}")
    if candidate == source_filename or not os.path.exists(candidate):
        return candidate
    index = 1
    while True:
        candidate = os.path.join(directory, f"{stem} ({index}).{target_ext}")
        if not os.path.exists(candidate):
            return candidate
        index += 1


def clean_video_sidecars(output_dir, started_at=0, target_ext=""):
    """Keep the requested media file and remove matching temporary sidecars and stream fragments."""
    try:
        names = os.listdir(output_dir)
    except OSError:
        return 0

    target_ext = (target_ext or "").lower().lstrip(".")
    finished_media = []
    for name in names:
        path = os.path.join(output_dir, name)
        if not os.path.isfile(path):
            continue
        if target_ext and not name.casefold().endswith(f".{target_ext}"):
            continue
        if re.search(r"\.f\d+\.", name, re.IGNORECASE) or ".temp." in name.casefold() or ".part" in name.casefold() or ".ytdl" in name.casefold():
            continue
        try:
            if started_at == 0 or os.path.getmtime(path) >= started_at - 2:
                finished_media.append(name)
        except OSError:
            continue

    removed = 0
    # 1. Clean explicit temporary sidecar markers (.ggu-converted, .temp, .part, .ytdl)
    for name in names:
        cf = name.casefold()
        if ".ggu-converted." in cf or ".temp." in cf or cf.endswith(".part") or cf.endswith(".ytdl"):
            path = os.path.join(output_dir, name)
            try:
                if os.path.isfile(path) and (started_at == 0 or os.path.getmtime(path) >= started_at - 2):
                    os.remove(path)
                    removed += 1
            except OSError:
                pass

    # 2. Clean matching stream format fragments (.f251, .f398, etc.) for finished files
    for final_name in finished_media:
        stem = os.path.splitext(final_name)[0]
        for name in names:
            if name == final_name:
                continue
            path = os.path.join(output_dir, name)
            if not os.path.isfile(path):
                continue
            if name.startswith(stem) and re.search(r"\.f\d+\.", name, re.IGNORECASE):
                try:
                    os.remove(path)
                    removed += 1
                except OSError:
                    pass
    return removed


def output_template(settings, output_dir, target_ext):
    pattern = settings.get("filename_pattern", "").strip()
    if not pattern:
        if settings["format"] == "video":
            pattern = "%(title)s [%(height)sp]"
        else:
            pattern = f"%(title)s [{BITRATE_MAP.get(settings['quality'], '192')}kbps]"
    if "%(ext)" not in pattern:
        pattern += ".%(ext)s"
    return os.path.join(output_dir, pattern)
