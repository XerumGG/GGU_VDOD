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


def audio_fallback_args(target_ext):
    codecs = {
        "mp3": "libmp3lame", "wav": "pcm_s16le", "aac": "aac", "flac": "flac",
        "ogg": "libvorbis", "opus": "libopus", "m4a": "aac", "wma": "wmav2",
        "aiff": "pcm_s16be", "alac": "alac",
    }
    return ["-vn", "-c:a", codecs[target_ext]]


def video_conversion_args(settings, target_ext):
    selected_codec_args = list(VIDEO_CODEC_ARGS.get(settings.get("video_codec"), []))
    resolution = settings.get("conversion_resolution", "Source")
    frame_rate = settings.get("frame_rate", "Source")
    bitrate = valid_bitrate(settings.get("video_bitrate"))
    needs_reencode = bool(selected_codec_args) or resolution != "Source" or frame_rate != "Source" or bool(bitrate)
    if not needs_reencode:
        return []
    fallback_args = video_fallback_args(target_ext)
    args = selected_codec_args or fallback_args[:2]
    args += fallback_args[2:]
    if resolution in VIDEO_RESOLUTION_OPTIONS and resolution != "Source":
        width, height = resolution.split("x", 1)
        args += ["-vf", f"scale={width}:{height}:force_original_aspect_ratio=decrease"]
    if frame_rate in FRAME_RATE_OPTIONS and frame_rate != "Source":
        args += ["-r", frame_rate]
    if bitrate:
        args += ["-b:v", bitrate]
    return args


def audio_conversion_args(settings, target_ext):
    args = list(audio_fallback_args(target_ext))
    if target_ext not in {"wav", "flac", "aiff", "alac"}:
        args += ["-b:a", BITRATE_MAP.get(settings["quality"], "192") + "k"]
    sample_rate = settings.get("sample_rate", "Source")
    if sample_rate in SAMPLE_RATE_OPTIONS and sample_rate != "Source":
        args += ["-ar", sample_rate]
    channels = settings.get("channels", "Source")
    if channels == "Mono":
        args += ["-ac", "1"]
    elif channels == "Stereo":
        args += ["-ac", "2"]
    compression = settings.get("compression_level", "Auto")
    if compression in COMPRESSION_OPTIONS and compression != "Auto" and target_ext in {"flac", "opus"}:
        args += ["-compression_level", compression]
    return args


def clean_video_sidecars(output_dir, started_at, target_ext):
    """Keep the requested video file and remove matching temporary sidecars."""
    try:
        names = os.listdir(output_dir)
    except OSError:
        return 0

    finished_media = []
    for name in names:
        path = os.path.join(output_dir, name)
        if not os.path.isfile(path) or not name.casefold().endswith(f".{target_ext}"):
            continue
        try:
            if os.path.getmtime(path) >= started_at - 2:
                finished_media.append(name)
        except OSError:
            continue

    removed = 0
    for name in names:
        if ".ggu-converted." not in name.casefold():
            continue
        path = os.path.join(output_dir, name)
        final_name = re.sub(r"\.ggu-converted\.", ".", name, flags=re.IGNORECASE)
        final_path = os.path.join(output_dir, final_name)
        try:
            is_current_file = os.path.getmtime(path) >= started_at - 2
            if os.path.isfile(path) and (is_current_file or os.path.isfile(final_path)):
                os.remove(path)
                removed += 1
        except OSError:
            pass

    for final_name in finished_media:
        stem = os.path.splitext(final_name)[0]
        prefix = stem + "."
        for name in names:
            if name == final_name or not name.startswith(prefix):
                continue
            extension = os.path.splitext(name)[1].casefold()
            if extension not in VIDEO_SIDECAR_EXTENSIONS:
                continue
            try:
                os.remove(os.path.join(output_dir, name))
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
