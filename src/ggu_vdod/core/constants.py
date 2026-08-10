"""Application-wide constants that do not depend on the desktop UI."""

APP_NAME = "GGU_VDOD"

UPDATE_COMPONENTS = (
    ("yt-dlp", "yt_dlp", "runtime dependency"),
    ("curl_cffi", "curl_cffi", "anti-bot impersonation dependency"),
    ("Pillow", "PIL", "runtime image dependency"),
    ("PySide6", "PySide6", "primary runtime UI framework"),
    ("PyInstaller", "PyInstaller", "binary build dependency"),
    ("FFmpeg", "ffmpeg", "multimedia encoder binary"),
    ("FFprobe", "ffprobe", "multimedia analyzer binary"),
)

VIDEO_QUALITIES = ["Best available", "2160p (4K)", "1440p (2K)", "1080p", "720p", "480p", "360p"]
AUDIO_QUALITIES = ["320 kbps (Best)", "256 kbps", "192 kbps", "128 kbps"]
VIDEO_OUTPUT_FORMATS = ["MP4", "MKV", "MOV", "AVI", "WebM", "FLV", "MPEG", "TS", "M4V", "OGV", "3GP"]
AUDIO_OUTPUT_FORMATS = ["MP3", "WAV", "AAC", "FLAC", "OGG", "Opus", "M4A", "WMA", "AIFF", "ALAC"]

VIDEO_SIDECAR_EXTENSIONS = {
    ".mp4", ".mkv", ".mov", ".avi", ".webm", ".flv", ".mpeg", ".ts", ".m4v", ".ogv", ".3gp",
    ".vtt", ".srt", ".ass", ".lrc", ".json", ".description", ".txt",
    ".jpg", ".jpeg", ".png", ".webp", ".avif", ".gif", ".part",
}
VIDEO_FORMAT_EXTENSIONS = {
    "MP4": "mp4", "MKV": "mkv", "MOV": "mov", "AVI": "avi", "WebM": "webm",
    "FLV": "flv", "MPEG": "mpeg", "TS": "ts", "M4V": "m4v", "OGV": "ogv", "3GP": "3gp",
}
AUDIO_FORMAT_EXTENSIONS = {
    "MP3": "mp3", "WAV": "wav", "AAC": "aac", "FLAC": "flac", "OGG": "ogg",
    "Opus": "opus", "M4A": "m4a", "WMA": "wma", "AIFF": "aiff", "ALAC": "m4a",
}

VIDEO_CODEC_OPTIONS = ["Auto", "H.264", "H.265", "VP9", "AV1"]
VIDEO_CODEC_ARGS = {
    "H.264": ["-c:v", "libx264"],
    "H.265": ["-c:v", "libx265"],
    "VP9": ["-c:v", "libvpx-vp9"],
    "AV1": ["-c:v", "libaom-av1"],
}
VIDEO_RESOLUTION_OPTIONS = ["Source", "3840x2160", "2560x1440", "1920x1080", "1280x720", "854x480", "640x360"]
FRAME_RATE_OPTIONS = ["Source", "24", "25", "30", "50", "60"]
SAMPLE_RATE_OPTIONS = ["Source", "44100", "48000", "96000"]
CHANNEL_OPTIONS = ["Source", "Mono", "Stereo"]
COMPRESSION_OPTIONS = ["Auto", "0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12"]
COOKIE_BROWSERS = ["None", "Chrome", "Edge", "Firefox", "Brave", "Opera", "Vivaldi", "Safari"]

HEIGHT_MAP = {
    "2160p (4K)": 2160,
    "1440p (2K)": 1440,
    "1080p": 1080,
    "720p": 720,
    "480p": 480,
    "360p": 360,
    "144p": 144,
}
BITRATE_MAP = {
    "320 kbps (Best)": "320",
    "256 kbps": "256",
    "192 kbps": "192",
    "128 kbps": "128",
}

MAX_RETRIES = 5
RETRY_WAIT_SECONDS = 5
CONNECTIVITY_ENDPOINTS = (("1.1.1.1", 53), ("8.8.8.8", 53), ("www.youtube.com", 443))

SCROLL_SPEED_MIN = 1
SCROLL_SPEED_MAX = 6
SCROLL_SPEED_DEFAULT = 1
ZOOM_MIN_PERCENT = 80
ZOOM_MAX_PERCENT = 140
ZOOM_STEP_PERCENT = 10
ZOOM_DEFAULT_PERCENT = 100
KEY_BINDING_CHOICES = (
    "Ctrl + + / Ctrl + =",
    "Ctrl + -",
    "Ctrl + 0",
    "None",
)
DEFAULT_KEY_BINDINGS = {
    "zoom_in": "Ctrl + + / Ctrl + =",
    "zoom_out": "Ctrl + -",
    "zoom_reset": "Ctrl + 0",
}

CONTENT_MIN_WIDTH = 1000
PREVIEW_WIDTH = 240
PREVIEW_HEIGHT = 135
PREVIEW_PLACEHOLDER_COLUMNS = 30
PREVIEW_PLACEHOLDER_ROWS = 7


def clamp_scroll_speed(value):
    try:
        value = int(value)
    except (TypeError, ValueError):
        value = SCROLL_SPEED_DEFAULT
    return max(SCROLL_SPEED_MIN, min(SCROLL_SPEED_MAX, value))


def clamp_zoom_percent(value):
    try:
        value = int(value)
    except (TypeError, ValueError):
        value = ZOOM_DEFAULT_PERCENT
    return max(ZOOM_MIN_PERCENT, min(ZOOM_MAX_PERCENT, value))
