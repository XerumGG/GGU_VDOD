# GGU_VDOD

Free Windows desktop app to download **video, audio, and images from 1,700+ websites** — then convert them to any format. Paste a link, pick quality, download. No ads, no accounts, no telemetry.

## Where it downloads from

Engine: yt-dlp (1,752 extractors, verified in this build) + bundled FFmpeg.

| Category | Sites |
|---|---|
| Video platforms | YouTube (videos, playlists, channels, Shorts), Vimeo, Dailymotion, Rumble, Bilibili, NicoNico, VK, PeerTube, Streamable, Wistia |
| Social media | TikTok, Instagram, X/Twitter, Facebook, Reddit, Snapchat, Pinterest, Tumblr, LinkedIn |
| Live & streams | Twitch (live + VODs), YouTube Live, Kick, any HLS/DASH stream, arte, BBC, CNN, ESPN |
| Music & audio | SoundCloud, Bandcamp, Mixcloud, podcasts |
| Adult (18+) | Pornhub, XHamster, XVideos, RedTube, YouPorn, SpankBang — same pipeline, no separate flow |
| Anything else | Direct MP4/WebM links, generic HLS/DASH, plus any local file (convert / inspect) |

Why it works where others fail: automatic retry with alternate YouTube clients (Android/iOS/TV), browser-cookie import for sign-in and age-gated content, TLS impersonation — and every failure explained in plain English with a fix.

One honest limit: DRM-protected content (Netflix, Spotify, …) can't be downloaded — by anyone, legally. See [USP.md](USP.md).

## Strengths

- **Errors that talk to humans** — a 21-category classifier turns `HTTP Error 403` into cause + fix (full spec: [errors.txt](errors.txt))
- **Self-healing downloads** — alternate-client retry, cookieless fallback, subtitle fallback, network back-off
- **Safe by default** — disk-space pre-flight check, download integrity verification, duplicate detection, failed-batch recovery reports
- **Real queue manager** — live rows (status / progress / speed / ETA), playlist auto-expansion, one-click Retry Failed
- **Batch friendly** — import links from txt/csv/json/clipboard, export failed links
- **Full converter** — 11 video + 10 audio formats, codec/bitrate/resolution control, timestamp trim, subtitle & thumbnail embedding
- **Private** — local-first, DPAPI-encrypted sessions, sanitized crash reports, clean uninstaller
- **Personal** — 11 languages, 5 themes + fully custom colors, fonts, zoom, key bindings, history, media library
- **Maintained** — in-app updater with silent install

## Install

- **Setup (recommended):** download `GGU_VDOD-setup-vX.Y.Z.exe` from [Releases](../../releases/latest) → run it. No admin needed.
- **Portable:** grab `GGU_VDOD-windows-portable.zip`, extract, run.
- **Update:** click **Check for Updates** inside the app (top-right).

| | |
|---|---|
| **Developer** | XerumGG |
| **Stack** | Python · PySide6 · yt-dlp · FFmpeg |
| **License** | MIT |

More docs: [USP](USP.md) · [FAQ](docs/FAQ.md) · [Installation](docs/Installation.md) · [Architecture](docs/Architecture.md) · [Roadmap](docs/Roadmap.md) · [Changelog](CHANGELOG.md)

## Build from source

```powershell
pip install -r requirements.txt pyinstaller
.\build_exe.ps1
```

Output: `dist\GGU_VDOD\`. Installer requires [Inno Setup 6](https://jrsoftware.org/isdl.php).
