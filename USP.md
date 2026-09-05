# GGU_VDOD — Unique Selling Points

> Download, convert, and organize media from **1,700+ websites** — social, streaming,
> live, music, and adult — in one local, private Windows app that explains every
> error in plain English.

## 1. Universal coverage — "If it plays in your browser, you can keep it"

yt-dlp engine (1,752 extractors) behind a real GUI: YouTube (videos, playlists,
channels, Shorts), TikTok, Instagram, X, Facebook, Reddit, Twitch live + VODs,
Kick, Vimeo, Dailymotion, Rumble, Bilibili, NicoNico, SoundCloud, Bandcamp,
Mixcloud, BBC/CNN/ESPN/arte, direct MP4/HLS/DASH links, mainstream adult tubes —
plus any local file for conversion and inspection.

One tool instead of five sketchy "online downloader" sites full of ads, quality
caps, and URL logging.

## 2. Access with your own keys — "You already have access; we make it work"

- **Age-gated (18+) and login-walled content:** import your own verified browser
  session (Chrome/Firefox/Edge/Brave cookies) or a stored DPAPI account — your
  cookies never leave your PC.
- **Bot-check walls:** automatic retry with alternate YouTube clients
  (Android/iOS/TV/Safari) recovers most *"confirm you're not a bot"* and 403
  failures with zero setup.
- **Broken cookie databases and rate limits:** detected, explained in plain
  English, retried automatically with safe fallbacks.

**Out of scope by policy:** DRM stripping (DMCA/EUCD), other people's private or
paid content, and geo-block circumvention. Everything you can legally open in
your browser — ~99% of real use — is fair game.

## 3. Reliability engine — "Errors that talk to humans"

A **21-category natural-language error system** (`errors.txt` is the public spec):
`Postprocessing: Error opening input files` becomes *"FFmpeg couldn't process
it — retry once, then switch format"*; a YouTube 403 becomes *"YouTube's
bot-check, not your internet — retrying with alternate clients"*.

Behind it: smart auto-retry, disk pre-flight guard, download integrity gate,
duplicate detection, per-batch recovery reports, and sanitized crash reports.

## 4. Conversion power — "A downloader that is also a converter"

**Any → any:** MP4, MKV, MOV, AVI, WebM, FLV, MPEG, TS, M4V, OGV, 3GP ↔ MP3, WAV,
AAC, FLAC, OGG, Opus, M4A, WMA, AIFF, ALAC. Full codec/bitrate/resolution/FPS
control, timestamp trim, subtitle & thumbnail embedding, automatic sidecar
cleanup — and no pointless re-encode when the source already matches.

## 5. Queue & batch — "Built for playlists, not just single links"

Live queue rows (title, status, progress, speed, ETA), automatic playlist
expansion into individual items, one-click **Retry Failed**, link import from
txt/csv/json/clipboard, and failed-link export.

## 6. Privacy & trust — "Your links are nobody's business"

Local-first, no accounts, no telemetry, no URL logging. DPAPI-encrypted
sessions, redacted diagnostics, audited open-source pipeline (yt-dlp + FFmpeg),
and an uninstaller with optional full wipe.

## 7. Desktop-class UX — "Built like a Windows app, not a script"

Dark theme system (5 presets + fully custom colors), 11 languages, fonts, zoom,
key bindings, download history with open/retry actions, media library browser,
FFprobe inspector, one-click in-app updater.

## 8. Positioning

| Instead of… | GGU_VDOD gives you… |
|---|---|
| Online downloader sites | No ads, no quality caps, no URL logging, batch support |
| yt-dlp CLI | Same engine, real GUI, human-readable errors, zero flags |
| Paid downloaders | Free, open pipeline, more formats, better recovery |
| Browser extensions | Browser-independent, no store risk, full conversion suite |

Roadmap highlights (`upcomingFeatures.txt`): pause/resume · broken-link pre-check ·
per-site rules · portable mode · privacy cleanup center · chapter splitting ·
creator export presets (Premiere / DaVinci / Unreal / Blender / FL Studio).

*GGU_VDOD — keep what you can watch. v0.2.30 #086.*
