# GGU_VDOD — Unique Selling Points

> **One line:** Download, convert, and organize media from virtually any website —
> social media, streaming platforms, live streams, and adult sites — in one local,
> private, Windows-native app that explains every error in plain English.

---

## 1. Universal Media Coverage — "If it plays in your browser, you can keep it"

Powered by the yt-dlp engine (1,800+ supported extractors) behind a real GUI.

| Source type | Examples | What GGU_VDOD does |
|---|---|---|
| **Video platforms** | YouTube, Vimeo, Dailymotion, Rumble, Odysee | Single videos, playlists, channels, full quality range up to 4K/8K |
| **Social media** | TikTok, Instagram, X/Twitter, Facebook, Reddit, Snapchat, Pinterest, Tumblr | Reels, stories (public), clips, images + video, with title/metadata |
| **Live streams** | Twitch, YouTube Live, Kick, generic HLS/DASH | Record live streams as they happen, or fetch the VOD replay afterwards |
| **Streaming sites** | Public/free streaming platforms | Direct stream and progressive downloads, remuxed to clean MP4/MKV |
| **Music & audio** | SoundCloud, Bandcamp, Mixcloud, podcasts | Audio-only extraction up to lossless (FLAC/ALAC), tags + thumbnail |
| **Adult platforms** | Public content on mainstream adult tube sites | Treated exactly like any other extractor — no judgment, no separate flow, same quality/error handling |
| **Local files** | Any file on disk | Full converter, trimmer, and FFprobe inspector — not just downloads |

**Why it matters:** one tool instead of five sketchy "online downloader" websites
that are covered in ads, cap quality, and log every URL you paste.

---

## 2. Access With Your Own Keys — "You already have access; we make it work"

Most "it doesn't work" cases are not bugs — the platform wants proof of a real
user. GGU_VDOD handles this using **your own session, on your own machine**:

- **Age-gated content (18+):** import your age-verified browser session
  (Chrome/Firefox/Edge/Brave cookies) and download what you are already allowed
  to watch. Your cookies never leave your PC.
- **Login-required content:** the same — your own account session, stored and
  used locally. Private memberships you legitimately pay for work like normal
  viewing.
- **Bot-check walls:** automatic one-shot retry with alternate YouTube clients
  (TV / Safari / embedded) recovers most *"confirm you're not a bot"* failures
  without any user setup.
- **Broken cookie databases:** if Chrome locks its cookie store, GGU_VDOD
  detects it, tells you in plain English, and auto-retries without cookies
  instead of dying.
- **Rate limits (HTTP 429) & temporary failures:** automatic back-off retries
  with a visible countdown.

### The honest line (this is a feature, not a limitation)

GGU_VDOD **does not and will not**:

- ❌ Strip or circumvent **DRM** (Widevine, FairPlay, PlayReady) — illegal under
  DMCA §1201 / EUCD, and a guaranteed takedown for the project.
- ❌ Access **other people's private or paid content** without their account —
  that is unauthorized access, full stop.
- ❌ Circumvent **regional blocks** as a marketed feature — geo decisions belong
  to the rights holder; users can configure their own proxy if their local law
  allows it.

Everything else — every public stream, every site you can legally open in your
browser, every session you own — is fair game, and it covers ~99% of real use.

---

## 3. The Reliability Engine — "Errors that talk to humans"

The only downloader in its class with a **19-category natural-language error
system** (`errors.txt` is the public spec):

| Typical tool says | GGU_VDOD says |
|---|---|
| `ERROR: Postprocessing: Error opening input files` | *"The media was fetched but FFmpeg could not process it. The site likely served broken data. Retry once, then switch format/quality."* |
| `HTTP Error 403: rate limit exceeded` | *"GitHub is temporarily limiting update checks from your network. Not your PC's fault — wait an hour or grab it from the Releases page."* |
| `Sign in to confirm you're not a bot` | *"The platform wants proof of a real browser session. Pick your browser under Browser cookies, or store a session in Account & Sessions."* |

Plus the machinery behind it:

- **Auto-retry with smart fallbacks** — cookies → cookieless, subtitles → no
  subtitles, standard client → alternate clients.
- **Disk pre-flight guard** — refuses to start a 4 GB download onto a 2 GB drive.
- **Integrity gate** — verifies the final file is real, playable media, not a
  30 KB error page renamed to `.mp4`.
- **Recovery reports** — after a batch, a plain-text report lists every failed
  link, the raw error, the human reason, and the recommended next action.
- **Duplicate detection** — same video + same settings fingerprint → skip or
  proceed, your choice.
- **Crash reports** — unhandled exceptions write a sanitized report (build, OS,
  settings, traceback) before dying.

---

## 4. Conversion Power — "A downloader that is also a converter"

- **Any → any:** MP4, MKV, MOV, AVI, WEBM, TS, OGV, 3GP ↔ MP3, M4A, AAC, WAV,
  FLAC, OPUS, OGG, WMA, AIFF, ALAC.
- **Full control:** codec (H.264/H.265/VP9/AV1), bitrate, resolution, frame
  rate, sample rate, channel layout, compression level.
- **Timestamp cutter:** trim `00:12 → 01:30` without a separate editor.
- **Sidecar hygiene:** cleans `.part`, `.ytdl`, and temp junk automatically.
- **No duplicate outputs:** if the source already matches your target, no
  pointless re-encode copy is created.

---

## 5. Privacy & Trust — "Your links are nobody's business"

- **Local-first:** no account with us, no telemetry, no URL logging, no cloud.
- **Sanitized diagnostics:** crash/recovery reports are manually inspectable
  text files — secrets are redacted before writing.
- **Open pipeline:** yt-dlp + FFmpeg — the same audited open-source tools the
  whole internet relies on.
- **Uninstall you can trust:** built-in uninstaller with optional full wipe of
  settings, sessions, and history.

---

## 6. Desktop-Class UX — "Built like a Windows app, not a script"

- Native window, dark theme system (5 presets + fully custom colors), font and
  zoom preferences, custom key bindings.
- Live progress: speed, ETA, transfer size, per-item status.
- Download history with **Open File / Open Folder / Copy URL / Retry** actions.
- Media library browser (videos / audio / thumbnails) and FFprobe deep
  inspector built in.
- In-app updater with silent install — updates are one click, not a reinstall.

---

## 7. Positioning

| vs | GGU_VDOD advantage |
|---|---|
| **Online downloader sites** | No ads, no quality caps, no URL logging, batch support, works offline |
| **yt-dlp CLI** | Same engine, real GUI, human-readable errors, zero flags to memorize |
| **Paid downloaders (4K Downloader et al.)** | Free, open pipeline, more formats, better error recovery, no license nag |
| **Browser extensions** | Not chained to one browser, no store approval risk, full conversion suite |

---

## 8. Roadmap highlights (see `upcomingFeatures.txt` for the full list)

Proper queue manager with playlist expansion · pause/resume · batch import/export
· broken-link pre-check · per-site rules · portable mode · privacy cleanup center
· chapter-aware splitting · loudness normalization · creator export presets
(Premiere / DaVinci / Unreal / Blender / FL Studio).

---

*GGU_VDOD — keep what you can watch. v0.2.18 #074.*
