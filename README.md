# GGU_VDOD

Simple Windows media downloader powered by yt-dlp and FFmpeg.

## What it does

- Video downloads use **MP4 by default**.
- You can change the video format to MKV, MOV, AVI, WebM, FLV, MPEG, TS, M4V, OGV, or 3GP.
- Audio-only downloads support MP3, WAV, AAC, FLAC, OGG, Opus, M4A, WMA, AIFF, and ALAC.
- Choose quality, subtitles, metadata, thumbnail embedding, cookies, proxy, and filename pattern.
- Preview the title, source, duration, resolution, and thumbnail before downloading.
- Downloads resume after connection loss. The footer shows speed, progress, transfer size, and ETA.
- Help, About, Preferences, undo/redo, context menus, and a scroll-speed setting are included.
- Themes include Dark, Fainted, Orange, Green Hacker, and Custom. Custom exposes every UI color
  and saves the palette for the next launch.
- Buttons and checkboxes use larger hit areas, clear hover/press feedback, and colorful selected
  indicators that return to a blank state when unchecked.

Use this only for media you own or are allowed to download. Follow site rules and local law.

## Quick setup

Requirements: Python 3.9+, FFmpeg, and Windows for the packaged `.exe`.

One-line setup and build on Windows:

```bat
build.bat
```

The executable is created at `dist\GGU_VDOD.exe`. Put FFmpeg at `dist\ffmpeg\ffmpeg.exe`,
or install it on PATH. The app detects it automatically.

Run from source:

```bat
venv\Scripts\python.exe app.py
```

## Download

1. Paste one or more links.
2. Leave **Video** and **MP4** selected, or choose another format.
3. Choose a folder and click **Download**.
4. Open **Advanced** for cookies, subtitles, metadata, FFmpeg, proxy, exact format IDs,
   and conversion controls.

Change themes with **Edit > Preferences > Themes and colors**. Pick a preset or choose
**Custom**, edit the hex colors, and click **Apply and save**.

If a link needs sign-in, select an authorized browser cookie source or a `cookies.txt` file.
The app does not bypass DRM, private access, age checks, bot checks, or regional blocks.

## Useful one-line commands

Update the development libraries:

```bat
venv\Scripts\python.exe -m pip install --upgrade yt-dlp Pillow PyInstaller
```

Check versions without changing anything:

```bat
venv\Scripts\python.exe -m pip list
```

Build the original executable again:

```bat
build.bat
```

Use `$env:GGU_BUILD_MODE='onedir'; .\build.bat` in PowerShell for a folder build.

## Troubleshooting

- **No MP4 or merge error:** install FFmpeg or place `ffmpeg.exe` beside the executable.
- **Cookie database error:** close the browser, or export and select `cookies.txt`.
- **Subtitle HTTP 429:** retry with subtitles off; the video download can still work.
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

Developed by **XerumGG** using Python, Tkinter/ttk, yt-dlp, FFmpeg, Pillow, PyInstaller,
and Python standard-library networking/threading tools.

## Changelog

- **#020 - Larger intuitive controls**: enlarged buttons, added hover/press/disabled feedback,
  and improved checkbox/radio indicators with accent-colored selected states.

- **#019 - UI themes and custom colors**: added four presets plus a saved Custom palette
  with editable window, panel, input, log, text, border, accent, status, tooltip, and
  selection colors.

- **#018 — MP4 default with format choices**: restored all video format choices while
  keeping MP4 as the default. Shortened this README and added simple one-line commands.
- **#017 — Clean video merging**: MP4 merging and matching sidecar cleanup were added.
- **#016 — Preview loading and library audit**: stale preview ghosting was fixed and the
  update report was expanded beyond yt-dlp.
