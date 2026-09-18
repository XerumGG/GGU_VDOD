# GGU_VDOD

A free, open-source Windows application for downloading videos, audio, and images from 1700+ supported websites — and converting them to any format you need. Paste a link, pick a quality, hit download.

Built on [yt-dlp](https://github.com/yt-dlp/yt-dlp) with [FFmpeg](https://ffmpeg.org/) bundled in, so there is nothing else to install. No ads, no accounts, no telemetry.

## Supported Sources

YouTube (videos, playlists, channels, Shorts), TikTok, Instagram, X / Twitter, Facebook, Reddit, Twitch (live and VODs), Kick, Vimeo, Dailymotion, Rumble, Bilibili, NicoNico, SoundCloud, Bandcamp, Mixcloud, BBC / CNN / ESPN / arte, direct MP4/HLS/DASH links — and local files on disk for conversion-only workflows.

Cookie import is supported for sites that require login or age verification. YouTube 403 / bot-check errors are retried automatically with alternate clients.

> **Note:** DRM-protected content (Netflix, Spotify, etc.) is not supported.

## Features

- Downloads up to 4K with playlists, batch links, and a live queue showing progress, speed, and ETA per item
- Converts between MP4, MKV, MOV, AVI, WebM, MP3, FLAC, WAV, OGG, Opus, M4A, WMA, AIFF, ALAC, and more
- Human-readable error explanations with suggested fixes
- Pre-download disk space check, post-download file integrity verification, and recovery reports for failed batches
- Download history, duplicate detection, and timestamp-based clip trimming
- 11 languages, customizable dark themes, zoom, and keyboard shortcuts
- In-app self-updater

## Installation

Download `GGU_VDOD-setup-vX.Y.Z.exe` from [Releases](../../releases/latest) and run it (no admin required). A portable ZIP is also available.

To update later, click **Check for Updates** in the top-right corner of the application.

## Building from Source

```powershell
pip install -r requirements.txt pyinstaller
.\build_exe.ps1
```

Output lands in `dist\GGU_VDOD\`. The installer step requires [Inno Setup 6](https://jrsoftware.org/isdl.php).

## Documentation

- [Project Principles](docs/USP.md)
- [FAQ](docs/FAQ.md)
- [Installation Guide](docs/Installation.md)
- [Architecture](docs/Architecture.md)
- [Roadmap](docs/Roadmap.md)
- [Changelog](CHANGELOG.md)

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Language | Python 3.10+ |
| UI Framework | PySide6 (Qt) |
| Download Engine | yt-dlp |
| Media Processing | FFmpeg |

## License

[MIT](LICENSE)
