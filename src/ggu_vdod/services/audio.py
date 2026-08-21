"""Audio notification sound manager with distinct Windows error cues."""

import sys
import threading

try:
    import winsound
    HAS_WINSOUND = True
except ImportError:
    HAS_WINSOUND = False

# MessageBeep is kept as a fallback.  Windows treats MB_ICONSTOP and
# MB_ICONHAND as aliases, and a user's sound scheme can map every system event
# to the same audio file.  The short Beep patterns below make categories
# recognisable even in that case.
SOUND_MAPPING = {
    "MB_ICONHAND": getattr(winsound, "MB_ICONHAND", 0x00000010) if HAS_WINSOUND else 0,
    "MB_ICONSTOP": getattr(winsound, "MB_ICONSTOP", 0x00000010) if HAS_WINSOUND else 0,
    "MB_ICONEXCLAMATION": getattr(winsound, "MB_ICONEXCLAMATION", 0x00000030) if HAS_WINSOUND else 0,
    "MB_ICONASTERISK": getattr(winsound, "MB_ICONASTERISK", 0x00000040) if HAS_WINSOUND else 0,
    "MB_OK": getattr(winsound, "MB_OK", 0x00000000) if HAS_WINSOUND else 0,
}

_DEFAULT_SOUND_PATTERNS = {
    "MB_ICONSTOP": ((392, 115), (330, 165)),
    "MB_ICONHAND": ((523, 100), (440, 100)),
    "MB_ICONEXCLAMATION": ((740, 105),),
    "MB_ICONASTERISK": ((988, 80),),
}

_ERROR_SOUND_PATTERNS = {
    "ERR_DISK_FULL": ((330, 120), (294, 170)),
    "ERR_NET_DISCONNECTED": ((523, 80), (392, 100)),
    "ERR_CLOUDFLARE_403": ((784, 75), (659, 100)),
    "ERR_RATE_LIMITED_429": ((698, 70), (698, 70), (523, 110)),
    "ERR_AGE_RESTRICTED": ((988, 70), (1175, 90)),
    "ERR_PRIVATE_VIDEO": ((784, 100), (622, 125)),
    "ERR_VIDEO_DELETED_404": ((466, 95), (349, 130)),
    "ERR_GEOBLOCKED": ((659, 95), (554, 120)),
    "ERR_FFMPEG_MISSING": ((294, 130), (247, 185)),
    "ERR_FORMAT_UNAVAILABLE": ((1047, 75), (880, 100)),
    "ERR_PERMISSION_DENIED": ((370, 115), (311, 165)),
    "ERR_DPAPI_COOKIE_LOCK": ((831, 80), (698, 110)),
    "ERR_PROXY_FAILED": ((587, 85), (440, 120)),
    "ERR_CORRUPT_STREAM": ((554, 80), (415, 125)),
    "ERR_FRAGMENT_FAILED": ((740, 70), (622, 75), (494, 105)),
    "ERR_UNHANDLED_EXCEPTION": ((262, 125), (220, 175)),
}


def sound_pattern_for(sound_type: str = "MB_ICONEXCLAMATION", error_code: str | None = None):
    """Return the audible pattern used for one classified error category."""
    return _ERROR_SOUND_PATTERNS.get(error_code or "", _DEFAULT_SOUND_PATTERNS.get(sound_type, _DEFAULT_SOUND_PATTERNS["MB_ICONEXCLAMATION"]))


def _play_pattern_async(pattern, fallback_sound_type=None):
    """Play a beep pattern on a worker thread; winsound.Beep blocks for the full duration."""
    if not HAS_WINSOUND:
        return

    def _worker():
        try:
            for frequency, duration in pattern:
                winsound.Beep(frequency, duration)
        except Exception:
            if fallback_sound_type is not None:
                try:
                    winsound.MessageBeep(fallback_sound_type)
                except Exception:
                    pass

    threading.Thread(target=_worker, daemon=True).start()


def play_error_sound(sound_type: str = "MB_ICONEXCLAMATION", error_code: str | None = None) -> None:
    """Play a recognisable sound pattern for a classified error."""
    _play_pattern_async(
        sound_pattern_for(sound_type, error_code),
        SOUND_MAPPING.get(sound_type, getattr(winsound, "MB_ICONEXCLAMATION", 0) if HAS_WINSOUND else 0),
    )


def play_success_sound() -> None:
    """Play Windows asterisk/notification chime on successful operation completion."""
    _play_pattern_async(((988, 80),), getattr(winsound, "MB_ICONASTERISK", 0) if HAS_WINSOUND else 0)
