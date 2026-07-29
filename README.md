 # GGU_VDOD (cross-platform desktop app)
__Put the link ; Get the VDO, download the MP3, yo yo yo...__


A dark-themed desktop app: paste a video link, pick MP4 (video) or MP3 (audio), click
__Download__. If your internet drops mid-download, it automatically waits, reconnects, and
__resumes from where it stopped__ instead of starting over.

The source runs on Windows, macOS, and Linux. Native packaged executables must be built
on the target operating system with PyInstaller. The Windows build produces
`GGU_VDOD.exe`; macOS/Linux builds produce a native executable for those platforms.

---

## 1. One-time setup (about 5 minutes)

**a) Install Python** (skip if you already have Python 3.9+)
- Download from https://www.python.org/downloads/
- During install, **check the box "Add python.exe to PATH"**

**b) Install ffmpeg** (required - used to merge video/audio and create MP3s)

You have two options - pick whichever is easier:

- Option 1 (recommended, zero-config): bundle it. Download ffmpeg from
  https://www.gyan.dev/ffmpeg/builds/ (get the "essentials" zip), and put
  the ffmpeg executable in a folder named `ffmpeg` next to the built app. On Windows,
  the layout is:
  ```
  dist\GGU_VDOD.exe
  dist\ffmpeg\ffmpeg.exe
  ```
The app automatically finds it there on startup - **no path to type in, no PATH
editing.** This is the default the app looks for first.

When rebuilding with `build.bat`, keep the same executable in the project-level
`ffmpeg\` folder too. The build script copies it back to `dist\ffmpeg\ffmpeg.exe`
after packaging, so it remains beside the rebuilt app. The local binary folder is
intentionally ignored by Git.

- **Option 2: install it system-wide.** Open Command Prompt and run:
  ```
  winget install ffmpeg
  ```
  The app also auto-detects ffmpeg if it's already on your system PATH, or installed at
  common locations like `C:\ffmpeg\bin\ffmpeg.exe`. On macOS, Homebrew can install it
  with `brew install ffmpeg`; on Linux use your distribution's package manager.

If ffmpeg is unavailable, the app can still attempt a single-file video download when
the site exposes one, but MP3 conversion and separate video/audio merging require ffmpeg.

Either way, the **"ffmpeg location"** field in the app will show a green
"✓ Using: ..." once it finds one, or a "⚠ not found" note if it can't - at which point
you can just click Browse and point it at your `ffmpeg.exe` manually.

## 2. Build the app

### Windows

1. Put the project files in one folder.
2. Double-click **`build.bat`**.
3. Wait for it to finish - it creates a virtual environment, installs `yt-dlp` and
   `PyInstaller`, then builds the app.
4. Your Windows app is now at:
   ```
   dist\GGU_VDOD.exe
   ```
   Copy that one file (and optionally the `ffmpeg` folder next to it, see above) wherever
   you like - Desktop, a USB drive, etc. It runs standalone.

The default one-file build is convenient to distribute. If Windows security software
flags it, build an unpacked folder instead with `set GGU_BUILD_MODE=onedir` before running
`build.bat`; unpacked PyInstaller builds are often easier for security tools to inspect.

### macOS/Linux

Run `chmod +x build.sh && ./build.sh`. The app will be created in `dist/GGU_VDOD`.
For an unpacked build, use `GGU_BUILD_MODE=onedir ./build.sh`.

You only need to repeat the build if you change `app.py` or want to update `yt-dlp`.

## 3. Using the app

1. The window opens at 1920x1080 (or your full screen if smaller), centered, and resizable.
2. Paste one or more video links into the box (one per line).
3. Choose **Video (MP4)** or **Audio only (MP3)**, and pick a quality.
4. Expand the **Advanced** tab if you need browser cookies or a `cookies.txt` file for
   sign-in-gated content, subtitles, metadata, thumbnails, a proxy, live-stream capture,
   or an exact format ID. It stays collapsed so the main downloader remains compact.
5. Check **"Save to"** - it defaults to an app folder inside your user Downloads folder,
   change it if you like.
6. Click **Download**. Progress and any errors show up in the log at the bottom.
7. Click **Open Save Folder** any time to jump straight to your files.

The app includes traditional **File**, **Edit**, **View**, **Window**, **Help**, and
**About** menus. Help and About open full landing pages instead of small alert popups.
Use **Edit > Preferences > Key bindings and scroll speed** to control scroll speed and
review the keyboard shortcuts. Text fields support Undo, Redo, Cut, Copy, Paste, and
Select all.

Your last-used save folder and ffmpeg path are remembered automatically for next time.

### If your internet drops mid-download

You don't need to do anything. The app:
- Detects the connection loss (either a network error from the download itself, or a
  direct connectivity check).
- Shows **"Internet connection lost - waiting to resume..."** in the status bar.
- Keeps checking every few seconds in the background.
- The moment your connection is back, it automatically resumes the **same file** using
  yt-dlp's partial-file support (`.part` files) - it picks up from the byte it stopped
  at, it does not redownload from 0%.

You can also click **Cancel** at any point - whatever's been downloaded so far is kept,
and clicking **Download** again later with the same link will resume it rather than
restart it.

## 4. Checking libraries for updates

YouTube changes things occasionally, and a stale media library can break downloads.
Use **Check library updates** in the Advanced section to audit the installed `yt-dlp`,
Pillow, and PyInstaller versions against PyPI. The report also shows the active Python
runtime and detected FFmpeg version. The audit is read-only: it does not install or
replace anything, and FFmpeg is maintained separately from PyPI.

If an update is reported, update the development environment:
```
venv\Scripts\activate
pip install --upgrade yt-dlp Pillow PyInstaller
```
Then rebuild with `build.bat` on Windows or `build.sh` on macOS/Linux.

## What changed in this version

- **Renamed** to **GGU_VDOD** throughout (window title, built app name).
- **Cross-platform runtime**: Windows, macOS, and Linux use native config folders,
  download defaults, ffmpeg discovery, and folder-opening behavior.
- **Animated tooltips**: hover over guidance text, controls, paths, and options to see a
  short plain-English explanation with a smooth fade-in/fade-out popup.
- **Scrollable interface and context menus**: the main panel supports mouse-wheel
  scrolling, and text fields provide right-click Cut, Copy, Paste, and Select all actions.
- **Transfer status bar**: a fixed qBittorrent-style footer shows download rate, upload
  rate, progress, transferred bytes, ETA, and queue status. Upload remains `0 B/s` because
  this is a download-only application.
- **Resilient optional features**: if a browser cookie database is locked or subtitle
  requests are rate-limited, the app retries the video without that optional feature and
  reports the result clearly.
- **Authentication support**: browser cookies and `cookies.txt` can be supplied for
  content the user is authorized to access.
- **Subtitles and media metadata**: subtitle downloads/embedding plus optional metadata
  and thumbnail embedding are available.
- **Clean MP4 video output**: video downloads merge and finish as one MP4 file. If
  subtitles or thumbnails are enabled, temporary `.vtt`, image, and intermediate media
  files are cleaned after successful processing. Audio-only mode still supports MP3, WAV,
  AAC, FLAC, OGG, Opus, M4A, WMA, AIFF, and ALAC through local FFmpeg conversion.
- **Advanced conversion controls**: the Advanced panel exposes video codec, video
  bitrate, output resolution, frame rate, sample rate, channel count, compression level,
  subtitle/metadata options, and a custom yt-dlp filename pattern.
- **Format inspection**: use **List formats** to inspect the formats yt-dlp reports for a
  URL, then enter an exact format expression such as `137+140` when needed.
- **Playlist visibility and proxy support**: playlist items are logged individually, and
  an HTTP/SOCKS proxy can be configured per user.

## Supported platforms and preview

After you paste the first link, GGU_VDOD fetches a lightweight preview containing the
title, thumbnail, uploader, duration, platform, and available resolution/bitrate when the
site exposes that metadata. Preview fetching never starts a download.

The preview names the source clearly (for example, **YouTube**, **X**, or **Facebook**).
Use **Download thumbnail (HQ)** to save the largest platform-provided thumbnail; the
small preview card stays lightweight while the saved image keeps its original quality.

If a platform blocks the full preview behind sign-in or age verification, GGU_VDOD makes
a separate best-effort attempt to show only public page metadata such as the title,
uploader, and thumbnail. It does not bypass account, cookie, age, or regional access
restrictions; authorized browser cookies or a `cookies.txt` file are still required for
restricted downloads.

The app uses the extractor set bundled with its installed yt-dlp version. Open
**Help → Supported platforms** to search the complete live extractor list for that build.
Common categories include YouTube, Vimeo, TikTok, Instagram, Facebook, X/Twitter, Reddit,
Twitch, Kick, Rumble, Dailymotion, SoundCloud, Bandcamp, Bilibili, archive.org, news and
streaming services, podcasts, music sites, and live-stream platforms.

The extractor list can also include adult-content platforms such as PornHub, XHamster,
XNXX, XVideos, YouPorn, SpankBang, Stripchat, and related sites when supported by the
installed yt-dlp version. Availability is extractor-dependent, may change without notice,
and may require cookies, a proxy, age verification, or other authorized access. The
official list explains that listed sites are not guaranteed to work because websites
change frequently: https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md.
- **Live-stream capture**: live URLs can be handed to yt-dlp while broadcasting, with an
  option to request capture from the beginning when the service provides that stream.
- **Dark mode**: the whole interface, including the log panel, dropdowns, and progress
  bar, now uses a dark color scheme. On Windows 10/11 the title bar goes dark too.
- **ffmpeg auto-detected by default**: the field pre-fills itself on startup (checks your
  system PATH, a bundled `ffmpeg` folder next to the exe, and common install locations)
  instead of starting blank.
- **Log panel fixed**: download progress and status updates from the background download
  thread previously could occasionally fail to reach the on-screen log. They're now routed
  through a proper thread-safe queue that the UI polls, and any unexpected error is written
  straight into the log instead of disappearing silently - so if something ever does go
  wrong, you'll see it there rather than a blank panel.

## A note on legal use

Downloading YouTube videos can conflict with YouTube's Terms of Service depending on
the content and what you do with it. This tool is meant for content you own, have
explicit permission to save, or that's licensed for reuse (e.g. Creative Commons) -
please make sure you have the right to download whatever you use it on.

## Change log

- **#017 — MP4-only video output**: video downloads now merge directly to MP4 and clean
  matching MKV/intermediate and subtitle sidecar files after success, leaving the final
  MP4 as the only video file from that download.

- **#016 — Clean preview loading and full library audit**: loading a new link now
  immediately clears the previous title and thumbnail so stale preview content cannot
  ghost underneath the loader. The update action now audits yt-dlp, Pillow, PyInstaller,
  Python, and the selected FFmpeg executable in a detailed read-only report.

- **#015 — Source-labelled HQ thumbnails**: added a platform source label to previews
  and a high-quality thumbnail download action that selects the largest thumbnail offered
  by the source.
- **#014 — Comprehensive local media conversion**: added broad video and audio output
  formats, local FFmpeg video-to-video/audio-to-audio/video-to-audio conversion, and
  Advanced controls for codec, bitrate, resolution, frame rate, audio, compression,
  metadata, subtitles, and filename patterns.
- **#013 — Preserve FFmpeg and restricted previews**: restored FFmpeg beside the
  release executable, preserved a local build-source copy outside Git, and added a
  clearly labeled public title/uploader/thumbnail fallback when full metadata is blocked
  by sign-in or age verification. The fallback never bypasses access restrictions.
- **#012 — Fix preview and dialog boundaries**: corrected the About/Help/Preferences
  layout crash, constrained the preview placeholder to a real compact card, and reflowed
  Advanced controls so browse and update buttons stay visible.
- **#011 — Restore compact downloader layout**: returned the main controls to one
  single-page interface, made Advanced a collapsible tab-style section, reduced the
  preview card to a compact 16:9 size, and corrected the oversized content width.
- **#010 — Advanced tab and landing pages**: moved ffmpeg and advanced output controls
  into an Advanced tab, and replaced Help/About alert popups with full landing pages.
  About credits XerumGG and lists the supportive development resources used by the app.
- **#009 — Enlarge thumbnail preview**: the preview now uses a readable 16:9 display area
  and scales the fetched thumbnail to fit it.
- **#008 — Link preview and platform directory**: added title/thumbnail metadata preview
  after pasting a URL and a dynamic Help menu listing for the installed yt-dlp extractors,
  including adult-content extractors when present.
- **#007 — Portable entry undo/redo fix**: replaced the unsupported Tk `Entry` undo option
  with a compatible history implementation so the packaged app opens correctly on all
  supported Tk builds.
- **#005 — Quality identifiers in filenames**: video downloads now include the actual
  selected height, such as `[2160p]`, `[1440p]`, or `[720p]`; MP3 downloads include the
  selected encoding target, such as `[320kbps]` or `[144kbps]`.
- **#006 — Traditional desktop controls**: added File/Edit/View/Window/Help/About menus,
  Undo/Redo and standard text-editing commands, plus Preferences for key bindings and
  scroll speed. The generated `VDOs/` output folder remains excluded by `.gitignore`.
- **#004 — Scrolling and stable project improvements**: added animated scrolling,
  controllable scroll speed, and stability fixes while preserving the original executable.
