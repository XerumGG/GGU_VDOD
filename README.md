# GGU_VDOD

A free Windows app for downloading videos, audio and images, and converting them to whatever format you need. Paste a link, pick a quality, hit download. That's pretty much it.

It's built on yt-dlp (1700+ supported sites) with FFmpeg bundled in, so there's nothing else to install. No ads, no accounts, nothing phoning home.

## What you can download from

YouTube (videos, playlists, channels, Shorts), TikTok, Instagram, X/Twitter, Facebook, Reddit, Twitch (live and VODs), Kick, Vimeo, Dailymotion, Rumble, Bilibili, NicoNico, SoundCloud, Bandcamp, Mixcloud, BBC / CNN / ESPN / arte, Pornhub, XHamster, XVideos and other adult tubes, direct MP4 links, HLS/DASH streams — and any file already sitting on your disk, if you just want to convert it.

If a video needs you logged in or age-verified, import your browser cookies and it downloads the same way it plays in your browser. If YouTube throws a 403 or bot check at you, the app retries by itself with different clients.

One thing it can't do: DRM stuff like Netflix or Spotify. Nothing can legally download those, so don't bother trying.

## What it does

- Downloads up to 4K with playlists, batch links and a live queue showing progress, speed and ETA per item
- Converts between MP4, MKV, MOV, AVI, WebM, MP3, FLAC, WAV, OGG, Opus, M4A, WMA, AIFF, ALAC and more
- Explains errors in normal words and tells you how to fix them
- Checks free disk space before downloading, verifies files aren't broken, and writes a recovery report for failed batches
- Remembers your history, spots duplicates, trims clips by timestamp
- 11 languages, dark themes you can recolor completely, zoom, custom shortcuts
- Updates itself from inside the app

## Install

Grab `GGU_VDOD-setup-vX.Y.Z.exe` from [Releases](../../releases/latest) and run it (no admin needed). Or take the portable zip if you'd rather not install anything.

To update later, click **Check for Updates** in the top-right of the app.

| | |
|---|---|
| Made by | XerumGG |
| Built with | Python, PySide6, yt-dlp, FFmpeg |
| License | MIT |

More reading: [why this exists](USP.md) · [FAQ](docs/FAQ.md) · [install details](docs/Installation.md) · [how it's built](docs/Architecture.md) · [roadmap](docs/Roadmap.md) · [changelog](CHANGELOG.md)

## Build it yourself

```powershell
pip install -r requirements.txt pyinstaller
.\build_exe.ps1
```

It lands in `dist\GGU_VDOD\`. The installer step needs [Inno Setup 6](https://jrsoftware.org/isdl.php).
