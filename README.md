# GGU_VDOD

High-performance desktop media downloader and local converter powered by PySide6, yt-dlp, curl_cffi, and FFmpeg; created by **XerumGG** (**GG Uranium**).

> **Development build v0.002.004 (049):** Active PySide6 desktop application with classified download-error alerts, distinct error sounds, DPAPI encrypted account session management, 18+ age verification detection, Mailpit local test inbox integration, and permanent FFmpeg/FFprobe directory integration.

## Key Capabilities & Features

- **Universal Video & Audio Downloader:** Download 4K/2K/1080p videos or convert audio to MP3, WAV, AAC, FLAC, OGG, Opus, M4A, WMA, AIFF, or ALAC.
- **Batch Processing & Playlists:** Single video links, playlist contexts, and multi-line batch URL inputs.
- **Cloudflare Impersonation (HTTP 403 Bypass):** Integrated `curl_cffi` Chrome TLS fingerprint impersonation to bypass Cloudflare anti-bot challenges.
- **DPAPI Encrypted Sessions:** Stores domain credentials and tokens securely under Windows DPAPI encryption in `auth_sessions.json`.
- **18+ Age Gate Detection & Auth Setup:** Detects age-restricted links, prompts for age verification, and connects with browser cookie import or Mailpit local test inbox (`127.0.0.1:8025`).
- **Permanent FFmpeg & FFprobe Path:** Permanent directory at `D:\GGU_VDOD\ffmpeg\` for `ffmpeg.exe` and `ffprobe.exe`.
- **Automatic 24-Hour Component Update Check:** Periodically checks versions for yt-dlp, PySide6, Pillow, PyInstaller, curl_cffi, FFmpeg, and FFprobe.
- **Force Application Restart (Reboot):** Instantly reboot the app and release processes using **Edit > Force restart application** (`Ctrl+Shift+` `).

## Project Documentation

- [Architecture](docs/Architecture.md)
- [Installation](docs/Installation.md)
- [FAQ](docs/FAQ.md)
- [Roadmap](docs/Roadmap.md)
- [Changelog](CHANGELOG.md)
- [Contributing](CONTRIBUTING.md)
- **Age/private/member-only link:** use valid authorized cookies; there is no bypass.
- **Old extractor error:** update yt-dlp, then rebuild.

Use **Advanced → Check library updates** to compare yt-dlp, Pillow, and PyInstaller with
PyPI. It also reports the Python and FFmpeg versions. The check is read-only.

## Supported sites

The installed yt-dlp build determines the live extractor list. Common sources include
YouTube, Vimeo, TikTok, Instagram, Facebook, X, Reddit, Twitch, Kick, Rumble, Dailymotion,
SoundCloud, Bandcamp, Bilibili, archive.org, podcasts, live platforms, and supported adult
content sites. Availability changes and some sites need cookies, proxy, or age verification.

## Credits

Developed by **GG Uranium** .
Tools used : Python, PySide6, yt-dlp, FFmpeg, Pillow, PyInstaller,
and Python standard-library networking/threading.

## Changelog

- **#028 - Responsive zoom and UI controls**: added bounded 80–140% zoom with Ctrl+wheel,
  configurable zoom shortcuts, and a more consistent control typography baseline.
- **#024 - Responsive windows and scrolling**: landing pages now keep normal Windows
  minimize, maximize, and close controls, and main-page wheel scrolling no longer uses a
  laggy global animation handler.
- **#023 - UI stability and preview fixes**: made preferences and landing pages resizable,
  scrollable, and easy to close; set Dark to a pitch-black default; removed slow full-window
  theme repainting; made YouTube watch links with playlist context preview the selected video;
  and prevented stale `.ggu-converted` working files from remaining beside final downloads.
- **#022 - Fix packaged UI assets**: the build now includes ttkbootstrap fonts and image
  assets, preventing the packaged executable from failing at startup.
- **#021 - Modern ttkbootstrap UI**: replaced the old flat control layer with themed ttkbootstrap
  widgets while keeping the downloader and custom color system intact.
- **#020 - Larger intuitive controls**: enlarged buttons, added hover/press/disabled feedback,
  and improved checkbox/radio indicators with accent-colored selected states.

- **#019 - UI themes and custom colors**: added four presets plus a saved Custom palette
  with editable window, panel, input, log, text, border, accent, status, tooltip, and
  selection colors.

- **#018 — MP4 default with format choices**: restored all video format choices while
  keeping MP4 as the default. Shortened this README and added simple one-line commands.


